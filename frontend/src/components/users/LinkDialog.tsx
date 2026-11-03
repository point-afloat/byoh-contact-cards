import { useState } from "react";
import type { InviteOut } from "@/api/types";
import { inputClass } from "@/components/LoginForm";
import { Modal } from "@/components/Modal";
import { Button } from "@/components/ui/button";
import { formatDate } from "@/screens/usersFormat";
import { strings } from "@/strings";

/** Shows a one-time link to the admin, with a copy button. The raw link is never shown again. */
export function LinkDialog({
  invite,
  kind,
  onClose,
}: {
  invite: InviteOut | null;
  kind: "invite" | "reset";
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const link = invite ? `${window.location.origin}${invite.invite_path}` : "";
  const email = invite?.user.email ?? "";
  const t = strings.users.linkDialog;

  async function copy() {
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      // No clipboard access: select the link so the person can copy it by hand.
      (document.getElementById("link-dialog-link") as HTMLInputElement | null)?.select();
    }
  }

  return (
    <Modal open={invite !== null} onClose={onClose} labelledBy="link-dialog-heading">
      {invite && (
        <div className="flex flex-col gap-4">
          <h2 id="link-dialog-heading" className="break-words text-xl font-semibold">
            {kind === "invite" ? t.inviteHeading(email) : t.resetHeading(email)}
          </h2>
          <p>{t.explanation(email, formatDate(invite.expires_at))}</p>
          <div className="flex flex-col gap-1">
            <label htmlFor="link-dialog-link" className="text-sm font-medium">
              {t.linkLabel}
            </label>
            <input
              id="link-dialog-link"
              readOnly
              value={link}
              className={inputClass}
              onFocus={(event) => event.target.select()}
            />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button onClick={copy}>{t.copy}</Button>
            <Button variant="outline" onClick={onClose}>
              {t.done}
            </Button>
            <p role="status" className="text-sm text-muted-foreground">
              {copied ? t.copied : ""}
            </p>
          </div>
        </div>
      )}
    </Modal>
  );
}
