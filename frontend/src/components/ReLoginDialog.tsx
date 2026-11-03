import { LoginForm } from "@/components/LoginForm";
import { Modal } from "@/components/Modal";
import { strings } from "@/strings";

/**
 * Shown over the page when the server ends a session. The page underneath stays mounted, so
 * whatever the user had typed is still there when they continue.
 */
export function ReLoginDialog() {
  return (
    <Modal open labelledBy="relogin-heading">
      <h2 id="relogin-heading" className="text-xl font-semibold">
        {strings.auth.expiredHeading}
      </h2>
      <p className="mb-4 mt-1 text-muted-foreground">{strings.auth.expiredText}</p>
      <LoginForm idPrefix="relogin" />
    </Modal>
  );
}
