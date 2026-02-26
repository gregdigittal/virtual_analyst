import Link from "next/link";

interface SoftGateBannerProps {
  message: string;
  actionLabel: string;
  actionHref: string;
}

export function SoftGateBanner({ message, actionLabel, actionHref }: SoftGateBannerProps) {
  return (
    <div role="alert" className="mb-6 flex items-center justify-between rounded-va-sm border border-va-warning/40 bg-va-warning/10 px-4 py-3">
      <span className="text-sm text-va-warning">{message}</span>
      <Link
        href={actionHref}
        className="rounded-va-xs bg-va-warning/20 px-3 py-1 text-sm font-medium text-va-warning hover:bg-va-warning/30"
      >
        {actionLabel} →
      </Link>
    </div>
  );
}
