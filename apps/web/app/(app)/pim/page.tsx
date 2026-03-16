import { VACard } from "@/components/ui";
import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import Link from "next/link";
import { redirect } from "next/navigation";

export default async function PimIndexPage() {
  const ctx = await getAuthContext();
  if (!ctx) redirect("/login");

  api.setAccessToken(ctx.accessToken);
  const peSummary = await api.pim.pe.summary(ctx.tenantId).catch(() => null);

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

        <Link href="/pim/economic">
          <VACard className="cursor-pointer p-6 transition-colors hover:border-va-blue/50">
            <div className="flex items-start gap-4">
              <span className="text-3xl" aria-hidden="true">
                🌐
              </span>
              <div>
                <h2 className="text-base font-medium text-va-text">
                  Economic Context
                </h2>
                <p className="mt-1 text-sm text-va-text2">
                  Macroeconomic regime classification and FRED indicator
                  dashboard. Monthly refresh.
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

        <Link href="/pim/backtest">
          <VACard className="cursor-pointer p-6 transition-colors hover:border-va-blue/50">
            <div className="flex items-start gap-4">
              <span className="text-3xl" aria-hidden="true">
                🔬
              </span>
              <div>
                <h2 className="text-base font-medium text-va-text">
                  Backtest Studio
                </h2>
                <p className="mt-1 text-sm text-va-text2">
                  Walk-forward backtest results with IC/ICIR signal quality
                  metrics and AI-generated performance commentary.
                </p>
              </div>
            </div>
          </VACard>
        </Link>

        <Link href="/pim/markov">
          <VACard className="cursor-pointer p-6 transition-colors hover:border-va-blue/50">
            <div className="flex items-start gap-4">
              <span className="text-3xl" aria-hidden="true">
                🔗
              </span>
              <div>
                <h2 className="text-base font-medium text-va-text">
                  Markov State Diagram
                </h2>
                <p className="mt-1 text-sm text-va-text2">
                  81-state Markov chain over GDP, sentiment, quality, and
                  momentum. Interactive steady-state visualisation.
                </p>
              </div>
            </div>
          </VACard>
        </Link>

        <Link href="/pim/pe">
          <VACard className="cursor-pointer p-6 transition-colors hover:border-va-blue/50">
            <div className="flex items-start gap-4">
              <span className="text-3xl" aria-hidden="true">
                💼
              </span>
              <div className="flex-1">
                <h2 className="text-base font-medium text-va-text">
                  PE Fund Assessments
                </h2>
                <p className="mt-1 text-sm text-va-text2">
                  DPI, TVPI, IRR, and J-curve analysis for private equity
                  funds. Peer comparison against vintage-year cohorts.
                </p>
                {peSummary && peSummary.total_assessments > 0 && (
                  <div className="mt-3 flex gap-4 text-xs text-va-text2">
                    <span>
                      <span className="font-mono text-va-text">
                        {peSummary.total_assessments}
                      </span>{" "}
                      fund{peSummary.total_assessments !== 1 ? "s" : ""}
                    </span>
                    {peSummary.avg_dpi !== null && (
                      <span>
                        Avg DPI{" "}
                        <span className="font-mono text-va-text">
                          {peSummary.avg_dpi.toFixed(2)}x
                        </span>
                      </span>
                    )}
                    {peSummary.avg_tvpi !== null && (
                      <span>
                        TVPI{" "}
                        <span className="font-mono text-va-text">
                          {peSummary.avg_tvpi.toFixed(2)}x
                        </span>
                      </span>
                    )}
                    {peSummary.avg_irr !== null && (
                      <span>
                        IRR{" "}
                        <span className="font-mono text-va-text">
                          {(peSummary.avg_irr * 100).toFixed(1)}%
                        </span>
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          </VACard>
        </Link>
      </div>
    </main>
  );
}
