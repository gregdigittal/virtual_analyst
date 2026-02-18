import { VACard } from "@/components/ui";
import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center px-4">
      <VACard className="max-w-md p-6 text-center">
        <h2 className="text-lg font-semibold text-va-text">Page not found</h2>
        <p className="mt-2 text-sm text-va-text2">
          The page you&apos;re looking for doesn&apos;t exist or has been moved.
        </p>
        <Link
          href="/baselines"
          className="mt-4 inline-block rounded-va-xs bg-va-blue px-4 py-2 text-sm font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
        >
          Go to Baselines
        </Link>
      </VACard>
    </div>
  );
}
