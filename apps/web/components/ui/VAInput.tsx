"use client";

import type { InputHTMLAttributes } from "react";

interface VAInputProps extends InputHTMLAttributes<HTMLInputElement> {
  className?: string;
  error?: string;
}

export function VAInput({ className = "", error, id, ...props }: VAInputProps) {
  const errorId = error && id ? `${id}-error` : undefined;
  return (
    <div className="w-full">
      <input
        id={id}
        className={`w-full rounded-va-xs border ${error ? "border-va-danger" : "border-va-border"} bg-va-surface px-3 py-2 text-va-text placeholder:text-va-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-50 ${className}`}
        aria-invalid={error ? "true" : undefined}
        aria-describedby={errorId}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-1 text-xs text-va-danger" role="alert">{error}</p>
      )}
    </div>
  );
}
