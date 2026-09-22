#!/usr/bin/env bash
#
# check-skill-inventory.sh — assert the README keeps step with what is actually
# in skills/.
#
# A skill needs no registration anywhere: every host is pointed at ./skills and
# picks up whatever is in it, so a new directory installs and works the moment
# it lands. That is also why a half-added skill is silent — no manifest fails to
# parse, no command errors. The README table simply lacks a row, the install
# snippets still count four, and one host manifest still describes the plugin as
# it was before. The skill works; the reader is told a number that is one short.
#
# This checks the part that can be checked mechanically:
#
#   - every directory under skills/ has a row in the README table
#   - the table lists exactly as many skills as skills/ holds
#   - every skill is named more than once in the README, because a table row
#     alone means the install snippets and the bundled-resources section were
#     not updated — one mention is the signature of a half-added skill
#
# It cannot check whether the prose is any good, nor whether the four host
# manifests describe the plugin consistently. That is a review. Version drift
# across those manifests is `scripts/bump-version.sh --check`.
#
# Usage:
#   scripts/check-skill-inventory.sh     # exits non-zero with a list of gaps

set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"

shopt -s nullglob
dirs=(skills/*/)
shopt -u nullglob

if [ "${#dirs[@]}" -eq 0 ]; then
  echo "error: no skill directories under skills/" >&2
  exit 1
fi

status=0
count=${#dirs[@]}

for dir in "${dirs[@]}"; do
  name="$(basename "$dir")"

  # The table row is the only place a skill is introduced, so it anchors both
  # this check and the count below.
  if ! grep -Fq "| \`skills/${name}/\` |" README.md; then
    echo "::error::README.md has no table row for '${name}' — add one under '## Available skills'" >&2
    status=1
    continue
  fi

  mentions="$(grep -Fc "skills/${name}" README.md || true)"
  if [ "${mentions:-0}" -lt 2 ]; then
    echo "::error::'${name}' is named ${mentions:-0} time(s) in README.md — a new skill also needs the install snippets for each host, and its bundled-resources section if it ships scripts" >&2
    status=1
  fi
done

rows="$(grep -Fc "| \`skills/" README.md || true)"
if [ "${rows:-0}" -ne "$count" ]; then
  echo "::error::README.md lists ${rows:-0} skill(s) but skills/ holds ${count}" >&2
  status=1
fi

if [ "$status" -eq 0 ]; then
  echo "OK: ${count} skills, every one listed in README.md"
fi
exit $status
