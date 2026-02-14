"use client";

import type { HTMLAttributes } from "react";

interface VACardProps extends HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export function VACard({ className = "", ...props }: VACardProps) {
  return (
    <div
      className={`rounded-va-lg border border-va-border bg-va-panel/80 ${className}`}
      {...props}
    />
  );
}
