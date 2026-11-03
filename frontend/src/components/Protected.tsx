import { type ReactNode, useEffect } from "react";
import { useAuth } from "@/auth/AuthProvider";
import { ReLoginDialog } from "@/components/ReLoginDialog";
import { Spinner } from "@/components/ui/alert";
import { navigate } from "@/router";
import { strings } from "@/strings";

/**
 * Route guard. Never signed in: go to the sign-in page. Signed in until the server ended the
 * session: keep the page and ask for the password in a dialog. `admin` pages send members home.
 */
export function Protected({ children, admin = false }: { children: ReactNode; admin?: boolean }) {
  const { status, user, expired } = useAuth();
  const notAllowed = status === "authenticated" && admin && user?.role !== "admin";

  useEffect(() => {
    if (status === "anonymous" && !expired) navigate("/login", true);
    if (notAllowed) navigate("/", true);
  }, [status, expired, notAllowed]);

  if (status === "loading") {
    return (
      <p role="status" className="flex items-center gap-3 p-8">
        <Spinner />
        {strings.auth.loading}
      </p>
    );
  }
  if (status === "anonymous") return expired ? <>{children}<ReLoginDialog /></> : null;
  if (notAllowed) return null;
  return <>{children}</>;
}
