"use client";

interface VAPaginationProps {
  page: number;
  pageSize: number;
  total?: number;
  hasMore?: boolean;
  onPageChange: (page: number) => void;
  className?: string;
}

export function VAPagination({
  page,
  pageSize,
  total,
  hasMore,
  onPageChange,
  className = "",
}: VAPaginationProps) {
  const totalPages = total != null ? Math.ceil(total / pageSize) : undefined;
  const canPrev = page > 1;
  const canNext =
    totalPages != null ? page < totalPages : (hasMore ?? false);

  if (totalPages != null && totalPages <= 1) return null;
  if (totalPages == null && !canPrev && !canNext) return null;

  const btnBase =
    "inline-flex items-center justify-center rounded-va-sm px-3 py-1.5 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight disabled:opacity-40 disabled:cursor-not-allowed";
  const btnStyle =
    "border border-va-border bg-transparent text-va-text hover:bg-white/5";

  return (
    <div
      className={`flex items-center justify-between gap-4 pt-4 ${className}`}
    >
      <button
        type="button"
        disabled={!canPrev}
        onClick={() => onPageChange(page - 1)}
        className={`${btnBase} ${btnStyle}`}
      >
        &larr; Prev
      </button>
      <span className="text-sm text-va-text2">
        {total != null
          ? `Page ${page} of ${totalPages} (${total} items)`
          : `Page ${page}`}
      </span>
      <button
        type="button"
        disabled={!canNext}
        onClick={() => onPageChange(page + 1)}
        className={`${btnBase} ${btnStyle}`}
      >
        Next &rarr;
      </button>
    </div>
  );
}
