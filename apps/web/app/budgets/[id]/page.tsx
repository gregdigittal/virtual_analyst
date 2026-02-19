"use client";

import { api, type BudgetDetail, type BudgetDashboardWidget, type BudgetVarianceItem } from "@/lib/api";
import { VAButton, VACard, VASpinner } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function BudgetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const budgetId = params?.id as string;
  const [budget, setBudget] = useState<BudgetDetail | null>(null);
  const [dashboard, setDashboard] = useState<{ widgets: BudgetDashboardWidget[] } | null>(null);
  const [variance, setVariance] = useState<{ variances: BudgetVarianceItem[]; materiality_pct: number } | null>(null);
  const [reforecasting, setReforecasting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);

  const load = useCallback(async () => {
    const supabase = createClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (!session?.user?.id) {
      router.replace("/login");
      return;
    }
    const tid = session.user.user_metadata?.tenant_id ?? session.user.id;
    setTenantId(tid);
    try {
      const [b, d, v] = await Promise.all([
        api.budgets.get(tid, budgetId),
        api.budgets.getDashboard(tid, budgetId).catch(() => null),
        api.budgets.getVariance(tid, budgetId).catch(() => null),
      ]);
      setBudget(b);
      setDashboard(d ?? null);
      setVariance(v ?? null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBudget(null);
      setDashboard(null);
      setVariance(null);
    } finally {
      setLoading(false);
    }
  }, [budgetId, router]);

  async function handleReforecast() {
    if (!tenantId) return;
    setReforecasting(true);
    setError(null);
    try {
      await api.budgets.reforecast(tenantId, budgetId, { horizon_months: 3 });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setReforecasting(false);
    }
  }

  useEffect(() => {
    if (!budgetId) return;
    load();
  }, [budgetId, load]);

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/budgets"
            className="text-sm text-va-blue hover:underline"
          >
            ← Budgets
          </Link>
        </div>
        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <VASpinner label="Loading…" />
        ) : budget ? (
          <>
            <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
              {budget.label}
            </h1>
            <p className="mt-1 text-sm text-va-text2">
              {budget.fiscal_year} · {budget.status}
            </p>
            {budget.workflow_instance_id && (
              <p className="mt-1 text-xs text-va-text2">
                Workflow: {budget.workflow_instance_id}
              </p>
            )}
            {dashboard?.widgets?.[0] && (
              <VACard className="mt-6 p-4">
                <h2 className="text-lg font-medium text-va-text">KPI summary</h2>
                <dl className="mt-2 grid gap-2 text-sm">
                  {dashboard.widgets[0].burn_rate != null && (
                    <div>
                      <dt className="text-va-text2">Burn rate</dt>
                      <dd className="font-medium text-va-text">{dashboard.widgets[0].burn_rate}</dd>
                    </div>
                  )}
                  {dashboard.widgets[0].utilisation_pct != null && (
                    <div>
                      <dt className="text-va-text2">Utilisation %</dt>
                      <dd className="font-medium text-va-text">{dashboard.widgets[0].utilisation_pct}%</dd>
                    </div>
                  )}
                  {dashboard.widgets[0].runway_months != null && (
                    <div>
                      <dt className="text-va-text2">Runway (months)</dt>
                      <dd className="font-medium text-va-text">{dashboard.widgets[0].runway_months}</dd>
                    </div>
                  )}
                </dl>
                {Array.isArray(dashboard.widgets[0].alerts) && dashboard.widgets[0].alerts.length > 0 && (
                  <div className="mt-3">
                    <h3 className="text-sm font-medium text-va-warning">Alerts</h3>
                    <ul className="mt-1 list-inside list-disc text-sm text-va-text2">
                      {(dashboard.widgets[0].alerts as { message: string }[]).map((a, i) => (
                        <li key={i}>{a.message}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </VACard>
            )}
            {variance && variance.variances.length > 0 ? (
              <VACard className="mt-6 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h2 className="text-lg font-medium text-va-text">Variance analysis</h2>
                  <span className="text-xs text-va-text2">
                    Materiality threshold: {variance.materiality_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-va-border text-left text-xs text-va-text2">
                        <th className="pb-2 pr-4 font-medium">Account</th>
                        <th className="pb-2 pr-4 text-right font-medium">Budget</th>
                        <th className="pb-2 pr-4 text-right font-medium">Actual</th>
                        <th className="pb-2 pr-4 text-right font-medium">Variance</th>
                        <th className="pb-2 text-right font-medium">%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {variance.variances.map((v, i) => (
                        <tr key={i} className="border-b border-va-border/50">
                          <td className="py-1.5 pr-4 font-mono text-va-text">{v.account_ref}</td>
                          <td className="py-1.5 pr-4 text-right font-mono text-va-text2">{v.budget_amount.toLocaleString()}</td>
                          <td className="py-1.5 pr-4 text-right font-mono text-va-text2">{v.actual_amount.toLocaleString()}</td>
                          <td className={`py-1.5 pr-4 text-right font-mono ${v.favourable ? "text-va-green" : "text-va-danger"}`}>
                            {v.variance_absolute > 0 ? "+" : ""}{v.variance_absolute.toLocaleString()}
                          </td>
                          <td className={`py-1.5 text-right font-mono text-xs ${v.material ? "font-semibold" : ""} ${v.favourable ? "text-va-green" : "text-va-danger"}`}>
                            {v.variance_percent.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4">
                  <VAButton
                    variant="secondary"
                    onClick={handleReforecast}
                    disabled={reforecasting}
                  >
                    {reforecasting ? "Reforecasting…" : "Run 3-month reforecast"}
                  </VAButton>
                </div>
              </VACard>
            ) : (
              <VACard className="mt-6 p-4">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-va-text2">No variance data available for this budget.</p>
                  <VAButton
                    variant="secondary"
                    onClick={handleReforecast}
                    disabled={reforecasting}
                  >
                    {reforecasting ? "Reforecasting…" : "Run 3-month reforecast"}
                  </VAButton>
                </div>
              </VACard>
            )}
          </>
        ) : (
          <p className="text-va-text2">Budget not found.</p>
        )}
      </main>
    </div>
  );
}
