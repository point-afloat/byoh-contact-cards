#!/usr/bin/env bash
# Tests for ruff-python.sh. Run from anywhere: bash .claude/hooks/test-ruff-python.sh
# Uses temporary files (inside the project, so the hook accepts them) and removes them.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="$(cd "$here/../.." && pwd)"
hook="$here/ruff-python.sh"
tmp="$(mktemp -d "$project/.ruff-hook-test.XXXXXX")"
outside="$(mktemp -d)"
trap 'rm -rf "$tmp" "$outside"' EXIT

failures=0
pass() { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; failures=$((failures + 1)); }

# run_hook <file-path-or-raw-stdin> -> sets $status and $stderr_text
run_hook() {
  local input="$1" err
  err="$(mktemp)"
  CLAUDE_PROJECT_DIR="$project" bash "$hook" <<<"$input" >/dev/null 2>"$err"
  status=$?
  stderr_text="$(cat "$err")"
  rm -f "$err"
}
tool_json() { printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$1"; }

# 1. A misformatted file gets lint-fixed (import order) and formatted; exit 0, silent.
printf 'import sys\nimport os\nprint(os.name, sys.argv)\ny   =  1\n' >"$tmp/messy.py"
started="$(date +%s%N)"
run_hook "$(tool_json "$tmp/messy.py")"
elapsed_ms=$((($(date +%s%N) - started) / 1000000))
expected=$'import os\nimport sys\n\nprint(os.name, sys.argv)\ny = 1\n'
[ "$status" -eq 0 ] && [ -z "$stderr_text" ] && [ "$(cat "$tmp/messy.py")" == "${expected%$'\n'}" ] \
  && pass "misformatted file is fixed and formatted (exit 0, silent), took ${elapsed_ms} ms" \
  || fail "misformatted file: status=$status stderr='$stderr_text' content='$(cat "$tmp/messy.py")'"

# 2. A problem ruff cannot fix: exit 2 with the ruff message.
printf 'print(undefined_name)\n' >"$tmp/broken.py"
run_hook "$(tool_json "$tmp/broken.py")"
[ "$status" -eq 2 ] && grep -q 'F821' <<<"$stderr_text" && grep -q 'broken.py' <<<"$stderr_text" \
  && pass "unfixable lint error gives exit 2 with the ruff message" \
  || fail "unfixable error: status=$status stderr='$stderr_text'"

# 3. A syntax error is reported too.
printf 'def f(:\n' >"$tmp/syntax.py"
run_hook "$(tool_json "$tmp/syntax.py")"
[ "$status" -eq 2 ] && pass "syntax error gives exit 2" || fail "syntax error: status=$status"

# 4. Files that must be left alone (all exit 0 and unchanged).
untouched() { # name, path, content
  printf '%s' "$3" >"$2"
  run_hook "$(tool_json "$2")"
  [ "$status" -eq 0 ] && [ "$(cat "$2")" == "$3" ] && pass "$1 is left untouched" \
    || fail "$1: status=$status content changed or non-zero exit"
}
untouched "non-Python file" "$tmp/notes.txt" 'x   =  1'
mkdir -p "$tmp/.venv" "$tmp/node_modules"
untouched ".venv path" "$tmp/.venv/messy.py" 'x   =  1'
untouched "node_modules path" "$tmp/node_modules/messy.py" 'x   =  1'
untouched "path outside the project" "$outside/messy.py" 'x   =  1'

# 5. Missing file, missing file_path, garbage input: nothing to do.
run_hook "$(tool_json "$tmp/does-not-exist.py")"
[ "$status" -eq 0 ] && pass "missing file is ignored" || fail "missing file: status=$status"
run_hook '{"tool_name":"Edit","tool_input":{}}'
[ "$status" -eq 0 ] && pass "no file_path is ignored" || fail "no file_path: status=$status"
run_hook 'this is not json'
[ "$status" -eq 0 ] && pass "invalid JSON is ignored" || fail "invalid JSON: status=$status"

# 6. A path with spaces and shell characters is handled as one argument.
mkdir -p "$tmp/dir with space"
printf 'x   =  1\n' >"$tmp/dir with space/a b;c.py"
run_hook "$(tool_json "$tmp/dir with space/a b;c.py")"
[ "$status" -eq 0 ] && [ "$(cat "$tmp/dir with space/a b;c.py")" == "x = 1" ] \
  && pass "path with spaces and shell characters is formatted safely" \
  || fail "unusual path: status=$status content='$(cat "$tmp/dir with space/a b;c.py")'"

echo
if [ "$failures" -eq 0 ]; then echo "All tests passed."; else echo "$failures test(s) failed."; exit 1; fi
