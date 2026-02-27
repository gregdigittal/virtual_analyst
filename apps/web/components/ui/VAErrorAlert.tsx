"use client";

import { VAButton } from "./VAButton";

interface VAErrorAlertProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export function VAErrorAlert({ message, onRetry, className = "" }: VAErrorAlertProps) {
  return (
    <div
      className={`flex items-center justify-between gap-3 rounded-va-sm border border-va-danger/50 bg-va-danger/10 px-4 py-3 text-sm text-va-danger ${className}`}
      role="alert"
    >
      <span>{message}</span>
      {onRetry && (
        <VAButton variant="danger" className="flex-shrink-0 text-xs px-3 py-1" onClick={onRetry}>
          Retry
        </VAButton>
      )}
    </div>
  );
}
