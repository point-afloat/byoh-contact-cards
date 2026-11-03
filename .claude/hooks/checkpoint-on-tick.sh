#!/usr/bin/env bash
# Claude Code PostToolUse hook: when a task box in an OpenSpec change's tasks.md is newly ticked,
# silently save a snapshot of the whole working tree as a git commit object under
#   refs/checkpoints/<change>/<task id>-<timestamp>
#
# The snapshot is only a recovery point. This hook never commits to a branch, never touches the
# index or the working tree, and never fails the tool call (it always exits 0 and stays silent).
#
# Usage:
#   (as a hook)   reads the tool call as JSON on stdin ({"tool_input": {"file_path": "..."}})
#   --init        records the currently ticked tasks of every change, so only later ticks count
set -uo pipefail

project="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
project="$(realpath -e -- "$project" 2>/dev/null)" || exit 0
cd "$project" || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0 # not a git repository: nothing to do
state_dir="$(git rev-parse --absolute-git-dir)/checkpoint-state"
mkdir -p "$state_dir" 2>/dev/null || exit 0

# The ids ("1.2") of the boxes that are ticked in a tasks.md, one per line, sorted.
ticked_ids() {
  grep -E '^- \[[xX]\] [0-9]+\.[0-9]+' -- "$1" 2>/dev/null |
    sed -E 's/^- \[[xX]\] ([0-9]+\.[0-9]+).*/\1/' | LC_ALL=C sort -u
}

# The text of a task, shortened, for the snapshot's message.
task_text() { # file id
  grep -E "^- \[[xX ]\] $2([^0-9]|$)" -- "$1" 2>/dev/null | head -1 |
    sed -E 's/^- \[[xX ]\] [0-9]+\.[0-9]+ *//' | cut -c1-80
}

snapshot() { # change id text
  local change="$1" id="$2" text="$3"
  (
    index="$(mktemp -u)"
    export GIT_INDEX_FILE="$index"
    trap 'rm -f "$index"' EXIT
    identity=()
    if [ -z "$(git config user.email 2>/dev/null)" ]; then
      identity=(-c user.name="checkpoint" -c user.email="checkpoint@localhost")
    fi
    parent=()
    if git rev-parse --verify -q HEAD >/dev/null; then
      parent=(-p "$(git rev-parse HEAD)")
      # Start from HEAD so files that are tracked although .gitignore matches them stay in
      # the snapshot, and so `git add` only has to look at what changed.
      git read-tree HEAD || exit 0
    fi
    git add -A >/dev/null 2>&1 || exit 0 # honours .gitignore: ignored files are never captured
    tree="$(git write-tree)" || exit 0
    commit="$(git "${identity[@]}" commit-tree "$tree" "${parent[@]}" \
      -m "checkpoint: $change $id $text")" || exit 0
    git update-ref "refs/checkpoints/$change/$id-$(date +%Y%m%d-%H%M%S)" "$commit"
  ) >/dev/null 2>&1
}

if [ "${1:-}" = "--init" ]; then
  for file in openspec/changes/*/tasks.md; do
    [ -f "$file" ] || continue
    change="$(basename "$(dirname "$file")")"
    ticked_ids "$file" >"$state_dir/$change"
  done
  exit 0
fi

# --- hook mode ----------------------------------------------------------------------------------
file="$(python3 -c '
import json, sys
try:
    print(json.load(sys.stdin).get("tool_input", {}).get("file_path", ""))
except Exception:
    pass
' 2>/dev/null)"
[ -n "$file" ] || exit 0

real="$(realpath -e -- "$file" 2>/dev/null)" || exit 0
rel="${real#"$project"/}"
[[ "$rel" =~ ^openspec/changes/([^/]+)/tasks\.md$ ]] || exit 0 # only active changes' task lists
change="${BASH_REMATCH[1]}"

state="$state_dir/$change"
current="$(ticked_ids "$real")"
if [ ! -f "$state" ]; then # first time this list is seen: remember it, snapshot nothing
  printf '%s\n' "$current" >"$state"
  exit 0
fi
newly="$(comm -13 <(LC_ALL=C sort -u "$state") <(printf '%s\n' "$current" | sed '/^$/d'))"
printf '%s\n' "$current" | sed '/^$/d' >"$state"

while IFS= read -r id; do
  [ -n "$id" ] && snapshot "$change" "$id" "$(task_text "$real" "$id")"
done <<<"$newly"
exit 0
