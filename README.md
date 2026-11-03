# Contact card importer

Scan a contact card with a phone camera, review what a vision model read from it, and send it to
FundraisingBox.

> This README is a stub that currently documents configuration. The full setup and usage guide is
> still to be written (see task 6.2 of the `build-contact-card-importer` change).

**More documentation**

- [Administrator guide](docs/admin-guide.md): adding colleagues, deactivating users, resetting
  passwords, and what to do if nobody can sign in.
- [Deploying to Sliplane](docs/deployment-sliplane.md)
- [Demo day plan](docs/demo-day-plan.md): using Sliplane's free 48-hour demo server for the NGO appointment
- [Ruff hooks](docs/dev-hooks.md)
- [Checkpoints](docs/checkpoints.md): task checkpoints and automatic snapshots while Claude implements a change

## Configuration

All settings come from environment variables. Locally, copy `.env.example` to `.env`; in Docker or
on Sliplane, set them on the service. Secrets are never written to the logs or sent to the browser.

| Variable | Default | Required | What it does |
|---|---|---|---|
| `LLM_BASE_URL` | `https://api.mistral.ai/v1` | no | Base URL of an OpenAI-compatible chat-completions endpoint with image input. |
| `LLM_MODEL` | none | **yes** | Model name sent to that endpoint (the cheapest vision model that reads your cards well). |
| `LLM_API_KEY` | none | yes for hosted endpoints | API key for the endpoint. Not needed for a local server such as `http://localhost:1234/v1`. |
| `LLM_TIMEOUT` | `60` | no | Seconds to wait for the model. |
| `LLM_RESPONSE_FORMAT` | `json_schema` | no | `json_schema` asks for structured output and falls back to `json_object` by itself if the endpoint rejects it; `json_object` forces plain JSON mode. |
| `FUNDRAISINGBOX_APITOKEN` | none | **yes** | FundraisingBox API token. Without it the health check reports unhealthy and sending is refused. |
| `UPLOAD_MAX_BYTES` | `10485760` | no | Largest accepted card image (10 MiB). |
| `SESSION_TTL_SECONDS` | `1800` | no | How long an idle review session is kept in memory. |
| `SESSION_MAX_COUNT` | `200` | no | Most review sessions held at once. |
| `DATA_DIR` | `/data` | **yes** (must exist and be writable) | Where persistent data lives, such as user accounts. Mount a volume here. Card images and contacts are never written to it. Locally, set it to a folder such as `./data`. |
| `PORT` | `8080` | no | Port the server listens on. Sliplane sets this for you. |
| `STATIC_DIR` | `frontend/dist` | no | Folder with the built web app; only set it to serve the app from somewhere else. |
| `INITIAL_ADMIN_EMAIL` | none | **yes** until the first user exists | Email of the first administrator, created at startup when no user exists. Ignored afterwards. |
| `INITIAL_ADMIN_PASSWORD` | none | **yes** until the first user exists | Password of the first administrator (at least 12 characters). Remove it after the first deploy; it is ignored once any user exists. |
| `AUTH_SESSION_IDLE_HOURS` | `12` | no | Hours of inactivity after which a sign-in expires. |
| `AUTH_SESSION_DAYS` | `14` | no | Longest a sign-in lasts, however active the user is. |
| `AUTH_INVITE_TTL_HOURS` | `168` | no | How long an invitation link works (7 days). |
| `AUTH_RESET_TTL_MINUTES` | `60` | no | How long a password-reset link works. |
| `AUTH_COOKIE_SECURE` | `true` | no | Send the sign-in cookie only over HTTPS. Set `false` only for plain-http local development. |
| `TRUSTED_PROXY` | `false` | no | Set `true` behind exactly one proxy (such as Sliplane) so sign-in throttling sees real client addresses via `X-Forwarded-For`. |

`GET /api/health` answers `200` when the app is configured and `DATA_DIR` is writable, and `503`
with the names of the problems otherwise. It needs no login and never includes secret values.
