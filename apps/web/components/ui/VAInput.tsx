"use client";

import type { InputHTMLAttributes } from "react";

interface VAInputProps extends InputHTMLAttributes<HTMLInputElement> {
  className?: string;
  error?: string;
}

export function VAInput({ className = "", error, ...props }: VAInputProps) {
  return (
    <div className="w-full">
      <input
        className={`w-full rounded-va-xs border ${error ? "border-va-danger" : "border-va-border"} bg-va-surface px-3 py-2 text-va-text placeholder:text-va-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-50 ${className}`}
        aria-invalid={error ? "true" : undefined}
        {...props}
      />
      {error && (
        <p className="mt-1 text-xs text-va-danger">{error}</p>
      )}
    </div>
  );
}
