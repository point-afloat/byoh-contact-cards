# Design

## Context

Builds on `build-contact-card-importer`: a FastAPI backend serving a Vite-built React SPA from `frontend/dist`, in-memory review sessions (single worker), configuration via environment variables, and `/api/health`. `add-user-accounts` adds the app's own login and a SQLite database under `DATA_DIR`. See proposal.md for motivation.

Observed from Sliplane's public docs (checked while planning; re-verify at implementation):
- Services deploy from a Git repo Dockerfile or a registry image.
- Sliplane sets a `PORT` env var (8080–65535) the service must listen on; one public port per service.
- Health check defaults to `/`, must return 2xx **without authentication**, and gates traffic shifting on deploy.
- Sliplane documents a basic-auth proxy pattern, but no built-in app login. An earlier version of this design used that proxy; it was dropped because users would then live in proxy config and need a developer to change (see `add-user-accounts`).
- Volume mount details were not confirmed from the docs and must be checked.

## Goals / Non-Goals

**Goals:**
- A small, reproducible, non-root image that follows Sliplane's port and health contract.
- User data survives redeploys via a mounted volume.
- Clear runbook so deployment can be repeated by someone other than the developer.

**Non-Goals:**
- Authentication logic (see `add-user-accounts`), proxies, multiple replicas, autoscaling, CI/CD, custom domains.

## Decisions

1. **Multi-stage Dockerfile:** stage 1 `node:<lts>-slim` runs `npm ci && npm run build`; stage 2 `python:3.12-slim` installs backend deps with uv (locked, no dev), copies `frontend/dist`, creates `/data` owned by a non-root user, and runs as that user. *Alternatives:* Railpack auto-detect (can't reliably combine Node build and Python runtime), two containers for frontend/backend (needless complexity).

2. **Run command:** `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1` via an entrypoint script using `exec` so SIGTERM reaches uvicorn. Single worker by design (in-memory sessions, SQLite).

3. **Health endpoint `/api/health`:** returns 200 `{status:"ok"}` when settings validate and `DATA_DIR` is writable, 503 with a non-sensitive reason otherwise; never requires auth and never calls external APIs (no model or FundraisingBox calls). It is the Sliplane health check path. It is on the auth allow-list in `add-user-accounts`.

4. **One public service, no proxy:** the app is the only service; access control is in the app. This removes a moving part and the config-file user management.

5. **Persistent volume:** a Sliplane volume mounted at `/data`; `DATA_DIR` defaults to `/data`. The image declares `/data` as a volume for local `docker run` parity. Startup checks writability. *Alternative:* external database (extra service and cost for ~10 users).

6. **Configuration only through env vars**, documented in `.env.example` and a README table; the container fails fast with a clear log line on missing required values. `.dockerignore` excludes `.env`, `node_modules`, `.venv`, caches and git data.

7. **Local parity:** `docker-compose.yml` builds the same image, mounts a named volume at `/data`, and reads `.env`.

8. **Verification:** a smoke script builds the image, runs it with dummy env and a temp volume, and checks `/api/health`, SPA index, non-root user, and that data survives a container replacement.

## Risks / Trade-offs

- [App exposed publicly before auth exists] → this change must not be deployed publicly without `add-user-accounts`; runbook states it as a precondition and the first-deploy checklist verifies anonymous requests get 401.
- [Volume lost or misconfigured, users disappear] → startup/health check for writable `DATA_DIR`, runbook step to verify the mount survives a redeploy, bootstrap admin recreates access.
- [In-memory review sessions lost on redeploy or crash] → spec requires a clear "session expired, rescan" message; acceptable for a low-volume tool.
- [Sliplane docs or UI change] → runbook links the official pages and is verified during the first real deployment.
- [Image size / build time (Node + Python)] → multi-stage build, slim bases, cached dependency layers.
- [Hosted model endpoint receives card images] → unchanged from the main change; documented there.

## Open Questions

- Which Sliplane plan/server size and region to use (an EU region is advisable for personal data); does not change the specs or tasks.
