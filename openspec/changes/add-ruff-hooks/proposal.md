# Proposal

## Why

Python code in this repository is written partly by Claude Code and partly by people, and ruff formatting and lint errors currently only get caught when someone remembers to run `ruff`. Two hooks close that gap: a Claude Code hook gives immediate feedback on every file Claude edits, and a pre-commit hook is the safety net for every contributor and editor.

## What Changes

- **Claude Code hook**: after Claude edits or writes a Python file, run `ruff format` and `ruff check --fix` on that file; remaining problems that cannot be fixed automatically are reported back to Claude so it can correct them in the same turn.
- **pre-commit hook**: a `.pre-commit-config.yaml` that runs `ruff check --fix` and `ruff format` on staged Python files, blocking a commit when unfixable problems remain.
- Both hooks use the project's pinned ruff (`uv run ruff`) and its existing `[tool.ruff]` configuration in `pyproject.toml`, so results are identical everywhere.
- Short developer documentation on how to enable and verify each hook.

## Capabilities

### New Capabilities
<!-- None: developer tooling only; the app's behaviour does not change, so this change sets skip_specs. -->

### Modified Capabilities
<!-- None. -->

## Impact

- New files: `.claude/settings.json` (hook registration), `.claude/hooks/ruff.sh` or similar hook script, `.pre-commit-config.yaml`, a short section in the README or `docs/`.
- New dev dependency: `pre-commit` (in the `dev` dependency group).
- The repository is **not a git repository yet** (no `.git`), and pre-commit needs one. Running `git init` and `pre-commit install` is part of this change but requires the owner's go-ahead.
- No effect on runtime code, the container image, or the frontend.

## Assumptions

- Only Python is covered. The frontend's ESLint, mypy, and the test suites are out of scope (the prototype's pre-commit also ran mypy; that can be added later as a separate change).
- The Claude hook is shared project configuration (`.claude/settings.json`, committed), not a personal one.
- `uv` is available on contributors' machines, as the project already requires it.
- No CI pipeline exists, so enforcement beyond local hooks is out of scope.
