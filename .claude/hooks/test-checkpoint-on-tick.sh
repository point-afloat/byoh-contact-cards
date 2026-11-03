#!/usr/bin/env bash
# Tests for checkpoint-on-tick.sh in a scratch git repository (the real repository is never used).
#   bash .claude/hooks/test-checkpoint-on-tick.sh
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hook="$here/checkpoint-on-tick.sh"
repo="$(mktemp -d)"
outside="$(mktemp -d)"
trap 'rm -rf "$repo" "$outside"' EXIT

failures=0
pass() { echo "ok   - $1"; }
fail() { echo "FAIL - $1"; failures=$((failures + 1)); }
check() { local description="$1"; shift; if "$@"; then pass "$description"; else fail "$description"; fi; }

git_in() { git -C "$repo" "$@"; }
refs() { git_in for-each-ref --format='%(refname)' "refs/checkpoints/${1:-}"; }
count_refs() { refs "${1:-}" | grep -c . || true; }
tasks="$repo/openspec/changes/demo/tasks.md"

# run the hook the way Claude Code does: tool call as JSON on stdin; captures stdout+stderr
run_hook() { # file path
  output="$(printf '{"tool_name":"Edit","tool_input":{"file_path":"%s"}}' "$1" |
    CLAUDE_PROJECT_DIR="$repo" bash "$hook" 2>&1)"
  status=$?
}
write_tasks() { # ticked ids...
  {
    echo "# Tasks"
    for id in 1.1 1.2 2.1; do
      if [[ " $* " == *" $id "* ]]; then echo "- [x] $id Task $id does a thing"; else echo "- [ ] $id Task $id does a thing"; fi
    done
  } >"$tasks"
}

# --- a repository with one commit -------------------------------------------------------------
git init -q -b main "$repo"
git_in config user.name tester
git_in config user.email tester@example.org
mkdir -p "$repo/openspec/changes/demo" "$repo/openspec/changes/archive/2026-01-01-old" "$repo/src"
write_tasks
echo "original" >"$repo/src/a.txt"
echo "will be deleted" >"$repo/src/gone.txt"
printf 'ignored.txt\nforced.txt\n' >"$repo/.gitignore"
echo "v1" >"$repo/forced.txt" # tracked on purpose although .gitignore matches it
git_in add -A && git_in add -f forced.txt && git_in commit -q -m "initial"
head_before="$(git_in rev-parse HEAD)"

# --- first sight of a task list records a baseline and snapshots nothing ----------------------
run_hook "$tasks"
check "the first edit of a task list only records a baseline" test "$(count_refs)" -eq 0 -a "$status" -eq 0

# --- a tick snapshots the whole working tree, without touching anything --------------------------
write_tasks 1.1
echo "changed by the task" >"$repo/src/a.txt"
echo "brand new file" >"$repo/src/new.txt"
rm "$repo/src/gone.txt"
echo "secret" >"$repo/ignored.txt"
echo "v2" >"$repo/forced.txt"
status_before="$(git_in status --porcelain)"
run_hook "$tasks"
check "ticking a task creates one checkpoint under refs/checkpoints/<change>/" test "$(count_refs demo)" -eq 1
ref="$(refs demo | head -1)"
snap() { git_in show "$ref:$1" 2>/dev/null; }
check "the checkpoint name carries the task id" bash -c '[[ "$1" == refs/checkpoints/demo/1.1-* ]]' _ "$ref"
check "it contains the modified file" test "$(snap src/a.txt)" = "changed by the task"
check "it contains a new, untracked file" test "$(snap src/new.txt)" = "brand new file"
check "it records the deletion" bash -c '! git -C "$1" cat-file -e "$2:src/gone.txt" 2>/dev/null' _ "$repo" "$ref"
check "a file tracked in spite of .gitignore keeps its new content" test "$(snap forced.txt)" = "v2"
check "it never captures ignored files" bash -c '! git -C "$1" cat-file -e "$2:ignored.txt" 2>/dev/null' _ "$repo" "$ref"
check "it contains the ticked task list" bash -c 'git -C "$1" show "$2:openspec/changes/demo/tasks.md" | grep -q "\[x\] 1.1"' _ "$repo" "$ref"
check "its parent is the current HEAD" test "$(git_in rev-parse "$ref^")" = "$head_before"
check "its message names the change, the task and its text" \
  bash -c 'git -C "$1" log -1 --format=%s "$2" | grep -q "checkpoint: demo 1.1 Task 1.1 does a thing"' _ "$repo" "$ref"

