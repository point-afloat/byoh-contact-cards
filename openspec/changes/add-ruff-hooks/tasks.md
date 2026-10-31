# Tasks

## 1. Claude Code hook

- [x] 1.1 Write `.claude/hooks/ruff-python.sh` (reads the tool JSON from stdin with `python3`, handles only existing `.py` files inside the project and outside `.venv/`/`node_modules/`, runs `uv run --quiet ruff check --fix` then `ruff format`, prints remaining problems to stderr and exits 2, otherwise exits 0) and a test script `.claude/hooks/test-ruff-python.sh`; verify by running the test script, which feeds JSON for a misformatted file (gets formatted, exit 0), a file with an unfixable lint error (exit 2 with the ruff message), a non-Python path, a missing file, a `.venv/` path and a path outside the project (all untouched, exit 0), and note the measured run time per call
- [x] 1.2 Register the hook in the committed `.claude/settings.json` (`PostToolUse`, matcher `Edit|Write|MultiEdit`, command pointing at the script via `$CLAUDE_PROJECT_DIR`); verify (the `/hooks` listing is a UI check left to the owner; registration is proven by the live edits) that a real Claude Code edit of a temporary misformatted `.py` file is formatted automatically and a temporary file with an unfixable error makes Claude receive the ruff message (then delete the temporary files)

## 2. pre-commit hook

- [x] 2.1 Add `pre-commit` to the dev dependency group (`uv add --dev pre-commit`, needs the owner's approval to install a new package); verify `uv run pre-commit --version` works
- [x] 2.2 Create `.pre-commit-config.yaml` with two local hooks, `uv run ruff check --fix` and `uv run ruff format` (`language: system`, `types: [python]`, filenames passed); verify `uv run pre-commit validate-config` passes
- [x] 2.3 With the owner's go-ahead run `git init`, then `uv run pre-commit install`; verify `uv run pre-commit run --all-files` passes on the current code, that committing a staged misformatted file is stopped with the file fixed for re-staging, and that a file with an unfixable lint error blocks the commit with the ruff message (use temporary files and remove them afterwards)

## 3. Documentation

- [x] 3.1 Write `docs/dev-hooks.md` explaining what each hook does, how to enable pre-commit (`uv sync`, `uv run pre-commit install`), how to run both checks by hand (`uv run ruff check --fix .`, `uv run ruff format .`), the `--no-verify` caveat, and the Claude Code version the hook was verified with; verify every command in the document runs as written, and link it from the README once task 6.2 of `build-contact-card-importer` creates one

## Workflow follow-up

- If a CI system is added later, run `uv run ruff check .` and `uv run ruff format --check .` there so enforcement does not depend on local hooks.
