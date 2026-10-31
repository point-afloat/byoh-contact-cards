# Tasks

## 1. Runtime contract in the backend (container-deployment)

- [ ] 1.1 Make the app read `PORT` (default 8080) in the run entrypoint and add `/api/health` returning 200/503 per config validity and `DATA_DIR` writability, without outbound calls or secrets; verify TestClient tests for healthy, missing-key (503, no secret in body), unwritable data dir (503), and a unit test for the port default/override
- [ ] 1.2 Make sure logging goes to stdout/stderr, never includes card data or credentials, and that expired/unknown review sessions return a distinct "session expired" error the frontend can show; verify a test asserting no card content or tokens in captured logs and a frontend test for the "scan again" message
- [ ] 1.3 Add `DATA_DIR` setting (default `/data`) with startup check; verify a test that startup fails with a clear message when it is missing or not writable and that no card data is written there

## 2. Container image (container-deployment)

- [ ] 2.1 Write the multi-stage `Dockerfile` (Node build stage, Python slim runtime with locked uv install, non-root user owning `/data`, `exec` entrypoint running one uvicorn worker on `${PORT:-8080}`) and `.dockerignore`; verify `docker build` succeeds from a clean checkout
- [ ] 2.2 Write a smoke script (`scripts/smoke-container.sh`) that runs the image with dummy env and a temp volume and checks `/api/health` is 200, `/` serves the SPA, the process user is non-root, only one worker runs, layers contain no `.env` or secrets, and data written to `/data` survives replacing the container; verify the script passes locally
- [ ] 2.3 Verify clean shutdown: `docker stop` finishes within the grace period and logs a graceful exit; verify against the smoke container
- [ ] 2.4 Add `docker-compose.yml` for local parity (named volume at `/data`, `.env`); verify `docker compose up` serves the app on the configured port

## 3. Configuration and docs for the container

- [ ] 3.1 Update `.env.example` with all deployment variables (including `PORT`, `DATA_DIR`) and document them in a README "Configuration" table; verify every variable the code reads is listed (test or grep script)
- [ ] 3.2 Make startup fail fast with a clear log line for missing required settings; verify by running the container without the model key and checking the log and the 503 health state

## 4. Sliplane deployment

- [ ] 4.1 Re-read Sliplane's current docs (deploying a service, health checks, volumes) and record the exact steps in `docs/deployment-sliplane.md`; verify the document links to the official pages used
- [ ] 4.2 Write the runbook: deploy from the repo Dockerfile as the single public service with env vars (including initial admin settings from `add-user-accounts`), a volume mounted at `/data`, and health check `/api/health`; state as a precondition that `add-user-accounts` is applied; verify a colleague can follow it unaided
- [ ] 4.3 Perform the first real deployment on Sliplane and verify: anonymous requests to app routes and API get the login page / 401, the health check passes without credentials, and the first admin can sign in
- [ ] 4.4 Redeploy with an open session and an existing second user; verify users persist, the "session expired" message appears for the open review, and a phone end-to-end run (upload, review, send to the FundraisingBox test account) succeeds
