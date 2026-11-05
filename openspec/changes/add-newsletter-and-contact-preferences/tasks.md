# Tasks

## 1. Backend: preferences in the send

- [x] 1.1 Add the preferences (newsletter, email, phone, post; all default false) to the send request and map them in the person payload builder: a ticked newsletter sets `wants_newsletter` true, a ticked email, phone or post sets `wants_no_email`, `wants_no_call` or `wants_no_post` to false, an unticked option adds no key. Verify with tests that the default adds no keys, each option adds exactly its key, all four together, and that an unknown key in the request is refused. (files: app/fundraisingbox/mapping.py, app/send.py, tests/test_fb_mapping.py, tests/test_send.py)
- [x] 1.2 Carry the preferences through the gateway, the live client and the mock, so the mock preview shows the same keys the live body contains, for a person and for a company-only card. Verify with respx tests of the live body and mock tests of the preview, with and without options. (files: app/fundraisingbox/gateway.py, app/fundraisingbox/client.py, app/fundraisingbox/mock.py, tests/test_fb_client.py, tests/test_fb_mock.py)
- [x] 1.3 Extend the `partly_sent` message so it lists the communication options among the changes not applied to the existing record, and keep the person from being created twice. Verify with a test that fails a detail step, changes an option, resends, and checks the message and that only one person was created. (files: app/send.py, tests/test_api_send.py)
- [ ] 1.4 Checkpoint: owner reviews and commits this group (tasks 1.1 to 1.3)

## 2. Frontend: the Communication section

- [x] 2.1 Regenerate the API types and add a Communication group of four checkboxes (all unticked, labelled, in a labelled `fieldset`) to the review form, with the strings, sending the choices with the confirm call and never saving them in the draft. Verify with Testing Library tests: all four unticked on first render even when the contact has an email and phone, toggling, the exact `preferences` in the send request, not part of the draft save, and an axe check. (files: frontend/src/screens/ReviewScreen.tsx, frontend/src/strings.ts, frontend/src/screens/ReviewScreen.test.tsx, frontend/src/api/schema.d.ts)
- [x] 2.2 Show the flags in the done-screen preview test data and check the preview prints them. Verify that a mock-mode send with the newsletter ticked shows `wants_newsletter` in the preview. (files: frontend/src/screens/DoneScreen.test.tsx)
- [ ] 2.3 Checkpoint: owner reviews and commits this group (tasks 2.1 to 2.2)

## 3. Docs and final checks

- [ ] 3.1 Document the options for staff (what each one means, that nothing is pre-ticked, that a card is not consent, that choices are not applied after a partial failure) in the admin or demo docs. Verify with `frontend/src/docs.test.ts` and a read-through. (files: docs/admin-guide.md)
- [ ] 3.2 Run everything: `uv run pytest -q`, `uv run ruff check .`, `uv run mypy app`, `npm test` and `npm run api:check` in `frontend/`, and the mock-mode check in `scripts/smoke-container.sh` extended to send with the newsletter ticked. Verify all pass. (files: scripts/smoke-container.sh)
- [ ] 3.3 Checkpoint: owner reviews and commits this group (tasks 3.1 to 3.2)

## Workflow follow-up

These need the real FundraisingBox account and are reference steps, not tracked tasks.

- On the first live send with each option ticked, open the person in FundraisingBox and confirm the
  newsletter and the three contact flags read as intended. If a flag points the other way, flip it in
  the one mapping table; if `wants_newsletter` is rejected as unknown, remove it as described in design.md.
- Before syncing specs, reconcile with `fundraisingbox-record-schema` from
  `use-fundraisingbox-person-schema` so the two do not describe the person body differently.
