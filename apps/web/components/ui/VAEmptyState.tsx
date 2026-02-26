import Link from "next/link";
import { VAButton } from "./VAButton";
import { VACard } from "./VACard";
import { NavIcon } from "./NavIcon";

interface VAEmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
  variant?: "empty" | "no-results";
  className?: string;
}

export function VAEmptyState({
  icon,
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
  variant = "empty",
  className = "",
}: VAEmptyStateProps) {
  const iconName = variant === "no-results" ? "search" : icon;

  return (
    <VACard className={`p-8 text-center ${className}`}>
      {iconName && (
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-va-surface">
          <NavIcon name={iconName} className="h-6 w-6 text-va-muted" />
        </div>
      )}
      <h3 className="text-lg font-medium text-va-text">{title}</h3>
      {description && (
        <p className="mx-auto mt-2 max-w-md text-sm text-va-text2">{description}</p>
      )}
      {actionLabel && actionHref && (
        <div className="mt-4">
          <Link href={actionHref}>
            <VAButton variant="primary">{actionLabel}</VAButton>
          </Link>
        </div>
      )}
      {actionLabel && onAction && !actionHref && (
        <div className="mt-4">
          <VAButton variant="primary" onClick={onAction}>{actionLabel}</VAButton>
        </div>
      )}
    </VACard>
  );
}
