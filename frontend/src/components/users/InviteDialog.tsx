import { type FormEvent, useState } from "react";
import { api, ApiClientError } from "@/api/client";
import type { InviteOut } from "@/api/types";
import { inputClass } from "@/components/LoginForm";
import { Modal } from "@/components/Modal";
import { ErrorAlert, Spinner } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { strings } from "@/strings";

export function InviteDialog({
  open,
  onClose,
  onInvited,
}: {
  open: boolean;
  onClose: () => void;
  onInvited: (invite: InviteOut) => void;
}) {
  const t = strings.users.inviteDialog;
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("member");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setFormError(null);
    setFieldErrors({});
    try {
      onInvited(await api.inviteUser(email, role));
    } catch (failure) {
      if (failure instanceof ApiClientError && Object.keys(failure.errors).length > 0) {
        setFieldErrors(failure.errors);
      } else {
        setFormError(failure instanceof ApiClientError ? failure.message : strings.genericError);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal open={open} onClose={onClose} labelledBy="invite-dialog-heading">
      <form onSubmit={submit} noValidate aria-busy={busy} className="flex flex-col gap-4">
        <h2 id="invite-dialog-heading" className="text-xl font-semibold">
          {t.heading}
        </h2>
        {formError && <ErrorAlert>{formError}</ErrorAlert>}
        <fieldset disabled={busy} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="invite-email" className="text-sm font-medium">
              {t.email}
            </label>
            <input
              id="invite-email"
              type="email"
              autoComplete="off"
              value={email}
              aria-invalid={fieldErrors.email ? true : undefined}
              aria-describedby={fieldErrors.email ? "invite-email-error" : undefined}
              onChange={(event) => setEmail(event.target.value)}
              className={inputClass}
            />
            {fieldErrors.email && (
              <p id="invite-email-error" role="alert" className="text-sm text-destructive">
                {fieldErrors.email}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="invite-role" className="text-sm font-medium">
              {t.role}
            </label>
            <select
              id="invite-role"
              value={role}
              onChange={(event) => setRole(event.target.value)}
              className={inputClass}
            >
              <option value="member">{strings.users.roles.member}</option>
              <option value="admin">{strings.users.roles.admin}</option>
            </select>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button type="submit">
              {busy ? (
                <>
                  <Spinner />
                  {t.saving}
                </>
              ) : (
                t.submit
              )}
            </Button>
            <Button variant="outline" onClick={onClose}>
              {t.cancel}
            </Button>
          </div>
        </fieldset>
      </form>
    </Modal>
  );
}
