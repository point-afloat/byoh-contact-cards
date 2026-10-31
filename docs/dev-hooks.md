# Ruff hooks

Python code is kept formatted and lint-clean by [ruff](https://docs.astral.sh/ruff/) in two places.
Both use the ruff version pinned in `uv.lock` and the rules in `[tool.ruff]` in `pyproject.toml`.

| Hook | Runs when | Covers |
|---|---|---|
| Claude Code hook (`.claude/hooks/ruff-python.sh`) | right after Claude edits or writes a `.py` file | edits made through Claude Code |
| pre-commit (`.pre-commit-config.yaml`) | on `git commit`, for staged Python files | everything that is committed, from any editor |

## Claude Code hook

Registered in `.claude/settings.json` as a `PostToolUse` hook on `Edit|Write|MultiEdit`. For each
Python file inside the project (never under `.venv/` or `node_modules/`) it runs
`ruff check --fix` and then `ruff format`.

- Everything fixable is fixed silently.
- If ruff still reports a problem, the hook exits with code 2 and prints ruff's message, which
  Claude Code passes back to Claude so it can fix the problem in the same turn.
- Verified with Claude Code 2.1.316. The first time, Claude Code may ask you to review the project's
  hooks (use `/hooks`) before they take effect.

Test the hook script itself (uses temporary files and cleans up after itself):

```bash
bash .claude/hooks/test-ruff-python.sh
```

## pre-commit

One-time setup after cloning:

```bash
uv sync
uv run pre-commit install
```

On `git commit`, staged Python files go through `ruff check --fix` and `ruff format`:

- If a hook changed a file, the commit is stopped. Review the change, `git add` the file again and
  commit again.
- If ruff reports something it cannot fix, the commit is stopped and the message tells you what to
  change.

Run the same checks on every tracked file at any time:

```bash
uv run pre-commit run --all-files
```

`git commit --no-verify` skips pre-commit. Use it only deliberately; the hooks are a local safety
net, not enforcement. If a CI system is added, run `uv run ruff check .` and
`uv run ruff format --check .` there as well.

## Running ruff by hand

```bash
uv run ruff check --fix .   # lint and apply safe fixes
uv run ruff format .        # format
```

## Scope

Only Python is covered. The frontend (ESLint, TypeScript), mypy and the test suites are not part of
these hooks.
