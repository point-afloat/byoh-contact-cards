# Design

## Context

`LoginForm` renders email and password inputs and is used by the sign-in page and the re-login
dialog (`frontend/src/components/LoginForm.tsx`). The password field is a plain `type="password"` input.

## Goals / Non-Goals

**Goals:** a standard eye toggle on the sign-in form, accessible, no new dependency.
**Non-Goals:** other password fields, remembering the choice, changing throttling or the API.

## Decisions

1. **A button in the same wrapper as the input, toggling the input type.** The value stays in the
   same controlled input, so nothing is lost on toggle. *Alternative:* a second text input shown
   instead: duplicates state and focus handling.
2. **`aria-label` plus `aria-pressed`, icon hidden from assistive tech.** The name says what the
   next press does ("Show password" / "Hide password"). Icons come from `lucide-react`, already used.
3. **Hidden after a failed attempt.** The existing behaviour clears the field and refocuses it; the
   visibility choice is left as the person set it, so it does not hide text they are still checking.

## Risks / Trade-offs

- [Shoulder surfing when visible] → the field starts hidden every time the form is opened.
