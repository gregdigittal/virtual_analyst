"use client";

import { VABadge, VAButton, VACard, VASpinner } from "@/components/ui";
import { api, type PimBacktestResult, type PimBacktestCommentary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(2)}%`;
}

function f2(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return v.toFixed(2);
}

// ---------------------------------------------------------------------------
// Cumulative return chart — uses pre-computed cumulative_return per period
// ---------------------------------------------------------------------------

function CumulativeReturnChart({ periods }: { periods: PimBacktestResult["periods"] }) {
  const data = periods.map((p, i) => ({
    period: i + 1,
    return: parseFloat(((p.cumulative_return) * 100).toFixed(3)),
  }));

  if (data.length === 0)
    return <p className="py-4 text-center text-sm text-va-text2">No period data available.</p>;

  return (
    <ResponsiveContainer width="100%" height={280}>
      <LineChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          dataKey="period"
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          label={{ value: "Period", position: "insideBottom", offset: -2, fill: "#94a3b8", fontSize: 11 }}
        />
        <YAxis
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          tickFormatter={(v: number) => `${v.toFixed(0)}%`}
        />
        <Tooltip
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any) => [`${Number(value).toFixed(2)}%`]}
          contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
          labelStyle={{ color: "#94a3b8" }}
        />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <ReferenceLine y={0} stroke="#64748b" strokeDasharray="4 2" />
        <Line
          type="monotone"
          dataKey="return"
          name="Cumulative Return (%)"
          stroke="#3b82f6"
          strokeWidth={2}
          dot={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// IC bar chart (per-period information coefficient)
// ---------------------------------------------------------------------------

function ICBarChart({ periods }: { periods: PimBacktestResult["periods"] }) {
  const data = periods
    .filter((p) => p.ic !== null)
    .map((p, i) => ({ period: i + 1, ic: parseFloat(((p.ic ?? 0) * 100).toFixed(3)) }));

  if (data.length === 0)
    return <p className="py-4 text-center text-sm text-va-text2">No IC data available.</p>;

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis dataKey="period" tick={{ fill: "#94a3b8", fontSize: 11 }} />
        <YAxis
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          tickFormatter={(v: number) => `${v.toFixed(0)}`}
          label={{ value: "IC ×100", angle: -90, position: "insideLeft", fill: "#94a3b8", fontSize: 11 }}
        />
        <Tooltip
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(value: any) => [`${(Number(value) / 100).toFixed(4)}`]}
          contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
          labelStyle={{ color: "#94a3b8" }}
        />
        <ReferenceLine y={0} stroke="#64748b" />
        <Bar
          dataKey="ic"
          name="IC"
          fill="#3b82f6"
          radius={[2, 2, 0, 0]}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Strategy metrics table
// ---------------------------------------------------------------------------

function StrategyMetricsTable({ result }: { result: PimBacktestResult }) {
  const rows = [
    { label: "Cumulative Return", value: pct(result.cumulative_return) },
    { label: "Annualised Return", value: pct(result.annualised_return) },
    { label: "Volatility", value: pct(result.volatility) },
    { label: "Sharpe Ratio", value: f2(result.sharpe_ratio) },
    { label: "Max Drawdown", value: pct(result.max_drawdown) },
    { label: "IC Mean", value: f2(result.ic_mean) },
    { label: "IC Std", value: f2(result.ic_std) },
    { label: "ICIR", value: f2(result.icir) },
  ];

  return (
    <div className="overflow-x-auto rounded-va-lg border border-va-border">
      <table className="w-full text-sm text-va-text">
        <thead>
          <tr className="border-b border-va-border bg-va-surface">
            <th className="px-4 py-3 text-left font-medium">Metric</th>
            <th className="px-4 py-3 text-right font-medium">Value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label} className="border-b border-va-border last:border-0">
              <td className="px-4 py-2 text-va-text2">{r.label}</td>
              <td className="px-4 py-2 text-right font-mono">{r.value}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function BacktestDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [result, setResult] = useState<PimBacktestResult | null>(null);
  const [commentary, setCommentary] = useState<PimBacktestCommentary | null>(null);
  const [loadingCommentary, setLoadingCommentary] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadResult = useCallback(async (tid: string, backtestId: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.pim.backtest.get(tid, backtestId);
      setResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  const loadCommentary = useCallback(async (tid: string, backtestId: string) => {
    setLoadingCommentary(true);
    try {
      const c = await api.pim.backtest.commentary(tid, backtestId);
      setCommentary(c);
    } catch (e) {
      // Commentary is non-critical — surface inline, don't crash
      setCommentary({
        backtest_id: backtestId,
        commentary: null,
        commentary_risks: `Failed to load commentary: ${e instanceof Error ? e.message : String(e)}`,
        limitations: "",
      });
    } finally {
      setLoadingCommentary(false);
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
      loadResult(ctx.tenantId, id);
    });
  }, [id, loadResult]);

  const strategyLabel = result?.config?.strategy_label ?? "—";
  const benchmarkLabel = result?.config?.benchmark_label ?? null;

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <Link href="/pim/backtest" className="mb-2 flex items-center gap-1 text-sm text-va-text2 hover:text-va-text">
            ← Backtest Studio
          </Link>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Backtest Detail
          </h1>
          <p className="mt-1 font-mono text-xs text-va-text2">{id}</p>
        </div>
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
            onClick={() => tenantId && loadResult(tenantId, id)}
          >
            Retry
          </VAButton>
        </VACard>
      )}

      {!loading && !error && result && (
        <div className="space-y-6">
          {/* Strategy header */}
          <VACard className="p-6">
            <div className="flex flex-wrap items-center gap-3">
              <span className="font-mono text-sm font-medium text-va-text">{strategyLabel}</span>
              <VABadge variant="default">{result.n_periods} periods</VABadge>
              {benchmarkLabel && (
                <VABadge variant="default">vs {benchmarkLabel}</VABadge>
              )}
            </div>
            {result.limitations && (
              <p className="mt-3 text-xs text-va-text2">{result.limitations}</p>
            )}
          </VACard>

          {/* Metrics table */}
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              Performance Metrics
            </h2>
            <StrategyMetricsTable result={result} />
          </VACard>

          {/* Cumulative return chart */}
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              Cumulative Return
            </h2>
            <CumulativeReturnChart periods={result.periods ?? []} />
          </VACard>

          {/* IC bar chart */}
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              Information Coefficient per Period
            </h2>
            <p className="mb-3 text-xs text-va-text2">
              IC measures the Pearson correlation between CIS rankings and realised returns.
              Positive IC indicates predictive signal. ICIR ≥ 0.5 suggests robust strategy.
            </p>
            <ICBarChart periods={result.periods ?? []} />
          </VACard>

          {/* LLM Commentary */}
          <VACard className="p-6">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-base font-medium text-va-text">AI Commentary</h2>
              {!commentary && !loadingCommentary && (
                <VAButton
                  variant="ghost"
                  onClick={() => tenantId && loadCommentary(tenantId, id)}
                >
                  Generate
                </VAButton>
              )}
            </div>

            {loadingCommentary && <VASpinner />}

            {commentary && !loadingCommentary && (
              <div className="space-y-4">
                {commentary.commentary && (
                  <div>
                    <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-va-text2">Performance</h3>
                    <p className="text-sm text-va-text leading-relaxed">{commentary.commentary}</p>
                  </div>
                )}
                {commentary.commentary_risks && (
                  <div>
                    <h3 className="mb-1 text-xs font-medium uppercase tracking-wide text-va-text2">Risks & Caveats</h3>
                    <p className="text-sm text-va-text2 leading-relaxed">{commentary.commentary_risks}</p>
                  </div>
                )}
                {commentary.limitations && (
                  <p className="text-xs text-va-text2 border-t border-va-border pt-3">{commentary.limitations}</p>
                )}
              </div>
            )}

            {!commentary && !loadingCommentary && (
              <p className="text-sm text-va-text2">
                Click Generate to produce AI commentary on signal quality and performance metrics.
              </p>
            )}
          </VACard>
        </div>
      )}
    </main>
  );
}
