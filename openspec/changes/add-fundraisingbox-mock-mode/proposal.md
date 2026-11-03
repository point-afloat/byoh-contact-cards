# Proposal

## Why

The app is about to be shown to the NGO on a Sliplane demo server. Every send creates a real person
(and possibly a company) in whatever FundraisingBox account the token belongs to, and there is no
way to try the full flow without that. A mock mode lets the whole scan, review and send flow be
tested end to end, and shown, without touching any real FundraisingBox data and without needing a
FundraisingBox account or token.

## What Changes

- New setting `FUNDRAISINGBOX_MODE` with two values: `live` (default, today's behaviour) and `mock`.
- In `mock` mode no request ever goes to FundraisingBox. Company search, company creation and person
  creation are answered by an in-memory stand-in that behaves like the real thing: it finds
  companies from a small built-in list plus any created since the server started, and returns new
  ids. The API token is not needed.
- The mock is impossible to miss: a notice on every signed-in page, a clear message on the done
  screen, `mock` shown by the health check, and a warning in the startup log.
- After a send in mock mode, the done screen can show the exact data that would have been sent to
  FundraisingBox, so the field mapping can be checked by eye.
- `live` mode is unchanged and remains the default everywhere, including the Docker image.

## Capabilities

### New Capabilities
- `fundraisingbox-mock`: running the app against an in-memory stand-in for FundraisingBox, clearly
  marked, for demos and end-to-end testing.

### Modified Capabilities
<!-- None: openspec/specs is empty. The existing fundraisingbox-export requirements (in the not yet
     archived build-contact-card-importer change) stay as they are for live mode. -->

## Impact

- Backend: a small gateway interface with the live client and a new in-memory mock behind it,
  the setting, health reporting, a protected `GET /api/app-info`, and an optional preview of the
  payload on the session. No change to live behaviour.
- Frontend: a banner in the app layout and an extended done screen. API types are regenerated.
- Docs: README configuration table, `.env.example`, the Sliplane runbook and the demo day plan.
- Risk: someone leaves mock mode on and believes cards are being saved. Mitigated by the banner on
  every page, the done-screen wording, the health check and the log line, and by `live` being the
  default.

## Assumptions

- The mock keeps its records in memory only. They disappear when the server restarts, which is fine
  for a demo and keeps personal data out of storage.
- The built-in example companies are made up (for example "Acme GmbH") and are shown to every
  signed-in user.
- Language model extraction is not mocked here; the Mistral key is still needed to scan cards.
- Out of scope: a separate mock HTTP server for FundraisingBox, mocking the model endpoint, and
  keeping a history of mock records beyond the preview on the done screen.
