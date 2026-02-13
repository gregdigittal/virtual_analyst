"use client";

import { api } from "@/lib/api";
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

  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-6xl px-4 py-8">
        <div className="mb-6 flex items-center gap-4">
          <Link
            href="/runs"
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            ← Runs
          </Link>
          <Link
            href={`/runs/${runId}`}
            className="text-sm text-muted-foreground hover:text-foreground"
          >
            Run {runId}
          </Link>
        </div>
        <h1 className="mb-4 text-2xl font-semibold tracking-tight">
          Monte Carlo Results
        </h1>
        {error && (
          <div
            className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <p className="text-muted-foreground">Loading MC results…</p>
        ) : data ? (
          <div className="space-y-6">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-sm text-muted-foreground">
                {data.num_simulations} simulations, seed {data.seed}
              </p>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-3 text-lg font-medium">Percentile table (terminal)</h2>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-border">
                      <th className="px-3 py-2 text-left font-medium">Metric</th>
                      <th className="px-3 py-2 text-right font-medium">P5</th>
                      <th className="px-3 py-2 text-right font-medium">P50</th>
                      <th className="px-3 py-2 text-right font-medium">P95</th>
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
                        <tr key={metric} className="border-b border-border/50">
                          <td className="px-3 py-2 font-medium capitalize">{metric.replace("_", " ")}</td>
                          <td className="px-3 py-2 text-right">{p5 != null ? p5.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</td>
                          <td className="px-3 py-2 text-right">{p50 != null ? p50.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</td>
                          <td className="px-3 py-2 text-right">{p95 != null ? p95.toLocaleString(undefined, { maximumFractionDigits: 0 }) : "—"}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
            <div className="rounded-lg border border-border bg-card p-4">
              <h2 className="mb-3 text-lg font-medium">Revenue fan (P10 / P50 / P90)</h2>
              <div className="h-64 overflow-x-auto">
                {data.percentiles.revenue && periodLabels.length > 0 ? (
                  <div className="flex h-full items-end gap-px">
                    {periodLabels.map((_, i) => (
                      <div key={i} className="flex flex-1 flex-col justify-end gap-0.5">
                        <div
                          className="w-full rounded-t bg-green-200/80"
                          style={{
                            height: `${Math.max(2, (data.percentiles.revenue.p90[i] ?? 0) / Math.max(1, (data.percentiles.revenue.p90 as number[]).reduce((a, b) => Math.max(a, b), 1)) * 100)}%`,
                          }}
                        />
                        <div
                          className="w-full rounded-t bg-green-500/90"
                          style={{
                            height: `${Math.max(2, (data.percentiles.revenue.p50[i] ?? 0) / Math.max(1, (data.percentiles.revenue.p90 as number[]).reduce((a, b) => Math.max(a, b), 1)) * 100)}%`,
                          }}
                        />
                        <div
                          className="w-full rounded-t bg-green-800/90"
                          style={{
                            height: `${Math.max(2, (data.percentiles.revenue.p10[i] ?? 0) / Math.max(1, (data.percentiles.revenue.p90 as number[]).reduce((a, b) => Math.max(a, b), 1)) * 100)}%`,
                          }}
                        />
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">No series data.</p>
                )}
              </div>
              <p className="mt-2 text-xs text-muted-foreground">
                Bars: P10 (dark), P50 (mid), P90 (light) by period
              </p>
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground">No MC data for this run.</p>
        )}
      </main>
    </div>
  );
}
