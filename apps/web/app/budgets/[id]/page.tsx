"use client";

import { api, type BudgetDetail, type BudgetDashboardWidget, type BudgetVarianceItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VASpinner } from "@/components/ui";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

function VarianceTrendChart({ data }: { data: { period_ordinal: number; budget_total: number; actual_total: number; variance_pct: number }[] }) {
  if (data.length === 0) return null;
  const W = 600, H = 200;
  const PAD = { top: 20, right: 20, bottom: 30, left: 60 };
  const plotW = W - PAD.left - PAD.right;
  const plotH = H - PAD.top - PAD.bottom;
  const maxVal = Math.max(...data.flatMap((d) => [d.budget_total, d.actual_total]), 1);
  const minVal = Math.min(...data.flatMap((d) => [d.budget_total, d.actual_total]), 0);
  const range = maxVal - minVal || 1;
  function x(i: number) { return PAD.left + (i / Math.max(data.length - 1, 1)) * plotW; }
  function y(v: number) { return PAD.top + plotH - ((v - minVal) / range) * plotH; }
  const budgetPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d.budget_total).toFixed(1)}`).join(" ");
  const actualPath = data.map((d, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(d.actual_total).toFixed(1)}`).join(" ");
  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-[600px]" role="img" aria-label="Variance trend chart">
        {[0, 0.25, 0.5, 0.75, 1].map((t) => {
          const yy = PAD.top + plotH * (1 - t);
          const val = minVal + range * t;
          return (
            <g key={t}>
              <line x1={PAD.left} y1={yy} x2={W - PAD.right} y2={yy} stroke="rgba(255,255,255,0.08)" />
              <text x={PAD.left - 6} y={yy + 4} textAnchor="end" className="fill-va-text2 text-[9px]">{(val / 1000).toFixed(0)}k</text>
            </g>
          );
        })}
        {data.map((d, i) => (
          <text key={i} x={x(i)} y={H - 8} textAnchor="middle" className="fill-va-text2 text-[9px]">P{d.period_ordinal}</text>
        ))}
        <path d={budgetPath} fill="none" stroke="#6366f1" strokeWidth="2" strokeDasharray="4 3" />
        <path d={actualPath} fill="none" stroke="#22d3ee" strokeWidth="2" />
        <line x1={PAD.left} y1={10} x2={PAD.left + 20} y2={10} stroke="#6366f1" strokeWidth="2" strokeDasharray="4 3" />
        <text x={PAD.left + 24} y={13} className="fill-va-text2 text-[9px]">Budget</text>
        <line x1={PAD.left + 80} y1={10} x2={PAD.left + 100} y2={10} stroke="#22d3ee" strokeWidth="2" />
        <text x={PAD.left + 104} y={13} className="fill-va-text2 text-[9px]">Actual</text>
      </svg>
    </div>
  );
}

function DepartmentRankingChart({ data }: { data: { department_ref: string; actual_total: number }[] }) {
  if (data.length === 0) return null;
  const maxVal = Math.max(...data.map((d) => d.actual_total), 1);
  return (
    <div className="space-y-2">
      {data.map((d) => (
        <div key={d.department_ref} className="flex items-center gap-3">
          <span className="w-28 shrink-0 truncate text-xs text-va-text2 text-right">{d.department_ref}</span>
          <div className="h-5 flex-1 rounded-sm bg-va-surface">
            <div className="h-full rounded-sm bg-va-blue/60" style={{ width: `${(d.actual_total / maxVal) * 100}%` }} />
          </div>
          <span className="w-20 shrink-0 text-right font-mono text-xs text-va-text">{d.actual_total.toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

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
    const ctx = await getAuthContext();
    if (!ctx) { router.replace("/login"); return; }
    api.setAccessToken(ctx.accessToken);
    setTenantId(ctx.tenantId);
    try {
      const [b, d, v] = await Promise.all([
        api.budgets.get(ctx.tenantId, budgetId),
        api.budgets.getDashboard(ctx.tenantId, budgetId).catch(() => null),
        api.budgets.getVariance(ctx.tenantId, budgetId).catch(() => null),
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
            {dashboard?.widgets?.[0]?.variance_trend?.length ? (
              <VACard className="mt-6 p-4">
                <h2 className="mb-3 text-lg font-medium text-va-text">Budget vs actual trend</h2>
                <VarianceTrendChart data={dashboard.widgets[0].variance_trend} />
              </VACard>
            ) : null}
            {dashboard?.widgets?.[0]?.department_ranking?.length ? (
              <VACard className="mt-6 p-4">
                <h2 className="mb-3 text-lg font-medium text-va-text">Spend by department</h2>
                <DepartmentRankingChart data={dashboard.widgets[0].department_ranking} />
              </VACard>
            ) : null}
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
