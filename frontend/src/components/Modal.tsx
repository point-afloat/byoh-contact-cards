import { type ReactNode, useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

type Props = {
  open: boolean;
  /** Called when the user dismisses the dialog (Escape or the backdrop). Omit to make it required. */
  onClose?: () => void;
  labelledBy: string;
  children: ReactNode;
  className?: string;
};

/**
 * A native <dialog>: the browser traps focus, makes the page behind inert and restores focus on
 * close. Without `onClose` it cannot be dismissed, only completed.
 */
export function Modal({ open, onClose, labelledBy, children, className }: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={labelledBy}
      onCancel={(event) => {
        event.preventDefault(); // Escape: let our own state decide
        onClose?.();
      }}
      className={cn(
        "m-auto w-[min(32rem,calc(100vw-2rem))] rounded-xl border border-border bg-background p-6 text-foreground backdrop:bg-black/50",
        className,
      )}
    >
      {open ? children : null}
    </dialog>
  );
}
