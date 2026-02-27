"use client";

import { useId } from "react";
import { VAButton } from "./VAButton";
import { useFocusTrap } from "@/hooks/useFocusTrap";

interface VAConfirmDialogProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  variant?: "danger" | "warning";
}

export function VAConfirmDialog({
  open,
  onConfirm,
  onCancel,
  title,
  description,
  confirmLabel = "Delete",
  variant = "danger",
}: VAConfirmDialogProps) {
  const instanceId = useId();
  const titleId = `${instanceId}-title`;
  const descId = `${instanceId}-desc`;
  const { ref, handleKeyDown } = useFocusTrap<HTMLDivElement>(open, onCancel);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onCancel}
    >
      <div
        ref={ref}
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
        className="mx-4 w-full max-w-md rounded-va-lg border border-va-border bg-va-panel p-6 shadow-va-md focus:outline-none"
      >
        <h3 id={titleId} className="text-lg font-semibold text-va-text">
          {title}
        </h3>
        {description && (
          <p id={descId} className="mt-2 text-sm text-va-text2">
            {description}
          </p>
        )}
        <div className="mt-6 flex justify-end gap-3">
          <VAButton variant="secondary" onClick={onCancel}>
            Cancel
          </VAButton>
          <VAButton
            variant={variant === "danger" ? "danger" : "primary"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </VAButton>
        </div>
      </div>
    </div>
  );
}
