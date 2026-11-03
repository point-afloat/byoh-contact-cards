import type { ReactNode } from "react";
import { useAuth } from "@/auth/AuthProvider";
import { Button } from "@/components/ui/button";
import { Link, navigate, usePath } from "@/router";
import { strings } from "@/strings";
import { cn } from "@/lib/utils";

function NavLink({ to, children }: { to: string; children: ReactNode }) {
  const current = usePath() === to;
  return (
    <Link
      to={to}
      aria-current={current ? "page" : undefined}
      className={cn(
        "inline-flex min-h-11 items-center rounded-lg px-3 font-medium hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring",
        current && "bg-muted",
      )}
    >
      {children}
    </Link>
  );
}

/** The frame around every page that needs a signed-in user: title, navigation and sign-out. */
export function AppLayout({ children }: { children: ReactNode }) {
  const { user, signOut } = useAuth();

  async function handleSignOut() {
    try {
      await signOut();
    } finally {
      navigate("/login", true);
    }
  }

  return (
    <div className="mx-auto flex min-h-dvh max-w-5xl flex-col gap-6 px-4 py-6">
      <header className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-2xl font-semibold">{strings.appTitle}</p>
            <p className="text-muted-foreground">{strings.appTagline}</p>
          </div>
          {user && (
            <p className="text-sm text-muted-foreground">
              {strings.nav.signedInAs} <span className="font-medium text-foreground">{user.email}</span>
            </p>
          )}
        </div>
        {user && (
          <nav aria-label={strings.nav.mainLabel} className="flex flex-wrap items-center gap-1">
            <NavLink to="/">{strings.nav.scan}</NavLink>
            {user.role === "admin" && <NavLink to="/admin/users">{strings.nav.users}</NavLink>}
            <NavLink to="/account">{strings.nav.account}</NavLink>
            <Button variant="ghost" onClick={handleSignOut}>
              {strings.nav.signOut}
            </Button>
          </nav>
        )}
      </header>
      <main className="flex-1">{children}</main>
    </div>
  );
}
