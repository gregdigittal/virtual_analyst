"use client";

import { useEffect } from "react";
import { VAButton } from "./VAButton";

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
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-md rounded-va-lg border border-va-border bg-va-panel p-6 shadow-va-md">
        <h3 className="text-lg font-semibold text-va-text">{title}</h3>
        {description && (
          <p className="mt-2 text-sm text-va-text2">{description}</p>
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
