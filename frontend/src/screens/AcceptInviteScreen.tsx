import { useQuery } from "@tanstack/react-query";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { api, ApiClientError } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";
import { inputClass } from "@/components/LoginForm";
import { PublicLayout } from "@/components/PublicLayout";
import { ErrorAlert, Spinner } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Link, navigate } from "@/router";
import { strings } from "@/strings";

const MIN_LENGTH = 12;

/** The token travels in the URL fragment (#token=...), which browsers never send to a server. */
function tokenFromUrl(): string {
  return new URLSearchParams(window.location.hash.replace(/^#/, "")).get("token") ?? "";
}

type Field = "password" | "confirm";

export function AcceptInviteScreen() {
  const [token] = useState(tokenFromUrl);
  const { setUser } = useAuth();
  const info = useQuery({
    queryKey: ["invite-info", token],
    queryFn: () => api.inviteInfo(token),
    enabled: token !== "",
    retry: false,
    staleTime: Infinity,
  });
  const [usedUp, setUsedUp] = useState(false); // the link stopped working while the form was open

  const invalid =
    token === "" ||
    usedUp ||
    (info.error instanceof ApiClientError && info.error.status >= 400 && info.error.status < 500);
  const broken = info.isError && !invalid; // could not ask the server (network, server error)

  const heading = useRef<HTMLHeadingElement>(null);
  const state = invalid ? "invalid" : broken ? "broken" : info.data ? "ready" : "loading";
  useEffect(() => {
    if (state !== "loading") heading.current?.focus();
  }, [state]);

  return (
    <PublicLayout>
      {state === "loading" && (
        <p role="status" className="flex items-center gap-3">
          <Spinner />
          {strings.invite.checking}
        </p>
      )}
      {state === "invalid" && (
        <div className="flex flex-col gap-3">
          <h1 ref={heading} tabIndex={-1} className="text-xl font-semibold outline-none">
            {strings.invite.invalidHeading}
          </h1>
          <p>{strings.invite.invalidText}</p>
          <Link to="/login" className="font-medium text-primary underline">
            {strings.invite.toSignIn}
          </Link>
        </div>
      )}
      {state === "broken" && (
        <div className="flex flex-col gap-3">
          <h1 ref={heading} tabIndex={-1} className="text-xl font-semibold outline-none">
            {strings.invite.checking}
          </h1>
          <ErrorAlert>{info.error instanceof ApiClientError ? info.error.message : strings.genericError}</ErrorAlert>
          <Button onClick={() => void info.refetch()}>{strings.invite.retry}</Button>
        </div>
      )}
      {state === "ready" && info.data && (
        <AcceptForm
          token={token}
          email={info.data.email}
          kind={info.data.kind}
          headingRef={heading}
          onSignedIn={(user) => {
            setUser(user);
            navigate("/"); // also drops the token from the address bar
          }}
          onUsedUp={() => setUsedUp(true)}
        />
      )}
    </PublicLayout>
  );
}

type FormProps = {
  token: string;
  email: string;
  kind: string;
  headingRef: React.RefObject<HTMLHeadingElement | null>;
  onSignedIn: (user: { id: number; email: string; role: string }) => void;
  onUsedUp: () => void;
};

function AcceptForm({ token, email, kind, headingRef, onSignedIn, onUsedUp }: FormProps) {
  const [values, setValues] = useState<Record<Field, string>>({ password: "", confirm: "" });
  const [errors, setErrors] = useState<Partial<Record<Field, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const inputs = { password: useRef<HTMLInputElement>(null), confirm: useRef<HTMLInputElement>(null) };
  const pendingFocus = useRef<Field | null>(null);
  const isReset = kind === "reset";

  // Inputs are disabled while saving and a disabled input cannot take focus: wait until enabled.
  useEffect(() => {
    if (!busy && pendingFocus.current) {
      inputs[pendingFocus.current].current?.focus();
      pendingFocus.current = null;
    }
  });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setFormError(null);
    const found: Partial<Record<Field, string>> = {};
    if (values.password.length < MIN_LENGTH) found.password = strings.invite.tooShort;
    else if (values.confirm !== values.password) found.confirm = strings.invite.mismatch;
    setErrors(found);
    if (found.password || found.confirm) {
      pendingFocus.current = found.password ? "password" : "confirm";
      inputs[pendingFocus.current].current?.focus();
      return;
    }

    setBusy(true);
    try {
      onSignedIn(await api.acceptInvite(token, values.password));
    } catch (failure) {
      if (failure instanceof ApiClientError && failure.code === "invite_invalid") {
        onUsedUp();
      } else if (failure instanceof ApiClientError && failure.errors.password) {
        setErrors({ password: failure.errors.password });
        pendingFocus.current = "password";
      } else {
        setFormError(failure instanceof ApiClientError ? failure.message : strings.genericError);
      }
    } finally {
      setBusy(false);
    }
  }

  function field(name: Field, label: string, hint?: string) {
    const id = `invite-${name}`;
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
          autoComplete="new-password"
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
    <form onSubmit={submit} noValidate aria-busy={busy} className="flex flex-col gap-4">
      <div>
        <h1 ref={headingRef} tabIndex={-1} className="text-xl font-semibold outline-none">
          {isReset ? strings.invite.resetHeading : strings.invite.welcomeHeading}
        </h1>
        <p className="text-muted-foreground">
          {strings.invite.forEmail} <span className="font-medium text-foreground">{email}</span>
        </p>
      </div>
      {formError && <ErrorAlert>{formError}</ErrorAlert>}
      <fieldset disabled={busy} className="flex flex-col gap-4">
        {/* Password managers use the email to file the new password under the right account. */}
        <input type="email" autoComplete="username" value={email} readOnly hidden aria-hidden="true" />
        {field("password", strings.invite.password, strings.invite.hint)}
        {field("confirm", strings.invite.confirm)}
        <Button type="submit">
          {busy ? (
            <>
              <Spinner />
              {strings.invite.saving}
            </>
          ) : isReset ? (
            strings.invite.submitReset
          ) : (
            strings.invite.submitInvite
          )}
        </Button>
      </fieldset>
    </form>
  );
}
