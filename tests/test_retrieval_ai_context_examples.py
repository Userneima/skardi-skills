#!/usr/bin/env python3
"""Guard the retrieval skill's copy-paste paths for audit intent.

The skill is a public procedure. These checks keep its first query runnable
and prevent a released v0.5.0 user from reporting audit flags their binary
cannot send.

Run: python3 tests/test_retrieval_ai_context_examples.py
"""
import re
import shlex
from pathlib import Path


SKILL = Path(__file__).parents[1] / "skills" / "retrieval" / "SKILL.md"


def text():
    return SKILL.read_text(encoding="utf-8")


def test_main_build_mints_a_session_before_the_first_query():
    """A first-step peek must never expand an unset $SKARDI_SESSION."""
    content = text()
    session_setup = content.index("SKARDI_SESSION=$(uuidgen")
    first_audited_query = content.index("skardi query --purpose")
    assert session_setup < first_audited_query, (
        "mint the main-build session before the first audited query, including "
        "the step-1 peek"
    )


def test_v050_reporting_example_does_not_claim_audit_flags():
    """Release users need evidence wording that matches their executable CLI."""
    content = text()
    report = content[content.index("Lead with the answer"):]
    assert "v0.5.0 build" in report
    assert "/* purpose: paid order count and revenue */" in report




def bash_blocks(content):
    """Fenced ```bash blocks, in document order."""
    return re.findall(r"```bash\n(.*?)```", content, re.S)


def query_commands(block, commented):
    """`skardi query` commands in one block, tokenized the way bash would.

    commented=False reads the runnable lines; commented=True reads the
    alternative forms written as `# skardi query ...` comment lines. A line
    continues only when it ends in a bare backslash, as in bash, and
    shlex drops trailing `# ...` comments, so a flag that sits in a comment
    is not counted as sent. A line that starts with a flag means a
    continuation broke, and fails loudly.
    """
    lines = []
    for raw in block.splitlines():
        stripped = raw.strip()
        is_comment = stripped.startswith("#")
        if is_comment != commented:
            continue
        lines.append(stripped[1:].strip() if commented else raw.rstrip("\n"))
    commands, current = [], ""
    for line in lines:
        current += line
        if line.endswith("\\"):
            current = current[:-1] + " "
            continue
        tokens = shlex.split(current, comments=True)
        current = ""
        # The command ends at the first control operator (`|`, `&&`, ...).
        ops = [i for i, t in enumerate(tokens) if t in {"|", "||", "&&", ";", "&"}]
        tokens = tokens[: ops[0]] if ops else tokens
        if tokens[:2] == ["skardi", "query"]:
            commands.append(tokens)
        elif tokens and tokens[0].startswith("-"):
            raise AssertionError(f"orphaned flag line, a continuation broke: {line}")
    return commands


def flags(tokens):
    """{flag: value} for a tokenized command; accepts `--f v` and `--f=v`."""
    out = {}
    i = 2
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            if "=" in tok:
                name, value = tok.split("=", 1)
            elif i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
                name, value = tok, tokens[i + 1]
                i += 1
            else:
                name, value = tok, None
            out[name] = value
        i += 1
    return out


def sql_of(f):
    return f.get("-e") or f.get("--sql")


def audited(tokens):
    return "--purpose" in flags(tokens)


def test_task_probe_runs_before_the_first_audited_query():
    """The --task probe is a real command, separate from the pair probe, run before any audited query."""
    content = text()
    blocks = bash_blocks(content)
    probe = next(
        (i for i, b in enumerate(blocks)
         if any(ln.strip().startswith("skardi query --help | grep -q -- '--task'")
                for ln in b.splitlines())),
        None,
    )
    assert probe is not None, "no executable --task probe line in a bash block"
    assert "'--purpose'" not in next(
        ln for ln in blocks[probe].splitlines() if "'--task'" in ln
    ), "probe --task on its own line, not folded into the pair probe"
    first_audited = next(
        i for i, b in enumerate(blocks) if any(audited(c) for c in query_commands(b, False))
    )
    assert probe < first_audited, "the --task probe must come before the first audited query"


def test_runnable_audited_queries_carry_the_same_task():
    """On a build that takes --task, every copy-paste query sends the pair, one identical task, and its SQL."""
    content = text()
    runnable = [flags(c) for b in bash_blocks(content) for c in query_commands(b, False) if audited(c)]
    assert runnable, "no runnable audited query found"
    tasks = set()
    for f in runnable:
        assert f.get("--session-id"), f
        assert sql_of(f), f"audited query lost its SQL: {f}"
        assert f.get("--task"), f"audited query without --task: {f}"
        tasks.add(f["--task"])
    assert len(tasks) == 1, f"examples reword the task: {sorted(tasks)}"


def test_no_query_sends_task_without_the_pair():
    """The CLI refuses --task alone, in runnable and commented forms alike."""
    content = text()
    for block in bash_blocks(content):
        for cmd in query_commands(block, False) + query_commands(block, True):
            f = flags(cmd)
            if "--task" in f:
                assert "--purpose" in f and "--session-id" in f, cmd


def test_every_audited_query_has_both_fallback_forms():
    """Each runnable audited query has, for the same SQL, a pair-only form and a v0.5.0 form."""
    content = text()
    for block in bash_blocks(content):
        alts = [flags(c) for c in query_commands(block, True)]
        for cmd in query_commands(block, False):
            if not audited(cmd):
                continue
            sql = sql_of(flags(cmd))
            same = [a for a in alts if sql_of(a) == sql]
            assert any("--purpose" in a and "--session-id" in a and "--task" not in a
                       for a in same), f"no pair-only form for: {sql}"
            assert any(not ({"--purpose", "--session-id", "--task"} & a.keys())
                       for a in same), f"no v0.5.0 form for: {sql}"


if __name__ == "__main__":
    failures = 0
    for name, fn in sorted(globals().items()):
        if not name.startswith("test_") or not callable(fn):
            continue
        try:
            fn()
            print(f"  ok    {name}")
        except AssertionError as exc:
            failures += 1
            print(f"  FAIL  {name}: {exc}")
    print(f"\n{'FAILED' if failures else 'all passed'} ({failures} failure(s))")
    raise SystemExit(bool(failures))
