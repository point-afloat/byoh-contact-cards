# Design

## Context

`Services.fundraisingbox` is a `FundraisingBoxClient` (app/fundraisingbox/client.py) with three
methods used by the send flow and the company search: `search_companies`, `create_company` and
`create_person`. The payloads are built by `app/fundraisingbox/mapping.py`. The health check
requires `FUNDRAISINGBOX_APITOKEN` (app/health.py). See proposal.md for motivation.

## Goals / Non-Goals

**Goals:**
- Exercise the real app, including the mapping and its validation, with no FundraisingBox at all.
- Make the mock unmistakable and `live` the safe default.

**Non-Goals:**
- A faithful HTTP-level fake of FundraisingBox (the live client is already tested with mocked HTTP
  against the documented API).
- Persisting mock records, or mocking the language model.

## Decisions

1. **A small gateway interface, two implementations.** A `Protocol` with `search_companies`,
   `create_company` and `create_person` (same signatures as today). `FundraisingBoxClient` stays as
   it is; a new `MockFundraisingBox` implements the same interface. `build_services` picks one from
   `settings.fundraisingbox_mode`. *Alternative:* a separate mock HTTP server plus a configurable base
   URL: more faithful at the HTTP level, but needs a second service on the demo server and a new
   setting. Rejected for the demo; it can be added later behind the same setting.

2. **The mock reuses the real mapping.** `create_person` builds `person_payload(...)` and
   `create_company` builds `company_payload(...)` exactly as live does, so the info-length check and
   the ContactPilot custom field are exercised. The built payload is returned with the created
   record (`CreatedRecord.payload`, empty in live mode).

3. **Mock data.** Three built-in example companies ("Acme GmbH" in Berlin, "Beispiel e.V." in
   Hamburg, "Stiftung Muster" in München) plus companies created since start, in a lock-protected
   in-memory list. Search is a case-insensitive substring match, limited like the live search.
   Identifiers come from a counter starting at 900001, so they are recognisably not real.

4. **Setting.** `fundraisingbox_mode: Literal["live", "mock"] = "live"` (env `FUNDRAISINGBOX_MODE`). The
   token stays optional in settings; the health check only requires it in `live` mode.

5. **Making it visible.**
   - Backend: the health response gains `"fundraisingbox": "mock"` in mock mode only; startup logs a
     warning; a protected `GET /api/app-info` returns `{fundraisingbox_mode}`.
   - Frontend: `useAppInfo()` (TanStack Query, `staleTime: Infinity`); `AppLayout` renders a
     full-width notice banner in mock mode; the done screen adds a sentence and a `<details>` element
     with the formatted payload.

6. **Payload preview.** The session gets an in-memory `demo_payload` (set only in mock mode) that is
   returned in `SessionOut` and goes away with the session (existing TTL and discard rules). It is
   never written to the database or the logs.

7. **Safety of the default.** `live` is the default in code, `.env.example`, the Docker image and the
   runbook. Only configuration can change it (no endpoint, no database setting).

## Risks / Trade-offs

- [Mock left on, people think cards are saved] → banner on every page, done-screen wording, health
  and log, `live` default, a line in the runbook's go-live checklist.
- [Mock and live drift apart] → both implement one interface, and one contract test runs the same
  scenarios against both (live with mocked HTTP, mock directly).
- [Preview shows personal data on screen] → only to the signed-in person who just sent it, only in
  mock mode, and it lives only as long as the review session.
- [Example companies look like real data] → obviously fictional names; documented.

## Open Questions

- Whether the example companies should be configurable (a JSON file) later; not needed for the demo.
