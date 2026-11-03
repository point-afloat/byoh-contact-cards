# Checkpoints: recovery points while Claude works through tasks

Two things make sure you always get a chance to review and commit while an OpenSpec change is
being implemented.

## 1. Checkpoint tasks in the plan

`openspec/config.yaml` has a rule for task lists: every task group ends with

```markdown
- [ ] 2.4 Checkpoint: owner reviews and commits this group (tasks 2.1 to 2.3)
```

Claude must not commit and must not tick this task, so the apply workflow stops there. Review the
group, commit it, then tick the box yourself. The rule applies when a change's tasks are written.
Changes planned before the rule was added do not have these tasks.

## 2. Automatic snapshots (a safety net)

`.claude/hooks/checkpoint-on-tick.sh` is a Claude Code hook (registered in `.claude/settings.json`).
When Claude ticks a task box in `openspec/changes/<change>/tasks.md`, the hook silently saves a
snapshot of the whole working tree as a git commit object:

```
refs/checkpoints/<change>/<task id>-<timestamp>
```

It never commits to your branch, never touches the staging area or your files, and ignores
everything in `.gitignore` (so `.env` is never captured). Because it works without asking, a long
unattended run still leaves one recovery point per finished task.

**Not covered:** edits made by you in an editor, and tick changes Claude makes through shell
commands (for example `sed`). The hook only sees Claude's Edit and Write tools.

## Using the snapshots

```bash
# list them, oldest first
git for-each-ref --sort=creatordate \
  --format='%(creatordate:short) %(refname:short)  %(subject)' refs/checkpoints

# what changed between two snapshots (that is, what a task did)
git diff --stat refs/checkpoints/<change>/<first> refs/checkpoints/<change>/<second>

# what a snapshot holds compared with your last real commit
git diff --stat HEAD refs/checkpoints/<change>/<id>

# look at one file as it was, or bring it back
git show refs/checkpoints/<change>/<id>:path/to/file
git restore --source=refs/checkpoints/<change>/<id> -- path/to/file

# browse a whole snapshot without touching your working tree
git worktree add ../checkpoint-view refs/checkpoints/<change>/<id>
git worktree remove ../checkpoint-view
```

To turn finished work into commits, use the difference between consecutive snapshots to see which
files belong to which task, stage those files and commit with the task id in the message.

## Housekeeping

- Snapshots live only in this repository's `.git` folder. They are not pushed, not shown by
  `git log`, and share storage with your normal objects, so they cost almost nothing.
- After installing the hook, or if a change shows unexpected snapshots, record the ticks that
  already exist so only later ticks count: `bash .claude/hooks/checkpoint-on-tick.sh --init`.
- Delete them when you no longer need them:

```bash
git for-each-ref --format='%(refname)' refs/checkpoints | xargs -r -n1 git update-ref -d
rm -rf "$(git rev-parse --absolute-git-dir)/checkpoint-state"
```

## Testing the hook

```bash
bash .claude/hooks/test-checkpoint-on-tick.sh
```

It runs 30 checks in a scratch repository (never this one): what a snapshot contains, that the
branch, staging area and files stay untouched, repeat calls, ignored paths, and a repository with
no commits and no git identity.
