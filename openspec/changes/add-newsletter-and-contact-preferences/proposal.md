# Proposal

## Why

A FundraisingBox person carries the person's newsletter subscription and which ways of contact
are allowed. Today every contact the app creates gets FundraisingBox's defaults, so someone who
asked for the newsletter or agreed to a call is not recorded, and staff must fix each record by
hand. Whether the person agreed can only come from the human at the review step: a printed card
is not consent, so the model must never fill it in.

## What Changes

- The review page gets a "Communication" section with four options, all unticked by default:
  newsletter, contact by email, contact by phone, contact by post.
- The options are set by the person reviewing, are never read from the card image, and are not
  part of what the model extracts.
- When sent, a ticked option is written to the person's FundraisingBox flags
  (`wants_newsletter` set to `true`, and `wants_no_email`, `wants_no_call` or `wants_no_post` set to `false`). An unticked
  option sends nothing, so FundraisingBox's own default stays (no consent assumed).
- The mock-mode preview shows the flags that would be sent.
- Because the flags are person-level, a ticked or changed option is not applied once the person
  already exists after a partly failed send; the message says so.

## Capabilities

### New Capabilities
- `contact-preferences`: how a reviewer records newsletter and contact-method consent on the
  review page and how it is written to FundraisingBox.

### Modified Capabilities
<!-- None: openspec/specs has no spec for the send mapping yet; this builds on the unarchived
     use-fundraisingbox-person-schema change (fundraisingbox-record-schema). -->

## Impact

- Frontend: `ReviewScreen.tsx` (a new section and its state), `strings.ts`, the generated API
  types, and tests. The choices are sent with the confirm request, not saved as part of the draft.
- Backend: the send request gains a `preferences` object (`app/send.py`), the person payload
  builder maps it (`app/fundraisingbox/mapping.py`), the gateway and mock carry it through
  (`app/fundraisingbox/client.py`, `mock.py`, `gateway.py`).
- API: `POST /api/sessions/{id}/send` accepts `preferences`; all fields are optional and default
  to not selected, so existing callers keep working.
- Data protection: the app stores nothing new; the choices live only in the request.

## Assumptions

- Direction of the flags (to be confirmed on the first live send, see tasks): the API documents
  `wants_no_email`, `wants_no_post`, `wants_no_call` only as "Information about contact
  opportunities", with `true` as the response default. This change reads them as "do not contact
  this way" and sends `false` for a ticked option.
- `wants_newsletter` appears only in the API's request example, with no description. It is
  assumed to mean subscribed, sent as `true` when ticked.
- `wants_mailing` is not used: its meaning is not documented clearly enough to guess.
- The options are not saved in the draft, so a page reload clears them.
- Out of scope: recording where or when consent was given, double opt-in, unsubscribing, and
  tags or interest groups.
