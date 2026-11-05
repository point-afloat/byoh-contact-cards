# Proposal

## Why

Today a card's email, phone, mobile number, address and website are written as text lines into the
person's `info` field, so FundraisingBox has no real email, phone, address or website records for
the person. They cannot be searched, filtered, mailed or synced, and `info` is limited to 1000
characters. The FundraisingBox API has proper records for each of these. The shortcut was chosen
early (to avoid a half-created person); the owner now wants the app to use the correct schema.

## What Changes

- A sent contact becomes a person record plus separate child records, as the FundraisingBox API
  defines them: an address (`personAddresses`), a phone (`personPhones`) for the phone and one for
  the mobile number, an email address (`personEmailAddresses`) and a website (`personWebsites`),
  each linked to the person by `fb_person_id`.
- `info` keeps only what has no field of its own: the card's notes, and the company name when the
  person is not linked to a company record. Email, phone, mobile, address and website no longer go
  into it.
- Values are checked locally against the API's documented limits and enumerations (for example a
  2-letter country code, email at most 100 characters, phone at most 50) before anything is created.
- Because several calls are needed, a failure part way leaves a person that already exists. The
  send remembers which records were created, tells the user what is missing, and a retry creates
  only the missing ones, never a second person.
- For a card with only a company, the contact details are attached to the company record.
- The ContactPilot custom field is sent as the API documents it: `{"id": 16786, "value": "Sync"}`.
- A company record's last name is cut to the documented 100 characters so long company names are
  not refused.
- The mock mode (`add-fundraisingbox-mock-mode`) mirrors the same calls and its done-screen
  preview shows the person and every child record that would have been sent.

## Capabilities

### New Capabilities
- `fundraisingbox-record-schema`: how a confirmed contact is written to FundraisingBox: which
  records are created, how fields map to the documented API schema, how values are checked, and
  how a partly failed send is resumed.

### Modified Capabilities
<!-- None: openspec/specs is empty. The existing "Field mapping" and "Contact channel data
     preserved" requirements live in the not yet archived build-contact-card-importer change
     (capability fundraisingbox-export) and are superseded by this capability; see design.md. -->

## Impact

- Backend: `app/fundraisingbox/mapping.py` (payload builders and local checks),
  `app/fundraisingbox/client.py` (four new create calls, one shared request function),
  `app/fundraisingbox/gateway.py` and `mock.py` (the same calls in the mock), `app/send.py`
  (the multi-step send and its resume state), `app/sessions.py` (what was already created).
- API: `demo_payload` on a session changes shape in mock mode (a person plus lists of child
  records). The send error messages gain a "created but incomplete" case.
- Frontend: the done screen shows the larger preview; the review form is unchanged.
- Docs: the Sliplane runbook and demo plan mention that the first live send should be checked in
  FundraisingBox itself.
- Risk: more calls per contact, so more points of failure and a slower send. Mitigated by local
  checks first and by resuming only what is missing.

## Assumptions

- Business cards carry work details, so every child record is created with `type: "work"`, except
  the mobile number (see design). The first record of each kind is the main one (`is_main: true`).
- Only one address, one email and one website exist on a card, so at most one of each is created,
  plus up to two phone numbers.
- The card has no state, birthday or messenger, so those fields are never sent.
- Out of scope: tags, bank accounts, newsletter or contact preferences, a second address, and
  reading existing child records back from FundraisingBox.
