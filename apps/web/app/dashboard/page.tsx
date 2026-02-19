"use client";

import {
  api,
  type BudgetDashboardWidget,
  type KpiItem,
  type ActivityItem,
} from "@/lib/api";
import { VAButton, VACard, VABadge, VASpinner } from "@/components/ui";
import { Nav } from "@/components/nav";
import { createClient } from "@/lib/supabase/client";
import { formatDateTime } from "@/lib/format";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function fmtNum(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "\u2014";
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "\u2014";
  const val = Math.abs(n) <= 1 ? n * 100 : n;
  return `${val.toFixed(1)}%`;
}

const KPI_METRICS = [
  { label: "Revenue", key: "revenue" },
  { label: "EBITDA", key: "ebitda" },
  { label: "Net Income", key: "net_income" },
  { label: "FCF", key: "fcf" },
] as const;

export default function DashboardPage() {
  const router = useRouter();
  const [widgets, setWidgets] = useState<BudgetDashboardWidget[]>([]);
  const [kpis, setKpis] = useState<KpiItem[]>([]);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [latestRunId, setLatestRunId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.user) {
      router.replace("/login");
      return;
    }
    const tid =
      session.user.user_metadata?.tenant_id ?? session.user.id;
    try {
      const [budgetRes, runsRes, actRes] = await Promise.all([
        api.budgets.getDashboard(tid),
        api.runs.list(tid),
        api.activity.list(tid, { limit: 10 }),
      ]);
      setWidgets(budgetRes.widgets ?? []);
      setActivity(actRes.items ?? []);

      const latest = runsRes.items?.[0];
      if (latest) {
        setLatestRunId(latest.run_id);
        const kpiRes = await api.runs.getKpis(tid, latest.run_id);
        setKpis(Array.isArray(kpiRes) ? kpiRes : []);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    let cancelled = false;
    load().then(() => {
      if (cancelled) return;
    });
    return () => {
      cancelled = true;
    };
  }, [load]);

  const terminalKpis = kpis.length > 0 ? kpis[kpis.length - 1] : null;
  const allAlerts = widgets.flatMap((w) =>
    w.alerts.map((a) => ({ ...a, budgetLabel: w.label }))
  );

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Financial Dashboard
          </h1>
          <VAButton variant="secondary" type="button" onClick={load}>
            Refresh
          </VAButton>
        </div>

        {error && (
          <div className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger">
            {error}
          </div>
        )}

        {loading ? (
          <VASpinner label="Loading dashboard\u2026" />
        ) : (
          <div className="space-y-6">
            {/* Row 1 \u2013 Budget health */}
            {widgets.length > 0 && (
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-va-text2">
                  Budget Health
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {widgets.map((w) => (
                    <VACard key={w.budget_id} className="p-4">
                      <p className="mb-2 text-sm font-medium text-va-text">
                        {w.label}
                      </p>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div>
                          <p className="text-xs text-va-text2">Burn rate</p>
                          <p className="font-mono text-lg font-semibold text-va-text">
                            {fmtNum(w.burn_rate)}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-va-text2">Runway</p>
                          <p className="font-mono text-lg font-semibold text-va-text">
                            {w.runway_months != null
                              ? `${w.runway_months.toFixed(0)}mo`
                              : "\u2014"}
                          </p>
                        </div>
                        <div>
                          <p className="text-xs text-va-text2">Utilisation</p>
                          <p className="font-mono text-lg font-semibold text-va-text">
                            {fmtPct(w.utilisation_pct)}
                          </p>
                        </div>
                      </div>
                    </VACard>
                  ))}
                </div>
              </section>
            )}

            {/* Row 2 \u2013 Terminal KPIs */}
            {terminalKpis && (
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-va-text2">
                  Latest Run KPIs
                  {latestRunId && (
                    <span className="ml-2 font-mono text-xs normal-case text-va-text2">
                      ({latestRunId.slice(0, 8)})
                    </span>
                  )}
                </h2>
                <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                  {KPI_METRICS.map((m) => (
                    <VACard key={m.key} className="p-4">
                      <p className="text-xs text-va-text2">{m.label}</p>
                      <p className="font-mono text-2xl font-semibold text-va-text">
                        {fmtNum(terminalKpis[m.key] as number)}
                      </p>
                    </VACard>
                  ))}
                </div>
              </section>
            )}

            {/* Row 3 \u2013 Alerts */}
            {allAlerts.length > 0 && (
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-va-text2">
                  Alerts
                </h2>
                <div className="flex flex-wrap gap-2">
                  {allAlerts.map((a, i) => (
                    <VABadge
                      key={i}
                      variant={
                        a.type === "overspend"
                          ? "danger"
                          : a.type === "underspend"
                            ? "warning"
                            : "default"
                      }
                    >
                      {a.budgetLabel}: {a.message}
                    </VABadge>
                  ))}
                </div>
              </section>
            )}

            {/* Row 4 \u2013 Activity feed */}
            {activity.length > 0 && (
              <section>
                <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-va-text2">
                  Recent Activity
                </h2>
                <VACard className="p-4">
                  <div className="space-y-3">
                    {activity.map((a) => (
                      <div key={a.id} className="flex items-start gap-3">
                        <div
                          className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${
                            a.type === "comment"
                              ? "bg-va-blue"
                              : "bg-va-violet"
                          }`}
                        />
                        <div className="min-w-0 flex-1">
                          <p className="text-sm text-va-text">{a.summary}</p>
                          <p className="text-xs text-va-text2">
                            {formatDateTime(a.timestamp)}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </VACard>
              </section>
            )}

            {widgets.length === 0 &&
              !terminalKpis &&
              activity.length === 0 && (
                <VACard className="p-6 text-center text-va-text2">
                  No dashboard data yet. Create budgets and run analyses to
                  populate this view.
                </VACard>
              )}
          </div>
        )}
      </main>
    </div>
  );
}
