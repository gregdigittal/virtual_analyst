import { VACard } from "@/components/ui";
import { getAuthContext } from "@/lib/auth";
import Link from "next/link";
import { redirect } from "next/navigation";

export default async function PimIndexPage() {
  const ctx = await getAuthContext();
  if (!ctx) redirect("/login");

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Page header */}
      <div className="mb-8">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Portfolio Intelligence
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          AI-powered investment analysis and sentiment monitoring.
        </p>
      </div>

      {/* Navigation cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Link href="/pim/universe">
          <VACard className="cursor-pointer p-6 transition-colors hover:border-va-blue/50">
            <div className="flex items-start gap-4">
              <span className="text-3xl" aria-hidden="true">
                🏢
              </span>
              <div>
                <h2 className="text-base font-medium text-va-text">
                  Universe Manager
                </h2>
                <p className="mt-1 text-sm text-va-text2">
                  Manage your investable company universe. Add tickers, set
                  sectors, and track your coverage.
                </p>
              </div>
            </div>
          </VACard>
        </Link>

        <Link href="/pim/sentiment">
          <VACard className="cursor-pointer p-6 transition-colors hover:border-va-blue/50">
            <div className="flex items-start gap-4">
              <span className="text-3xl" aria-hidden="true">
                📊
              </span>
              <div>
                <h2 className="text-base font-medium text-va-text">
                  Sentiment Monitor
                </h2>
                <p className="mt-1 text-sm text-va-text2">
                  Track news sentiment across your portfolio. Powered by
                  Polygon.io news and Claude AI.
                </p>
              </div>
            </div>
          </VACard>
        </Link>
      </div>
    </main>
  );
}
