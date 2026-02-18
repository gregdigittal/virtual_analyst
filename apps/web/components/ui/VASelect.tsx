"use client";

import type { SelectHTMLAttributes } from "react";

interface VASelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  className?: string;
}

export function VASelect({ className = "", ...props }: VASelectProps) {
  return (
    <select
      className={`w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-50 ${className}`}
      {...props}
    />
  );
}
