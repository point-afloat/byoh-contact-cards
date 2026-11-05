# Design

## Context

Observed in the code: `FundraisingBoxClient` makes one call per record, to `persons.json` only
(`app/fundraisingbox/client.py`). `person_payload` builds the info text from email, phone, mobile,
address, website, notes and, when unlinked, the company (`app/fundraisingbox/mapping.py`). The send
flow (`app/send.py`) validates, optionally creates a company once (remembered on the session), then
creates the person and marks the session sent. `MockFundraisingBox` implements the same gateway and
returns the payload it was given. See proposal.md for why this changes.

From the FundraisingBox reference (persons-create, personAddresses-create, personPhones-create,
personEmailAddresses-create, personWebsites-create): a person body has no address, phone, email or
website fields. Each of those is its own `POST /v1/<resource>.json` with a required `fb_person_id`.
Limits: last name 100, first name 100, title 50, position 200, info 1000; address 300, post code
100, city 100, state 100, country a 2-letter code; phone 50; email 100; website url 1000. Types for
all four child records: `home`, `work`, `other`. Success is 201 with the new `id`; a failure is 400
with an empty body. The earlier importer design recorded the same facts and chose `info` to avoid a
half-created person; this change takes that risk on purpose and handles it (decision 3).

## Goals / Non-Goals

**Goals:**
- Real email, phone, address and website records in FundraisingBox.
- A send that can be resumed: no duplicate person, no silent loss of a detail.
- One place where the API's limits and enumerations live.

**Non-Goals:**
- Updating a person after it was created (the API has edit calls; the app only creates).
- Reading existing child records, duplicate detection, or a second address, email or website.
- A background queue: the send stays synchronous, the user sees the result.

## Decisions

1. **Sequential calls, person first.** Order: person, email, phone, mobile, address, website. Every
   child needs the person's id, so there is nothing to parallelise, and the order is the order of
   importance (an email matters more than a website if something fails). *Alternative:* one call
   with nested arrays: the person body does not accept them (the `fb_person_*` arrays appear only
   in responses).

2. **The gateway grows four methods.** `add_email`, `add_phone`, `add_address`, `add_website`, each
   taking the record id and the values and returning a `CreatedRecord` (with its payload in mock
   mode). `FundraisingBoxClient._call` takes the URL as an argument instead of using the persons URL
   constant, so the five create calls share the request, error and logging code. The mock builds
   the same payloads and applies the same limits. *Alternative:* a single `create_details` method
   that does all four: simpler for the caller, but it hides the step that failed, which the resume
   logic and the error message need.

3. **Resume state lives on the session.** The session keeps what was already created: the person
   (id and payload) and a map from step name (`email`, `phone`, `mobile`, `address`, `website`) to
   its payload. A send builds the list of steps from the contact, skips the ones already done and
   runs the rest. If a step fails, the person is kept, the session is not marked sent, and the user
   gets a `502` with code `partly_sent` whose message says the person exists and lists the missing
   details and the reason. The session is marked sent, and the image and contact discarded, only
   when every step succeeded. A retry after the user corrected a value sends the corrected value,
   because each step reads the current contact. This extends the existing "created company is
   remembered" mechanism. Changes the user makes to person-level fields (name, company choice) after
   the person exists are not applied, because there is no edit call; the message says so.
   *Alternative:* roll back (delete) the person on failure: the API has a delete call, but deleting
   from a failed request risks removing something the owner already worked on and needs yet another
   call that can fail.

4. **Local checks come first, as one list.** A function in `mapping.py` checks every documented
   limit and the email format and returns field name to message for all problems. The send raises
   one `validation_error` (the app's existing shape, with the `errors` map the form already
   highlights) before any request. The info text error moves into this list under the `notes`
   field, replacing the separate `info_too_long` code. Limits are constants next to the payload
   builders, so a limit changes in one place.

5. **Type and main flags.** Phone, email, address and website use `work` (a business card); the
   mobile number uses `other` because the documented create enum is `home`, `work`, `other` (the
   person-show page also lists `mobile`, but the create page does not). The first record of each
   kind is `is_main: true`. The mobile type is one constant, so it is a one-line change if the
   first live check shows that `mobile` is accepted. Website records also send `website_type:
   homepage`.

6. **Country codes from a built-in table.** A small table of German and English names for the
   countries a card is likely to show (DACH, neighbours, EU, UK, US and a few more), matched
   case-insensitively; a 2-letter value is accepted as is. Unknown text is not guessed: the address
   goes without a country and the text goes into `info`. *Alternative:* the `pycountry` library:
   complete, but a new dependency and megabytes for a field that is empty on most cards.

7. **Company-only cards attach details to the company.** The company record is the only record
   that exists, so the contact details belong to it. When a company is created for a person, the
   details stay with the person (they are the person's card details); the company record gets no
   details. The company's required `last_name` is the name cut to 100 characters; `company_name`
   is the full name (limit 1000, also checked).

8. **ContactPilot custom field as documented.** `{"id": 16786, "value": "Sync"}`: the id as a number
   and no `name`. The prototype sent the id as text with a name; the reference documents a number
   and a value only. The value `Sync` is what the integration reacts to and does not change.

9. **Mock preview shape.** In mock mode the session's `demo_payload` becomes
   `{"person": {...}, "emails": [...], "phones": [...], "addresses": [...], "websites": [...]}`
   (`"company"` instead of `"person"` for a company-only card, and only the lists that have
   entries). Child payloads show the `fb_person_id` the mock assigned. The done screen already
   prints the JSON it is given, so the frontend needs no new code, only updated tests.

## Risks / Trade-offs

- [A person exists without all its details after a failure] → clear `partly_sent` message, resume
  without duplicates, the contact stays open. The window is short, and the details are on screen.
- [More calls make a send slower] → five small requests; the existing 30 second timeout applies per
  call. Worth measuring on the first live send.
- [The custom field format change breaks the ContactPilot integration] → it is the documented
  format, but unverified against the account. The first live send is checked in FundraisingBox
  (workflow follow-up in tasks.md); `FundraisingBoxClient` logs only the status, never bodies.
- [`other` is a poor label for a mobile number] → documented, one constant, revisited after the
  first live check.
- [The country table misses a country] → the text is kept in `info`, so nothing is lost.
- [Specs overlap with the unarchived importer change] → see Migration plan.

## Migration Plan

1. No data migration: review sessions live in memory, so a restart drops any open one.
2. Reconcile before syncing specs: in `build-contact-card-importer`, the requirements "Field
   mapping" (custom field with id as text and a name) and "Contact channel data preserved" (values
   as info lines) are superseded by `fundraisingbox-record-schema`. Edit or remove them there so two
   specs do not describe different behaviour.
3. Deploy in mock mode first and look at the preview; check the first live send in FundraisingBox.
4. Roll back by redeploying the previous image. Records already created stay in FundraisingBox.
