# Deploying to Sliplane

How to run the contact card importer as a Docker container on [Sliplane](https://sliplane.io).
Facts about Sliplane below come from its documentation (checked 2026-10-31); re-check the linked
pages if something behaves differently:

- [Deploying a service](https://docs.sliplane.io/services/deploying-a-service): sources, Dockerfile path, environment variables, `PORT`, health check
- [Volumes](https://docs.sliplane.io/services/volumes): persistent storage and mount paths

> **Check the sign-in before you share the address.** The app has its own login (see the
> [administrator guide](admin-guide.md)) and it handles personal data and can create records in
> FundraisingBox. After the first deploy, confirm that opening the address without signing in shows
> only the sign-in page and that `GET /api/auth/me` answers `401` (step 5 below).

## What the container expects

| | |
|---|---|
| Port | Listens on `$PORT` (Sliplane sets it), default `8080`, on all interfaces |
| Health check | `GET /api/health`: `200` when configured and `/data` is writable, otherwise `503` naming the problem. Needs no login. |
| Runs as | uid/gid `10001` (user `app`), a single process |
| Persistent data | `/data` (accounts and similar; never card images or contacts) |
| Settings | environment variables only, see the [Configuration table](../README.md#configuration) |
| Shutdown | stops within a second or two on `SIGTERM` |

## Runbook

### 1. Choose how Sliplane gets the code

- **GitHub repository.** Sliplane's Git source is GitHub. Push this repository to GitHub, connect it
  in Sliplane (you need admin access on the repository), choose the branch, keep the Dockerfile path
  `/Dockerfile` and the Docker context `/`. New commits then deploy automatically unless you switch
  off *Automatically deploy new commits*.
- **Registry image.** Build and push the image yourself, then choose *Registry* as the source and
  enter the image as `registry/namespace/image:tag` (no `https://`), for example
  `ghcr.io/<owner>/contact-card-importer:1.0.0`. Use an explicit tag in production, not `latest`.
  Private images need registry credentials added to the team. This works whatever hosts the code
  (for example GitLab).

### 2. Create the service

1. In the Sliplane project choose **Deploy Service** and pick (or create) a server. An EU region is
   advisable because the app handles personal data.
2. Add the service with the source from step 1.

### 3. Set the environment variables

Enter them as key-value pairs (or paste a `.env`). They are runtime variables; the Dockerfile needs
no `ARG`s. Mark every secret as **secret** so its value is hidden after saving.

| Variable | Value |
|---|---|
| `LLM_MODEL` | the model chosen for your cards |
| `LLM_API_KEY` | your model provider's key (**secret**) |
| `FUNDRAISINGBOX_MODE` | `live` (the default) sends to FundraisingBox; `mock` sends nothing and needs no token (demos and tests) |
| `FUNDRAISINGBOX_APITOKEN` | the FundraisingBox API token (**secret**), needed only in `live` mode |
| `LLM_BASE_URL`, `LLM_RESPONSE_FORMAT`, `UPLOAD_MAX_BYTES`, ... | only if you need to change the defaults |
| `SLIPLANE_USER_ID` | `10001` (the user the container runs as) |
| `SLIPLANE_GROUP_ID` | `10001` |
| `INITIAL_ADMIN_EMAIL` | the first administrator's email address |
| `INITIAL_ADMIN_PASSWORD` | their starting password, at least 12 characters (**secret**) |

Leave `PORT` and `DATA_DIR` unset: Sliplane provides `PORT`, and `DATA_DIR` defaults to `/data`.
`SLIPLANE_USER_ID` and `SLIPLANE_GROUP_ID` make Sliplane give the attached volume to the user the
container runs as; without them the app cannot write to `/data` and the health check reports it.

`INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` create the first administrator the first time
the app starts with an empty database. Deploy once, sign in, change the password under **Account**,
then **remove `INITIAL_ADMIN_PASSWORD`** from the service. The app ignores both settings whenever
any account exists, and it reports itself unhealthy (naming the setting) if there are no accounts
and they are missing or unusable. Everything after that, such as inviting colleagues, is done in the
app; see the [administrator guide](admin-guide.md).

Leave `TRUSTED_PROXY` unset (`false`) unless you have confirmed that Sliplane's proxy passes the
visitor's address in `X-Forwarded-For`. While it is off, sign-in throttling sees every visitor as
coming from the proxy's address, so many failed sign-ins from anywhere can pause sign-in for
everyone for a few minutes (the per-email limit keeps working either way). Setting it to `true`
without a proxy in front lets visitors fake their address.

**Go-live checklist (leaving mock mode).** Set `FUNDRAISINGBOX_MODE=live` and add the
`FUNDRAISINGBOX_APITOKEN`, then redeploy. While the mode is `mock`, a banner on every page says
nothing is sent. The first live send creates a person and one record per detail (email, phone,
address, website): open that person in FundraisingBox and check the records and the ContactPilot
field before trusting it.

### 4. Health check and volume

- **Health check route:** `/api/health`. It must answer `200` to an unauthenticated request, or the
  deployment does not receive traffic. Sliplane checks it before switching traffic and then every
  minute; three failures in a row send an email.
- **Volume:** attach a server volume and mount it at the absolute path `/data`. Attaching a volume
  redeploys the service.

### 5. Deploy and check

1. Deploy and watch the deployment log. A configuration problem shows up as `Startup problem: ...`
   lines naming the setting (never its value), and the health check stays red.
2. Open the service URL and confirm the app loads and `GET /api/health` returns `{"status":"ok"}`.
3. Without signing in, check that the address shows only the sign-in page and that
   `GET /api/auth/me` answers `401`. Then sign in as the first administrator, open **Users** and
   invite a colleague following the administrator guide.
4. Redeploy once and confirm your users are still there (they live in `/data`).

## Things to know

- **Volumes disable zero-downtime deploys.** Sliplane stops the old container before starting the new
  one, so a release that fails to start causes downtime until you fix or roll back. A failed *build*
  leaves the old deployment running.
- **Review sessions live in memory.** A redeploy ends open reviews; the user sees "This review
  session has expired. Please scan the card again."
- **One public port per service**, and *Expose Service* cannot be changed after creation (redeploy a
  copy if you must).
- **Docker Compose files are not deployed by Sliplane.** `docker-compose.yml` here is only for
  running the same image locally.
- If `/data` is reported as not writable, check `SLIPLANE_USER_ID` and `SLIPLANE_GROUP_ID` first.

## Run the same image locally

```bash
cp .env.example .env     # fill in LLM_MODEL, LLM_API_KEY and FUNDRAISINGBOX_APITOKEN
docker compose up --build
```

`bash scripts/smoke-container.sh` builds the image and checks the whole contract above in real
containers (health, non-root, one process, no secrets in the image, data surviving a replacement,
`PORT`, misconfiguration, clean shutdown).
