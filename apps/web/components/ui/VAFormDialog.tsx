"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { VAButton } from "./VAButton";
import { VAInput } from "./VAInput";

interface FormField {
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
}

interface VAFormDialogProps {
  open: boolean;
  title: string;
  description?: string;
  fields: FormField[];
  onSubmit: (values: Record<string, string>) => void;
  onCancel: () => void;
  submitLabel?: string;
  loading?: boolean;
}

export function VAFormDialog({
  open,
  title,
  description,
  fields,
  onSubmit,
  onCancel,
  submitLabel = "Submit",
  loading = false,
}: VAFormDialogProps) {
  const [values, setValues] = useState<Record<string, string>>({});
  const formRef = useRef<HTMLFormElement>(null);
  const previousFocusRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (open) {
      setValues({});
      previousFocusRef.current = document.activeElement as HTMLElement;
      // Focus first input on open
      requestAnimationFrame(() => {
        const firstInput = formRef.current?.querySelector<HTMLElement>("input");
        firstInput?.focus();
      });
    } else if (previousFocusRef.current) {
      previousFocusRef.current.focus();
      previousFocusRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  // Focus trap
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key !== "Tab" || !formRef.current) return;
      const focusable = formRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    },
    [],
  );

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(values);
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onCancel}
    >
      <form
        ref={formRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="va-form-title"
        aria-describedby={description ? "va-form-desc" : undefined}
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
        className="mx-4 w-full max-w-md rounded-va-lg border border-va-border bg-va-panel p-6 shadow-va-md"
      >
        <h3 id="va-form-title" className="text-lg font-semibold text-va-text">
          {title}
        </h3>
        {description && (
          <p id="va-form-desc" className="mt-2 text-sm text-va-text2">
            {description}
          </p>
        )}
        <div className="mt-4 space-y-3">
          {fields.map((field) => (
            <div key={field.name}>
              <label
                htmlFor={`form-${field.name}`}
                className="mb-1 block text-sm font-medium text-va-text"
              >
                {field.label}
              </label>
              <VAInput
                id={`form-${field.name}`}
                value={values[field.name] ?? ""}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                }
                placeholder={field.placeholder}
                required={field.required}
              />
            </div>
          ))}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <VAButton type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </VAButton>
          <VAButton type="submit" variant="primary" disabled={loading}>
            {loading ? "Saving..." : submitLabel}
          </VAButton>
        </div>
      </form>
    </div>
  );
}
