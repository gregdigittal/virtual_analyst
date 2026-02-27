"use client";

interface VASkeletonProps {
  className?: string;
}

export function VASkeleton({ className = "" }: VASkeletonProps) {
  return (
    <div
      className={`animate-pulse motion-reduce:animate-none rounded-va-xs bg-va-border/50 ${className}`}
      aria-hidden="true"
    />
  );
}

export function VACardSkeleton({ className = "" }: VASkeletonProps) {
  return (
    <div
      className={`rounded-va-lg border border-va-border bg-va-panel/80 p-4 ${className}`}
      aria-hidden="true"
    >
      <div className="flex items-center justify-between">
        <VASkeleton className="h-4 w-2/5" />
        <VASkeleton className="h-5 w-16 rounded-full" />
      </div>
      <VASkeleton className="mt-3 h-3 w-3/4" />
      <VASkeleton className="mt-2 h-3 w-1/2" />
    </div>
  );
}

export function VAListSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label="Loading">
      {Array.from({ length: count }).map((_, i) => (
        <VACardSkeleton key={i} />
      ))}
      <span className="sr-only">Loading...</span>
    </div>
  );
}
