"use client";

import { api } from "@/lib/api";
import { VACard, VASpinner } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

export default function RunMcPage() {
  const params = useParams();
  const runId = params.id as string;
  const [data, setData] = useState<{
    num_simulations: number;
    seed: number;
    percentiles: Record<string, Record<string, number[]>>;
    summary: Record<string, unknown>;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.user?.id) return;
      const tid = session.user.id;
      setTenantId(tid);
      try {
        const res = await api.runs.getMc(tid, runId);
        if (!cancelled) setData(res);
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId]);

  if (!tenantId && !loading) return null;

  const periods = data?.percentiles?.revenue?.p50?.length ?? 0;
  const periodLabels = Array.from({ length: periods }, (_, i) => `P${i}`);
  const maxVal =
    data?.percentiles?.revenue?.p90?.reduce((a, b) => Math.max(a, b), 1) ?? 1;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/runs"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            ← Runs
          </Link>
          <Link
            href={`/runs/${runId}`}
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            Run {runId}
          </Link>
        </div>
        <h1 className="font-brand mb-4 text-2xl font-semibold tracking-tight text-va-text">
          Monte Carlo Results
        </h1>
        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <VASpinner label="Loading MC results…" />
        ) : data ? (
          <div className="space-y-6">
            <VACard className="p-4">
              <p className="text-sm text-va-text2">
                {data.num_simulations} simulations, seed {data.seed}
              </p>
            </VACard>
            <VACard className="p-4">
              <h2 className="mb-3 font-brand text-lg font-medium text-va-text">
                Percentile table (terminal)
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm text-va-text">
                  <thead>
                    <tr className="border-b border-va-border">
                      <th className="px-3 py-2 text-left font-medium">Metric</th>
                      <th className="px-3 py-2 text-right font-medium text-va-blue">P5</th>
                      <th className="px-3 py-2 text-right font-medium text-va-violet">P50</th>
                      <th className="px-3 py-2 text-right font-medium text-va-magenta">P95</th>
                    </tr>
                  </thead>
                  <tbody>
                    {["revenue", "ebitda", "net_income", "fcf"].map((metric) => {
                      const p = data.percentiles[metric];
                      const last = periods - 1;
                      const p5 = p?.p5?.[last];
                      const p50 = p?.p50?.[last];
                      const p95 = p?.p95?.[last];
                      return (
                        <tr key={metric} className="border-b border-va-border/50">
                          <td className="px-3 py-2 font-medium capitalize">
                            {metric.replaceAll("_", " ")}
                          </td>
                          <td className="px-3 py-2 text-right font-mono">
                            {p5 != null
                              ? p5.toLocaleString(undefined, {
                                  maximumFractionDigits: 0,
                                })
                              : "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono">
                            {p50 != null
                              ? p50.toLocaleString(undefined, {
                                  maximumFractionDigits: 0,
                                })
                              : "—"}
                          </td>
                          <td className="px-3 py-2 text-right font-mono">
                            {p95 != null
                              ? p95.toLocaleString(undefined, {
                                  maximumFractionDigits: 0,
                                })
                              : "—"}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </VACard>
            <VACard className="p-4">
              <h2 className="font-brand mb-3 text-lg font-medium text-va-text">
                Revenue fan (P10 / P50 / P90)
              </h2>
              <div className="h-64 overflow-x-auto">
                {data.percentiles.revenue && periodLabels.length > 0 ? (
                  <div className="flex h-full items-end gap-px">
                    {periodLabels.map((_, i) => (
                      <div
                        key={i}
                        className="flex flex-1 flex-col justify-end gap-0.5"
                      >
                        <div
                          className="w-full rounded-t bg-va-magenta/80"
                          style={{
                            height: `${Math.max(
                              2,
                              ((data.percentiles.revenue.p90[i] ?? 0) / maxVal) * 100
                            )}%`,
                          }}
                        />
                        <div
                          className="w-full rounded-t bg-va-violet/90"
                          style={{
                            height: `${Math.max(
                              2,
                              ((data.percentiles.revenue.p50[i] ?? 0) / maxVal) * 100
                            )}%`,
                          }}
                        />
                        <div
                          className="w-full rounded-t bg-va-blue/90"
                          style={{
                            height: `${Math.max(
                              2,
                              ((data.percentiles.revenue.p10[i] ?? 0) / maxVal) * 100
                            )}%`,
                          }}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-va-text2">No series data.</p>
                )}
              </div>
              <p className="mt-2 text-xs text-va-text2">
                Bars: P10 (blue), P50 (violet), P90 (magenta) by period
              </p>
            </VACard>
          </div>
        ) : (
          <p className="text-va-text2">No MC data for this run.</p>
        )}
      </main>
    </div>
  );
}
