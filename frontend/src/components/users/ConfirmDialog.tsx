import { Modal } from "@/components/Modal";
import { Button } from "@/components/ui/button";
import { strings } from "@/strings";

export function ConfirmDialog({
  open,
  heading,
  text,
  confirmLabel,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  heading: string;
  text: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} onClose={onCancel} labelledBy="confirm-heading">
      <div className="flex flex-col gap-4">
        <h2 id="confirm-heading" className="break-words text-xl font-semibold">
          {heading}
        </h2>
        <p>{text}</p>
        <div className="flex flex-wrap gap-3">
          <Button onClick={onConfirm}>{confirmLabel}</Button>
          <Button variant="outline" onClick={onCancel}>
            {strings.users.confirm.cancel}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
