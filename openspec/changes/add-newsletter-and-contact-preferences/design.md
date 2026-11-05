# Design

## Context

`ReviewScreen` renders sections from `SECTIONS` (`frontend/src/screens/fields.ts`) with
react-hook-form over the `Contact` model, whose fields are strings that the vision model fills in
and the draft endpoint saves on blur. `person_payload` builds the person body
(`app/fundraisingbox/mapping.py`). A send is `SendRequest(contact, company)` (`app/send.py`) and the
person is created once, then detail records follow (see `use-fundraisingbox-person-schema`).

From the FundraisingBox persons reference: booleans `wants_mailing`, `wants_no_email`,
`wants_no_post`, `wants_no_call` ("Information about contact opportunities", response default
`true`); `wants_newsletter` appears only in the request example (`false`).

## Goals / Non-Goals

**Goals:** consent comes only from the reviewer; unticked means no claim; the preview shows exactly
what is sent.
**Non-Goals:** consent evidence, double opt-in, unsubscribe, tags, `wants_mailing`.

## Decisions

1. **Preferences are not part of `Contact`.** `Contact` is the extraction schema; adding booleans
   would let the model guess consent and would change the strict JSON schema sent to the model.
   They travel in a separate `preferences` object of the send request: `{newsletter, email, phone,
   post}`, all booleans defaulting to false. *Alternative:* extra `Contact` fields: simpler form
   code, but consent could be pre-filled and the draft would persist it.
2. **Only ticked options are sent.** Ticked newsletter: `wants_newsletter: true`. Ticked email,
   phone, post: `wants_no_email`, `wants_no_call`, `wants_no_post` set to `false`. Unticked: the
   key is absent, so FundraisingBox keeps its default (which reads as no consent). *Alternative:*
   always send all flags: would overwrite FundraisingBox defaults and could withdraw consent a
   person already has in the system on a retry of the same person.
3. **One mapping function.** `person_payload` takes the preferences and adds the keys; the same
   function builds the mock preview, so the preview cannot drift from the live body. Applies to the
   first record the send creates: the person, or the company for a company-only card.
4. **Form state, not draft state.** The checkboxes sit in the Communication section as a labelled
   group with their own `useState`, sent with the confirm call. The draft endpoint is unchanged, so a
   reload clears them: safer than persisting a consent choice the reviewer has not confirmed.
5. **Resume rule.** The flags belong to the person body, which is created once. A retry after a
   partial failure cannot change them, so the `partly_sent` message lists "the newsletter and
   contact options" with the name and company among the changes not applied.

## Risks / Trade-offs

- [Flag direction guessed from sparse docs] → first live send checked in FundraisingBox
  (workflow follow-up in tasks.md); the mapping is one small table, easy to flip.
- [`wants_newsletter` undocumented] → same live check; if rejected as an unknown field, the
  option is removed from the payload and the checkbox hidden until clarified.
- [A reload clears the choices] → they are one click each and reviewed at confirm time.
