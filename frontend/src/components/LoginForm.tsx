import { Eye, EyeOff } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";
import { ApiClientError } from "@/api/client";
import { useAuth } from "@/auth/AuthProvider";
import { ErrorAlert, Spinner } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { strings } from "@/strings";

export const inputClass =
  "min-h-11 w-full rounded-lg border border-border bg-background px-3 text-base focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring aria-[invalid=true]:border-destructive";

/** Email and password. Errors come from the server and never say which of the two was wrong. */
export function LoginForm({
  onSignedIn,
  idPrefix = "login",
}: {
  onSignedIn?: () => void;
  idPrefix?: string;
}) {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const passwordInput = useRef<HTMLInputElement>(null);
  const refocusPassword = useRef(false);

  // A disabled input cannot take focus, so wait until the form is enabled again.
  useEffect(() => {
    if (!busy && refocusPassword.current) {
      refocusPassword.current = false;
      passwordInput.current?.focus();
    }
  }, [busy]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
      onSignedIn?.();
    } catch (failure) {
      setError(
        failure instanceof ApiClientError
          ? failure.message
          : strings.genericError,
      );
      setPassword("");
      refocusPassword.current = true;
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-4" aria-busy={busy}>
      {error && <ErrorAlert>{error}</ErrorAlert>}
      <fieldset disabled={busy} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1">
          <label htmlFor={`${idPrefix}-email`} className="text-sm font-medium">
            {strings.auth.email}
          </label>
          <input
            id={`${idPrefix}-email`}
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className={inputClass}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label
            htmlFor={`${idPrefix}-password`}
            className="text-sm font-medium"
          >
            {strings.auth.password}
          </label>
          <div className="relative">
            <input
              ref={passwordInput}
              id={`${idPrefix}-password`}
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className={`${inputClass} pr-12`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((shown) => !shown)}
              aria-pressed={showPassword}
              aria-label={
                showPassword
                  ? strings.auth.hidePassword
                  : strings.auth.showPassword
              }
              className="absolute inset-y-0 right-0 flex min-w-11 items-center justify-center rounded-r-lg text-muted-foreground hover:text-foreground focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-ring"
            >
              {showPassword ? (
                <EyeOff aria-hidden="true" size={20} />
              ) : (
                <Eye aria-hidden="true" size={20} />
              )}
            </button>
          </div>
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? (
            <>
              <Spinner />
              {strings.auth.signingIn}
            </>
          ) : (
            strings.auth.signIn
          )}
        </Button>
      </fieldset>
    </form>
  );
}
