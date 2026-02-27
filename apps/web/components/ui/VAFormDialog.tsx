"use client";

import { useEffect, useId, useState } from "react";
import { VAButton } from "./VAButton";
import { VAInput } from "./VAInput";
import { useFocusTrap } from "@/hooks/useFocusTrap";

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
  const instanceId = useId();
  const titleId = `${instanceId}-title`;
  const descId = `${instanceId}-desc`;
  const { ref, handleKeyDown } = useFocusTrap<HTMLFormElement>(open, onCancel, {
    initialFocus: "input",
  });

  useEffect(() => {
    if (open) setValues({});
  }, [open]);

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
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={description ? descId : undefined}
        onSubmit={handleSubmit}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={handleKeyDown}
        className="mx-4 w-full max-w-md rounded-va-lg border border-va-border bg-va-panel p-6 shadow-va-md"
      >
        <h3 id={titleId} className="text-lg font-semibold text-va-text">
          {title}
        </h3>
        {description && (
          <p id={descId} className="mt-2 text-sm text-va-text2">
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
          <VAButton type="submit" variant="primary" loading={loading}>
            {loading ? "Saving..." : submitLabel}
          </VAButton>
        </div>
      </form>
    </div>
  );
}
