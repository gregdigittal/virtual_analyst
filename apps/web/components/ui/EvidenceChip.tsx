"use client";

import type { HTMLAttributes } from "react";

interface EvidenceChipProps extends HTMLAttributes<HTMLSpanElement> {
  source?: string;
  confidence?: "high" | "medium" | "low";
  className?: string;
}

export function EvidenceChip({
  source,
  confidence,
  className = "",
  children,
  ...props
}: EvidenceChipProps) {
  const confidenceClass =
    confidence === "high"
      ? "text-va-success border-va-success/40"
      : confidence === "medium"
        ? "text-va-warning border-va-warning/40"
        : "text-va-danger border-va-danger/40";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-va-xs border px-2 py-0.5 text-xs font-medium text-va-text2 ${confidenceClass} ${className}`}
      {...props}
    >
      {source && <span className="font-mono truncate max-w-[120px]">{source}</span>}
      {confidence && (
        <span className="capitalize opacity-90">{confidence}</span>
      )}
      {children}
    </span>
  );
}
