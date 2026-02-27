"use client";

import type { ButtonHTMLAttributes } from "react";

interface VAButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
  className?: string;
}

export function VAButton({
  variant = "primary",
  loading = false,
  className = "",
  children,
  disabled,
  ...props
}: VAButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-va-sm px-4 py-2 text-sm font-medium cursor-pointer transition focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-50 disabled:cursor-not-allowed";
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
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg
          className="h-4 w-4 animate-spin motion-reduce:animate-none"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle
            className="opacity-25"
            cx="12"
            cy="12"
            r="10"
            stroke="currentColor"
            strokeWidth="4"
          />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
          />
        </svg>
      )}
      {children}
    </button>
  );
}
