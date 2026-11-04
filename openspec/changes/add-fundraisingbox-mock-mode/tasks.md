# Tasks

## 1. Backend: mode, mock and wiring

- [x] 1.1 Add the `FUNDRAISINGBOX_MODE` setting (`live` default, `mock`, anything else is a clear configuration error naming the setting and the allowed values) and a gateway `Protocol` that `FundraisingBoxClient` already satisfies; verify tests for default, mock, invalid value and that the live client still passes its existing tests
- [x] 1.2 Implement `MockFundraisingBox` (built-in example companies, created companies searchable afterwards, case-insensitive substring search, ids from 900001, real `person_payload`/`company_payload` mapping so over-long info is refused, payload returned with the created record) and pick it in `build_services`; verify tests for search in any case, a created company found afterwards, distinct ids, the info-length refusal recording nothing, and that no HTTP request is made (respx with no routes)
- [x] 1.3 Health and startup: the token is required only in `live` mode, the health response says `"fundraisingbox": "mock"` in mock mode only, and startup logs a warning; add the protected `GET /api/app-info` returning `{fundraisingbox_mode}` and list it as protected in the route-protection test; verify tests for healthy-without-token in mock, 503-without-token in live, the log warning, 401 anonymous and the exact response of `/api/app-info`
- [x] 1.4 Payload preview: keep `demo_payload` on the session in mock mode only, return it in `SessionOut`, discard it with the session; regenerate the OpenAPI types; verify tests for the payload (info lines, ContactPilot custom field) after a mock send, none in live mode, and gone after the session is discarded or expires
- [ ] 1.5 Checkpoint: owner reviews and commits this group (tasks 1.1 to 1.4)

## 2. Frontend: make the mock unmistakable

- [x] 2.1 `useAppInfo()` and a banner in `AppLayout` shown only in mock mode on every signed-in page; verify Testing Library tests for banner in mock, no banner in live, banner on the scan, account and users pages, and an axe check
- [x] 2.2 Done screen in mock mode: says the contact was not sent to FundraisingBox and shows a `<details>` with the payload that would have been sent; verify tests for the wording, the payload content, no payload and no extra text in live mode, and an axe check
- [ ] 2.3 Checkpoint: owner reviews and commits this group (tasks 2.1 to 2.2)

## 3. Docs and end-to-end

- [ ] 3.1 Document `FUNDRAISINGBOX_MODE` in the README table and `.env.example` (the existing documentation test must pass), the Sliplane runbook (including a go-live checklist line "set `FUNDRAISINGBOX_MODE=live` and add the token") and update `docs/demo-day-plan.md` to use mock mode; verify `pytest tests/test_env_docs.py` and a read-through of the changed docs
- [ ] 3.2 Container smoke check in mock mode with no token: extend `scripts/smoke-container.sh` so a container with `FUNDRAISINGBOX_MODE=mock` and no token is healthy, reports `mock`, and a card sent through the API returns a demo record without any outbound call; verify the script passes
- [ ] 3.3 End-to-end in a real browser against the real server in mock mode (headless Chrome, no model key needed by using the API to create the session): sign in, review, pick an example company, send, and see the banner, the wording and the payload; verify by running it once and recording the result in the demo plan
- [ ] 3.4 Checkpoint: owner reviews and commits this group (tasks 3.1 to 3.3)
