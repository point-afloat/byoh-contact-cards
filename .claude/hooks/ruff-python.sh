#!/usr/bin/env bash
# Claude Code PostToolUse hook: lint-fix and format the Python file Claude just edited.
#
# Input : the tool call as JSON on stdin ({"tool_input": {"file_path": "..."}, ...}).
# Output: exit 0 and silence when there is nothing to do or everything was fixed;
#         exit 2 with ruff's message on stderr when problems remain, which Claude Code
#         feeds back to Claude so it can fix them in the same turn.
#
# Only existing .py files inside the project (and outside .venv/ and node_modules/) are
# touched. The file path is always passed to ruff as a separate quoted argument.
set -uo pipefail

project="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
project="$(realpath -e -- "$project" 2>/dev/null)" || exit 0

# Parse with python3 (jq may not be installed). Any parse problem means "nothing to do".
file="$(python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
except Exception:
    pass
' 2>/dev/null)"

[ -n "$file" ] || exit 0
case "$file" in *.py) ;; *) exit 0 ;; esac

real="$(realpath -e -- "$file" 2>/dev/null)" || exit 0 # does not exist (yet): nothing to do
case "$real" in "$project"/*) ;; *) exit 0 ;; esac    # outside the project
rel="${real#"$project"/}"
case "$rel" in
  .venv/* | */.venv/* | node_modules/* | */node_modules/*) exit 0 ;;
esac

cd "$project" || exit 0

# Lint-fix first, then format, so import sorting and formatting do not fight.
output="$(uv run --quiet ruff check --fix -- "$real" 2>&1)"
status=$?
uv run --quiet ruff format -- "$real" >/dev/null 2>&1 || true

if [ "$status" -ne 0 ]; then
  {
    echo "ruff found problems in $rel that could not be fixed automatically:"
    echo "$output"
  } >&2
  exit 2
fi
exit 0
