"use client";

import { api, type BudgetDetail, type BudgetDashboardWidget } from "@/lib/api";
import { VACard } from "@/components/ui";
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
      const [b, d] = await Promise.all([
        api.budgets.get(tid, budgetId),
        api.budgets.getDashboard(tid, budgetId).catch(() => null),
      ]);
      setBudget(b);
      setDashboard(d ?? null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBudget(null);
      setDashboard(null);
    } finally {
      setLoading(false);
    }
  }, [budgetId, router]);

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
          <p className="text-va-text2">Loading…</p>
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
            <p className="mt-4 text-sm text-va-text2">
              Variance and reforecast: use API <code className="rounded bg-va-panel px-1">GET /api/v1/budgets/{budgetId}/variance</code> and{" "}
              <code className="rounded bg-va-panel px-1">POST /api/v1/budgets/{budgetId}/reforecast</code>.
            </p>
          </>
        ) : (
          <p className="text-va-text2">Budget not found.</p>
        )}
      </main>
    </div>
  );
}
