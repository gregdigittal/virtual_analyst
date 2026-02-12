"use client";

import { Nav } from "@/components/nav";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface MetricsSummary {
  request_count: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  by_endpoint: Record<string, number>;
}

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchSummary = useCallback(async () => {
    try {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const res = await fetch(`${API_URL}/api/v1/metrics/summary`, {
        headers: {
          "X-Tenant-ID":
            session?.user?.user_metadata?.tenant_id ?? session?.user?.id ?? "",
          Authorization: `Bearer ${session?.access_token ?? ""}`,
        },
      });
      if (!res.ok) throw new Error(res.statusText);
      const data = (await res.json()) as MetricsSummary;
      setSummary(data);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.user) {
        router.replace("/login");
        return;
      }
      if (!cancelled) await fetchSummary();
    })();
    return () => {
      cancelled = true;
    };
  }, [router, fetchSummary]);

  if (!summary && !loading && !error) return null;

  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">
            Performance dashboard
          </h1>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              fetchSummary();
            }}
            className="rounded-md border border-input bg-background px-3 py-1.5 text-sm hover:bg-accent"
          >
            Refresh
          </button>
        </div>
        {error && (
          <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
            {error}
          </div>
        )}
        {loading && !summary ? (
          <p className="text-muted-foreground">Loading…</p>
        ) : summary ? (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="rounded-lg border bg-card p-4">
                <p className="text-sm text-muted-foreground">Request count</p>
                <p className="text-2xl font-semibold">{summary.request_count}</p>
                <p className="text-xs text-muted-foreground">
                  Last 1,000 requests
                </p>
              </div>
              <div className="rounded-lg border bg-card p-4">
                <p className="text-sm text-muted-foreground">Latency P50</p>
                <p className="text-2xl font-semibold">
                  {summary.latency_p50_ms.toFixed(1)} ms
                </p>
              </div>
              <div className="rounded-lg border bg-card p-4">
                <p className="text-sm text-muted-foreground">Latency P95</p>
                <p className="text-2xl font-semibold">
                  {summary.latency_p95_ms.toFixed(1)} ms
                </p>
              </div>
            </div>
            {Object.keys(summary.by_endpoint).length > 0 && (
              <div className="rounded-lg border bg-card p-4">
                <h2 className="mb-3 text-sm font-medium">Latency by endpoint (avg ms)</h2>
                <ul className="space-y-1 text-sm">
                  {Object.entries(summary.by_endpoint)
                    .sort(([, a], [, b]) => b - a)
                    .map(([path, avg]) => (
                      <li key={path} className="flex justify-between gap-4">
                        <span className="truncate font-mono text-muted-foreground">
                          {path}
                        </span>
                        <span>{avg.toFixed(1)}</span>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        ) : null}
      </main>
    </div>
  );
}
