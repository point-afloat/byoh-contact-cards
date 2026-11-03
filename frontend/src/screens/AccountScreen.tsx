import { type FormEvent, useEffect, useRef, useState } from "react";
import { api, ApiClientError } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";
import { inputClass } from "@/components/LoginForm";
import { ErrorAlert, Spinner } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { strings } from "@/strings";

type Field = "current" | "next" | "confirm";
const MIN_LENGTH = 12;

export function AccountScreen() {
  const { user } = useAuth();
  const [values, setValues] = useState<Record<Field, string>>({ current: "", next: "", confirm: "" });
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const inputs = {
    current: useRef<HTMLInputElement>(null),
    next: useRef<HTMLInputElement>(null),
    confirm: useRef<HTMLInputElement>(null),
  };

  const pendingFocus = useRef<Field | null>(null);

  // Move focus to the first field with a problem. Inputs are disabled while saving, and a
  // disabled input cannot take focus, so server-side problems wait until the form is enabled.
  useEffect(() => {
    if (!busy && pendingFocus.current) {
      inputs[pendingFocus.current].current?.focus();
      pendingFocus.current = null;
    }
  });

  function focusFirst(found: Partial<Record<Field, string>>) {
    const first = (["current", "next", "confirm"] as Field[]).find((field) => found[field]);
    if (first) pendingFocus.current = first;
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setDone(false);
    setFormError(null);

    const found: Partial<Record<Field, string>> = {};
    if (!values.current) found.current = strings.account.required;
    if (values.next.length < MIN_LENGTH) found.next = strings.account.tooShort;
    else if (values.confirm !== values.next) found.confirm = strings.account.mismatch;
    setErrors(found);
    if (Object.keys(found).length > 0) {
      focusFirst(found);
      return;
    }

    setBusy(true);
    try {
      await api.changePassword(values.current, values.next);
      setValues({ current: "", next: "", confirm: "" });
      setDone(true);
    } catch (failure) {
      if (failure instanceof ApiClientError) {
        const server: Partial<Record<Field, string>> = {
          current: failure.errors.current_password,
          next: failure.errors.new_password,
        };
        const fromServer = Object.fromEntries(Object.entries(server).filter(([, value]) => value));
        setErrors(fromServer);
        if (Object.keys(fromServer).length > 0) focusFirst(fromServer);
        else setFormError(failure.message);
      } else {
        setFormError(strings.genericError);
      }
    } finally {
      setBusy(false);
    }
  }

  function field(name: Field, label: string, autoComplete: string, hint?: string) {
    const id = `account-${name}`;
    const error = errors[name];
    const describedBy = [error && `${id}-error`, hint && `${id}-hint`].filter(Boolean).join(" ");
    return (
      <div className="flex flex-col gap-1">
        <label htmlFor={id} className="text-sm font-medium">
          {label}
        </label>
        <input
          ref={inputs[name]}
          id={id}
          type="password"
          autoComplete={autoComplete}
          value={values[name]}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy || undefined}
          onChange={(event) => setValues((previous) => ({ ...previous, [name]: event.target.value }))}
          className={inputClass}
        />
        {hint && (
          <p id={`${id}-hint`} className="text-sm text-muted-foreground">
            {hint}
          </p>
        )}
        {error && (
          <p id={`${id}-error`} role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <section aria-labelledby="account-heading" className="flex max-w-lg flex-col gap-6">
      <div>
        <h1 id="account-heading" className="text-xl font-semibold">
          {strings.account.heading}
        </h1>
        <dl className="mt-3 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
          <dt className="text-muted-foreground">{strings.account.emailLabel}</dt>
          <dd className="font-medium">{user?.email}</dd>
          <dt className="text-muted-foreground">{strings.account.roleLabel}</dt>
          <dd className="font-medium">{user ? (strings.account.roles[user.role] ?? user.role) : ""}</dd>
        </dl>
      </div>

      <form onSubmit={submit} noValidate aria-busy={busy} className="flex flex-col gap-4">
        <h2 className="text-lg font-semibold">{strings.account.changeHeading}</h2>
        {formError && <ErrorAlert>{formError}</ErrorAlert>}
        {done && (
          <p role="status" className="rounded-lg border border-border bg-muted px-4 py-3 text-sm">
            {strings.account.success}
          </p>
        )}
        <fieldset disabled={busy} className="flex flex-col gap-4">
          {field("current", strings.account.current, "current-password")}
          {field("next", strings.account.next, "new-password", strings.account.hint)}
          {field("confirm", strings.account.confirm, "new-password")}
          <Button type="submit" className="w-full sm:w-auto">
            {busy ? (
              <>
                <Spinner />
                {strings.account.saving}
              </>
            ) : (
              strings.account.submit
            )}
          </Button>
        </fieldset>
      </form>
    </section>
  );
}
