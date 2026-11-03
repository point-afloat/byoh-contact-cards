import type { ReactNode } from "react";
import { strings } from "@/strings";

/** Layout for pages people can see without signing in (sign in, accepting an invitation). */
export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-8">
      <p className="text-center text-lg font-semibold">{strings.appTitle}</p>
      <main className="rounded-xl border border-border p-6">{children}</main>
    </div>
  );
}
