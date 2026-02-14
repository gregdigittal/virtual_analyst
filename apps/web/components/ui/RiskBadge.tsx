"use client";

import type { HTMLAttributes } from "react";

type RiskLevel = "low" | "medium" | "high";

interface RiskBadgeProps extends HTMLAttributes<HTMLSpanElement> {
  level: RiskLevel;
  className?: string;
}

export function RiskBadge({
  level,
  className = "",
  ...props
}: RiskBadgeProps) {
  const styles: Record<RiskLevel, string> = {
    low: "bg-va-success/15 text-va-success border-va-success/40",
    medium: "bg-va-warning/15 text-va-warning border-va-warning/40",
    high: "bg-va-danger/15 text-va-magenta border-va-danger/40",
  };
  return (
    <span
      className={`inline-flex items-center rounded-va-xs border px-2 py-0.5 text-xs font-medium capitalize ${styles[level]} ${className}`}
      {...props}
    >
      {level}
    </span>
  );
}
