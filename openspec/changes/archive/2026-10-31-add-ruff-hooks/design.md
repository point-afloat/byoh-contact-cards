# Design

## Context

Ruff is already a dev dependency with its configuration in `pyproject.toml` (`line-length = 100`, rules `E, F, I, UP, B`, target `py312`), and the code has been kept clean by running it by hand. The repository has no `.git` directory, and `.claude/` currently contains only `commands/` and `skills/` (no `settings.json`, no hooks). The prototype in `../contact_cards` used a pre-commit config with *local* hooks calling `uv run ruff check .` and `uv run mypy src/`; that is the pattern to follow, minus mypy and plus formatting. See proposal.md for scope.

## Goals / Non-Goals

**Goals:**
- Python files Claude writes are formatted and lint-fixed immediately, and unfixable problems come back to Claude within the same turn.
- Commits cannot contain unformatted or lint-failing Python.
- One source of truth for rules (`pyproject.toml`) and one ruff version (the one pinned by `uv.lock`).

**Non-Goals:**
- mypy, pytest, ESLint, or any frontend checks; CI enforcement; reformatting unrelated files as part of this change.

## Decisions

1. **Claude hook = `PostToolUse` command hook on `Edit|Write|MultiEdit`**, registered in the committed `.claude/settings.json` and implemented by a small script (`.claude/hooks/ruff-python.sh`). It receives the tool call as JSON on stdin, reads `tool_input.file_path`, and does nothing unless the path is an existing `.py` file inside the project and not under `.venv/` or `node_modules/`. For such a file it runs `uv run --quiet ruff check --fix <file>` then `uv run --quiet ruff format <file>`. If the check still reports problems it prints them to stderr and exits `2`, which Claude Code feeds back to Claude so it can fix them; otherwise it exits `0` silently. *Alternatives:* `PreToolUse` (can't fix a file that doesn't exist yet), a `Stop` hook running ruff on the whole repo (feedback arrives too late and touches files Claude didn't edit), a settings-embedded one-liner (no room for the path filtering and stdin parsing). The JSON is parsed with `python3`, not `jq`, because `jq` may not be installed.

2. **Order is lint-fix first, then format**, as ruff recommends, so import sorting and formatting do not fight.

3. **pre-commit uses local hooks that call `uv run ruff`** (`ruff-check --fix` and `ruff-format`, `types: [python]`, filenames passed by pre-commit) instead of the `astral-sh/ruff-pre-commit` mirror. That keeps the version identical to `uv.lock` and the Claude hook, at the cost of requiring `uv` on every machine, which the project already requires. *Alternative:* the official mirror with a pinned `rev` (works without `uv`, faster to install, but a second place to keep in sync).

4. **`pre-commit` itself is a dev dependency** (`uv add --dev pre-commit`), so `uv sync` installs it and `uv run pre-commit install` activates it.

5. **Both hooks are needed, not redundant**: the Claude hook only sees edits made through Claude's edit tools (not shell `sed`, not human edits); pre-commit sees everything that gets committed but only at commit time.

6. **Git is a prerequisite for pre-commit**: the plan includes `git init`, but running it is the owner's decision because it turns this directory into a repository (the `.gitignore` already exists).

## Risks / Trade-offs

- [Auto-formatting changes the file right after Claude's edit] → Claude Code re-reads changed files; at worst a follow-up edit needs a fresh read. Accepted because it keeps files always formatted.
- [`uv run` adds latency to every Python edit] → ruff is fast; the script exits immediately for non-Python files; measure in task 1.1 and use `ruff` directly from `.venv/bin` if it is noticeable.
- [Exit code 2 semantics for `PostToolUse` could differ between Claude Code versions] → verified by a real edit in task 1.2; the documentation states the version it was tested with.
- [Files with syntax errors mid-edit trigger feedback] → intended; ruff reports the syntax error and Claude fixes it.
- [`git commit --no-verify` or contributors skipping `pre-commit install`] → documented; a CI check would be the real enforcement and is out of scope until a CI system exists.
- [Hook script runs arbitrary paths from tool input] → the script resolves the path and refuses anything outside the project directory, and passes it to ruff as a quoted argument, never through a shell string.

## Open Questions

- Whether to add mypy to pre-commit later (the prototype had it); deferrable, it would not change this design.
