import { Button } from "./Button";
import { Modal } from "./Modal";

export function ConfirmDialog({
  open,
  title,
  message,
  confirmText = "确认删除",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal open={open} title={title} onClose={onCancel} width="max-w-sm">
      <p className="text-sm text-slate-600">{message}</p>
      <div className="mt-6 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onCancel}>
          取消
        </Button>
        <Button variant="danger" size="sm" onClick={onConfirm}>
          {confirmText}
        </Button>
      </div>
    </Modal>
  );
}
