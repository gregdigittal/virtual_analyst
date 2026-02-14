"use client";

import type { HTMLAttributes } from "react";

interface VABadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: "default" | "success" | "warning" | "danger" | "violet";
  className?: string;
}

export function VABadge({
  variant = "default",
  className = "",
  ...props
}: VABadgeProps) {
  const variants = {
    default: "bg-va-muted/20 text-va-text2 border border-va-border",
    success: "bg-va-success/15 text-va-success border border-va-success/40",
    warning: "bg-va-warning/15 text-va-warning border border-va-warning/40",
    danger: "bg-va-danger/15 text-va-danger border border-va-danger/40",
    violet: "bg-va-violet/15 text-va-violet border border-va-violet/40",
  };
  return (
    <span
      className={`inline-flex items-center rounded-va-xs px-2 py-0.5 text-xs font-medium ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
