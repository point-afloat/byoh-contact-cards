# Proposal

## Why

Typing a long password on a phone with the text hidden invites typos, and a wrong password
costs a throttled attempt. A show/hide control, as on most sign-in forms, lets people check what
they typed before sending it.

## What Changes

- The sign-in form gets an eye button at the end of the password field that switches the field
  between hidden and visible text.
- The control is a labelled, keyboard-operable button that announces its state.
- Applies to the sign-in form only, which the re-login dialog reuses.

## Capabilities

### New Capabilities
- `sign-in-password-visibility`: how a person can reveal and hide the password they type on the
  sign-in form.

### Modified Capabilities
<!-- None: openspec/specs is empty. -->

## Impact

- Frontend only: `frontend/src/components/LoginForm.tsx`, `frontend/src/strings.ts`,
  `frontend/src/screens/LoginScreen.test.tsx`. No API, data or dependency change (the icon library
  was already in use).
- Visible text is never stored or sent anywhere new; the field value is the same as before.

## Assumptions

- The change was made directly and is recorded here afterwards.
- The change-password and invite screens keep their hidden fields; they can adopt the control later.
