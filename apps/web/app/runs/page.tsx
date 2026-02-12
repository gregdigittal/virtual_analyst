"use client";

import { api, type RunSummary } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function RunsPage() {
  const [items, setItems] = useState<RunSummary[]>([]);
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
        const res = await api.runs.list(tid);
        if (!cancelled) setItems(res.items);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            View run results, statements, and KPIs.
          </p>
        </div>
        {error && (
          <div
            className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
            role="alert"
          >
            {error}
          </div>
        )}
        {loading ? (
          <p className="text-muted-foreground">Loading runs…</p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-6 text-center text-muted-foreground">
            No runs yet. Create a baseline and run the model from the baseline
            detail page.
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((r) => (
              <li key={r.run_id}>
                <Link
                  href={`/runs/${r.run_id}`}
                  className="block rounded-lg border border-border bg-card p-4 transition hover:bg-muted/50"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{r.run_id}</span>
                    <span
                      className={`text-sm ${
                        r.status === "succeeded"
                          ? "text-green-600"
                          : r.status === "failed"
                            ? "text-red-600"
                            : "text-muted-foreground"
                      }`}
                    >
                      {r.status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-muted-foreground">
                    Baseline {r.baseline_id}
                    {r.scenario_id ? ` · Scenario ${r.scenario_id}` : ""}
                  </p>
                  {r.created_at && (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {new Date(r.created_at).toLocaleString()}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