check "the branch is untouched (same HEAD, no new commit)" test "$(git_in rev-parse HEAD)" = "$head_before" -a "$(git_in rev-list --count HEAD)" -eq 1
check "the staging area is untouched" git_in diff --cached --quiet
check "the working tree is untouched (same status as before)" test "$(git_in status --porcelain)" = "$status_before"
check "files in the working tree keep their content" test "$(cat "$repo/src/a.txt")" = "changed by the task" -a ! -e "$repo/src/gone.txt"
check "the hook is silent and succeeds" test -z "$output" -a "$status" -eq 0

# --- repeat calls and several ticks ---------------------------------------------------------------
run_hook "$tasks"
check "calling again without a new tick creates nothing" test "$(count_refs demo)" -eq 1
sleep 1
write_tasks 1.1 1.2 2.1
run_hook "$tasks"
check "two new ticks at once give two more checkpoints" test "$(count_refs demo)" -eq 3
write_tasks 1.1 1.2
run_hook "$tasks"
check "un-ticking creates nothing" test "$(count_refs demo)" -eq 3
sleep 1
write_tasks 1.1 1.2 2.1
run_hook "$tasks"
check "ticking it again later creates a new checkpoint" test "$(count_refs demo)" -eq 4

# --- init: existing ticks are not snapshotted -----------------------------------------------------
mkdir -p "$repo/openspec/changes/other"
printf -- '- [x] 1.1 already done\n- [ ] 1.2 not yet\n' >"$repo/openspec/changes/other/tasks.md"
CLAUDE_PROJECT_DIR="$repo" bash "$hook" --init
run_hook "$repo/openspec/changes/other/tasks.md"
check "--init remembers existing ticks so they are not snapshotted" test "$(count_refs other)" -eq 0
printf -- '- [x] 1.1 already done\n- [x] 1.2 not yet\n' >"$repo/openspec/changes/other/tasks.md"
run_hook "$repo/openspec/changes/other/tasks.md"
check "a tick after --init is snapshotted" test "$(count_refs other)" -eq 1

# --- things that must be ignored -----------------------------------------------------------------
total="$(count_refs)"
echo "- [x] 1.1 done" >"$repo/openspec/changes/archive/2026-01-01-old/tasks.md"
run_hook "$repo/openspec/changes/archive/2026-01-01-old/tasks.md"
check "an archived change's tasks are ignored" test "$(count_refs)" -eq "$total" -a "$status" -eq 0
run_hook "$repo/src/a.txt"
check "other files are ignored" test "$(count_refs)" -eq "$total" -a "$status" -eq 0
echo "- [x] 9.9 outside" >"$outside/tasks.md"
run_hook "$outside/tasks.md"
check "a file outside the project is ignored" test "$(count_refs)" -eq "$total" -a "$status" -eq 0
run_hook "$repo/openspec/changes/demo/nope.md"
check "a missing file is ignored" test "$(count_refs)" -eq "$total" -a "$status" -eq 0
output="$(echo 'not json' | CLAUDE_PROJECT_DIR="$repo" bash "$hook" 2>&1)"; status=$?
check "invalid JSON is ignored and silent" test "$status" -eq 0 -a -z "$output"
output="$(echo '{"tool_input":{}}' | CLAUDE_PROJECT_DIR="$repo" bash "$hook" 2>&1)"; status=$?
check "no file_path is ignored and silent" test "$status" -eq 0 -a -z "$output"
output="$(echo '{}' | CLAUDE_PROJECT_DIR="$outside" bash "$hook" 2>&1)"; status=$?
check "outside a git repository it does nothing, silently" test "$status" -eq 0 -a -z "$output"

# --- a repository with no commits yet and no git identity -------------------------------------
fresh="$(mktemp -d)"
git init -q -b main "$fresh"
mkdir -p "$fresh/openspec/changes/first"
printf -- '- [ ] 1.1 start\n' >"$fresh/openspec/changes/first/tasks.md"
echo data >"$fresh/file.txt"
for step in baseline tick; do
  [ "$step" = tick ] && printf -- '- [x] 1.1 start\n' >"$fresh/openspec/changes/first/tasks.md"
  printf '{"tool_input":{"file_path":"%s"}}' "$fresh/openspec/changes/first/tasks.md" |
    HOME="$fresh" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_SYSTEM=/dev/null CLAUDE_PROJECT_DIR="$fresh" bash "$hook" >/dev/null 2>&1
done
check "it works in a repository with no commits and no identity configured" \
  test "$(git -C "$fresh" for-each-ref refs/checkpoints | grep -c .)" -eq 1
rm -rf "$fresh"

echo
if [ "$failures" -eq 0 ]; then echo "All tests passed."; else echo "$failures test(s) failed."; exit 1; fi
