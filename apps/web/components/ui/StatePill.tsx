"use client";

import type { HTMLAttributes } from "react";

type State = "draft" | "selected" | "committed";

interface StatePillProps extends HTMLAttributes<HTMLSpanElement> {
  state: State;
  className?: string;
}

export function StatePill({ state, className = "", ...props }: StatePillProps) {
  const styles: Record<State, string> = {
    draft: "border border-va-violet text-va-violet bg-transparent",
    selected: "bg-va-violet/15 text-va-violet border border-va-violet/40",
    committed: "bg-va-blue/15 text-va-blue border border-va-blue/40",
  };
  const labels: Record<State, string> = {
    draft: "Draft",
    selected: "Selected",
    committed: "Committed",
  };
  return (
    <span
      className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ${styles[state]} ${className}`}
      {...props}
    >
      {labels[state]}
    </span>
  );
}
