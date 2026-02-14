"use client";

import type { ButtonHTMLAttributes } from "react";

interface VAButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  className?: string;
}

export function VAButton({
  variant = "primary",
  className = "",
  ...props
}: VAButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-va-sm px-4 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-50";
  const variants = {
    primary:
      "bg-va-blue text-va-text hover:bg-va-blue/90 shadow-va-glow-blue",
    secondary:
      "border border-va-border bg-transparent text-va-text hover:bg-white/5",
    ghost: "bg-transparent text-va-text2 hover:bg-white/5",
    danger: "bg-va-danger text-va-text hover:bg-va-danger/90",
  };
  return (
    <button
      type="button"
      className={`${base} ${variants[variant]} ${className}`}
      {...props}
    />
  );
}
