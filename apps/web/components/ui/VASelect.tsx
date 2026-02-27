"use client";

import { useId, type SelectHTMLAttributes } from "react";

interface VASelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  className?: string;
  error?: string;
}

export function VASelect({ className = "", error, children, id, ...props }: VASelectProps) {
  const generatedId = useId();
  const selectId = id ?? generatedId;
  const errorId = error ? `${selectId}-error` : undefined;
  return (
    <div className="w-full">
      <select
        id={selectId}
        className={`w-full rounded-va-xs border ${error ? "border-va-danger" : "border-va-border"} bg-va-surface px-3 py-2 text-sm text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-50 ${className}`}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={errorId}
        {...props}
      >
        {children}
      </select>
      {error && (
        <p id={errorId} className="mt-1 text-xs text-va-danger" role="alert">{error}</p>
      )}
    </div>
  );
}
