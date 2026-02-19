"use client";

import { api, type MetricsSummary } from "@/lib/api";
import { VAButton, VACard, VASpinner } from "@/components/ui";
import { Nav } from "@/components/nav";
import { getAuthContext } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

export default function DashboardPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async (tid: string) => {
    try {
      const data = await api.metrics.getSummary(tid);
      setSummary(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      await fetchSummary(ctx.tenantId);
    })();
  }, [router, fetchSummary]);

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Performance dashboard
          </h1>
          <VAButton
            variant="secondary"
            type="button"
            onClick={() => {
              if (tenantId) { setLoading(true); fetchSummary(tenantId); }
            }}
          >
            Refresh
          </VAButton>
        </div>
        {error && (
          <div className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger">
            {error}
          </div>
        )}
        {loading && !summary ? (
          <VASpinner label="Loading…" />
        ) : summary ? (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <VACard className="p-4">
                <p className="text-sm text-va-text2">Request count</p>
                <p className="font-mono text-2xl font-semibold text-va-text">
                  {summary.request_count}
                </p>
                <p className="text-xs text-va-text2">Last 1,000 requests</p>
              </VACard>
              <VACard className="p-4">
                <p className="text-sm text-va-text2">Latency P50</p>
                <p className="font-mono text-2xl font-semibold text-va-text">
                  {summary.latency_p50_ms.toFixed(1)} ms
                </p>
              </VACard>
              <VACard className="p-4">
                <p className="text-sm text-va-text2">Latency P95</p>
                <p className="font-mono text-2xl font-semibold text-va-text">
                  {summary.latency_p95_ms.toFixed(1)} ms
                </p>
              </VACard>
            </div>
            {Object.keys(summary.by_endpoint).length > 0 && (
              <VACard className="p-4">
                <h2 className="mb-3 text-sm font-medium text-va-text">
                  Latency by endpoint (avg ms)
                </h2>
                <ul className="space-y-1 text-sm">
                  {Object.entries(summary.by_endpoint)
                    .sort(([, a], [, b]) => b - a)
                    .map(([path, avg]) => (
                      <li
                        key={path}
                        className="flex justify-between gap-4 text-va-text"
                      >
                        <span className="truncate font-mono text-va-text2">
                          {path}
                        </span>
                        <span className="font-mono">{avg.toFixed(1)}</span>
                      </li>
                    ))}
                </ul>
              </VACard>
            )}
          </div>
        ) : (
          <VACard className="p-6 text-center text-va-text2">
            No dashboard data yet. Run an analysis to see metrics here.
          </VACard>
        )}
      </main>
    </div>
  );
}
