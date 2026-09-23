#!/usr/bin/env python3
"""Guard the retrieval skill's copy-paste paths for audit intent.

The skill is a public procedure. These checks keep its first query runnable
and prevent a released v0.5.0 user from reporting audit flags their binary
cannot send.

Run: python3 tests/test_retrieval_ai_context_examples.py
"""
import re
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
    """`skardi query` commands in one block, backslash continuations joined.

    commented=False returns runnable lines; commented=True returns the
    alternative forms written as `# skardi query ...` comment lines.
    """
    lines = [ln.strip() for ln in block.splitlines()]
    if commented:
        lines = [ln[1:].strip() for ln in lines if ln.startswith("#")]
    else:
        lines = [ln for ln in lines if not ln.startswith("#")]
    joined = "\n".join(lines).replace("\\\n", " ")
    return [c for c in joined.splitlines() if c.startswith("skardi query ")]


def audited(cmd):
    return "--purpose" in cmd


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
    """On a build that takes --task, every copy-paste query sends the pair and one identical task."""
    content = text()
    runnable = [c for b in bash_blocks(content) for c in query_commands(b, False) if audited(c)]
    assert runnable, "no runnable audited query found"
    tasks = set()
    for cmd in runnable:
        assert "--session-id" in cmd, cmd
        m = re.search(r'--task "([^"]+)"', cmd)
        assert m, f"audited query without --task: {cmd}"
        tasks.add(m.group(1))
    assert len(tasks) == 1, f"examples reword the task: {sorted(tasks)}"


def test_no_query_sends_task_without_the_pair():
    """The CLI refuses --task alone, in runnable and commented forms alike."""
    content = text()
    for block in bash_blocks(content):
        for cmd in query_commands(block, False) + query_commands(block, True):
            if "--task " in cmd:
                assert "--purpose" in cmd and "--session-id" in cmd, cmd


def test_every_audited_template_has_both_fallback_forms():
    """Each template shows a no---task form (pair only) and a v0.5.0 form (no flags)."""
    content = text()
    for block in bash_blocks(content):
        if not any(audited(c) for c in query_commands(block, False)):
            continue
        alts = query_commands(block, True)
        assert any(audited(c) and "--task" not in c for c in alts), block
        assert any(not audited(c) and "--session-id" not in c and "--task" not in c
                   for c in alts), block

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
