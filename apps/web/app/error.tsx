"use client";

import { VAButton, VACard } from "@/components/ui";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4">
      <VACard className="max-w-md p-6 text-center">
        <h2 className="text-lg font-semibold text-va-danger">
          Something went wrong
        </h2>
        <p className="mt-2 text-sm text-va-text2">
          {error.message || "An unexpected error occurred."}
        </p>
        <VAButton className="mt-4" onClick={reset}>
          Try again
        </VAButton>
      </VACard>
    </div>
  );
}
