import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/** An error message announced to assistive technology as soon as it appears. */
export function ErrorAlert({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="alert"
      className={cn(
        "rounded-lg border border-destructive px-4 py-3 text-sm text-destructive",
        className,
      )}
      {...props}
    />
  );
}

export function Spinner({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn(
        "inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent",
        className,
      )}
    />
  );
}
