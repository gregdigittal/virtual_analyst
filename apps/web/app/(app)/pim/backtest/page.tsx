"use client";

import { VABadge, VAButton, VACard, VASpinner } from "@/components/ui";
import { api, type PimBacktestResult, type PimBacktestSummaryItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function pct(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function f2(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2);
}

function IcirBadge({ icir }: { icir: number | null }) {
  if (icir === null) return <VABadge variant="default">—</VABadge>;
  if (icir >= 1.5) return <VABadge variant="success">{icir.toFixed(2)}</VABadge>;
  if (icir >= 0.5) return <VABadge variant="warning">{icir.toFixed(2)}</VABadge>;
  return <VABadge variant="default">{icir.toFixed(2)}</VABadge>;
}

function SummaryTable({ items }: { items: PimBacktestSummaryItem[] }) {
  if (items.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-va-text2">
        No backtest strategies found. Run a backtest to see aggregated performance here.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto rounded-va-lg border border-va-border">
      <table className="w-full min-w-[900px] text-sm text-va-text">
        <thead>
          <tr className="border-b border-va-border bg-va-surface">
            <th className="px-4 py-3 text-left font-medium">Strategy</th>
            <th className="px-4 py-3 text-right font-medium">Runs</th>
            <th className="px-4 py-3 text-right font-medium">Avg Return</th>
            <th className="px-4 py-3 text-right font-medium">Avg Sharpe</th>
            <th className="px-4 py-3 text-right font-medium">Avg IC</th>
            <th className="px-4 py-3 text-right font-medium">ICIR</th>
            <th className="px-4 py-3 text-right font-medium">Best</th>
            <th className="px-4 py-3 text-right font-medium">Worst</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.strategy_label} className="border-b border-va-border last:border-0 hover:bg-va-surface/50">
              <td className="px-4 py-3 font-mono text-xs">{item.strategy_label}</td>
              <td className="px-4 py-3 text-right">{item.run_count}</td>
              <td className="px-4 py-3 text-right">{pct(item.avg_cumulative_return)}</td>
              <td className="px-4 py-3 text-right">{f2(item.avg_sharpe_ratio)}</td>
              <td className="px-4 py-3 text-right">{f2(item.avg_ic_mean)}</td>
              <td className="px-4 py-3 text-right">
                <IcirBadge icir={item.avg_icir} />
              </td>
              <td className="px-4 py-3 text-right text-green-400">{pct(item.best_cumulative_return)}</td>
              <td className="px-4 py-3 text-right text-red-400">{pct(item.worst_cumulative_return)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BacktestStudioPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [summary, setSummary] = useState<PimBacktestSummaryItem[]>([]);
  const [summaryNote, setSummaryNote] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadSummary = useCallback(async (tid: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.pim.backtest.summary(tid);
      setSummary(res.items);
      setSummaryNote(res.note);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    getAuthContext().then((ctx) => {
      if (!ctx) {
        window.location.href = "/login";
        return;
      }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      loadSummary(ctx.tenantId);
    });
  }, [loadSummary]);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Backtest Studio
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Walk-forward backtest results with IC/ICIR signal quality metrics.
          </p>
        </div>
        <Link href="/pim/backtest/run">
          <VAButton>Run Backtest</VAButton>
        </Link>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <VASpinner />
        </div>
      )}

      {error && !loading && (
        <VACard className="border-red-500/30 bg-red-500/5 p-4">
          <p className="text-sm text-red-400">{error}</p>
          <VAButton
            variant="ghost"
            className="mt-2"
            onClick={() => tenantId && loadSummary(tenantId)}
          >
            Retry
          </VAButton>
        </VACard>
      )}

      {!loading && !error && (
        <>
          <VACard className="mb-6 p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              Strategy Performance Summary
            </h2>
            <SummaryTable items={summary} />
            {summaryNote && (
              <p className="mt-3 text-xs text-va-text2">{summaryNote}</p>
            )}
          </VACard>

          <VACard className="p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              Recent Backtest Runs
            </h2>
            <RecentRunsTable tenantId={tenantId} />
          </VACard>
        </>
      )}
    </main>
  );
}

function RecentRunsTable({ tenantId }: { tenantId: string | null }) {
  const [runs, setRuns] = useState<PimBacktestResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tenantId) return;
    setLoading(true);
    api.pim.backtest.results(tenantId, { limit: 20 })
      .then((res) => setRuns(res.items))
      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [tenantId]);

  if (loading) return <VASpinner />;
  if (error) return <p className="text-sm text-red-400">{error}</p>;
  if (runs.length === 0)
    return <p className="text-sm text-va-text2">No backtest runs yet.</p>;

  return (
    <div className="overflow-x-auto rounded-va-lg border border-va-border">
      <table className="w-full min-w-[700px] text-sm text-va-text">
        <thead>
          <tr className="border-b border-va-border bg-va-surface">
            <th className="px-4 py-3 text-left font-medium">Run ID</th>
            <th className="px-4 py-3 text-left font-medium">Strategy</th>
            <th className="px-4 py-3 text-right font-medium">Periods</th>
            <th className="px-4 py-3 text-right font-medium">Return</th>
            <th className="px-4 py-3 text-right font-medium">Sharpe</th>
            <th className="px-4 py-3 text-right font-medium">IC</th>
            <th className="px-4 py-3 text-right font-medium">ICIR</th>
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.backtest_id} className="border-b border-va-border last:border-0 hover:bg-va-surface/50">
              <td className="px-4 py-3">
                <Link
                  href={`/pim/backtest/${encodeURIComponent(r.backtest_id)}`}
                  className="font-mono text-xs text-va-blue hover:underline"
                >
                  {r.backtest_id.slice(0, 12)}…
                </Link>
              </td>
              <td className="px-4 py-3 font-mono text-xs">{r.config?.strategy_label ?? "—"}</td>
              <td className="px-4 py-3 text-right">{r.n_periods}</td>
              <td className="px-4 py-3 text-right">{pct(r.cumulative_return)}</td>
              <td className="px-4 py-3 text-right">{f2(r.sharpe_ratio)}</td>
              <td className="px-4 py-3 text-right">{f2(r.ic_mean)}</td>
              <td className="px-4 py-3 text-right">
                <IcirBadge icir={r.icir} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
