"use client";

import type { InputHTMLAttributes } from "react";

interface VAInputProps extends InputHTMLAttributes<HTMLInputElement> {
  className?: string;
}

export function VAInput({ className = "", ...props }: VAInputProps) {
  return (
    <input
      className={`w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-va-text placeholder:text-va-muted focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-50 ${className}`}
      {...props}
    />
  );
}
