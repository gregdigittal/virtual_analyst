"use client";

import { api, type RunSummary } from "@/lib/api";
import { VACard } from "@/components/ui";
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
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Runs
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            View run results, statements, and KPIs.
          </p>
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
          <p className="text-va-text2">Loading runs…</p>
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No runs yet. Create a baseline and run the model from the baseline
            detail page.
          </VACard>
        ) : (
          <ul className="space-y-2">
            {items.map((r) => (
              <li key={r.run_id}>
                <Link
                  href={`/runs/${r.run_id}`}
                  className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-va-text">{r.run_id}</span>
                    <span
                      className={`text-sm ${
                        r.status === "succeeded"
                          ? "text-va-success"
                          : r.status === "failed"
                            ? "text-va-danger"
                            : "text-va-text2"
                      }`}
                    >
                      {r.status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-va-text2">
                    Baseline {r.baseline_id}
                    {r.scenario_id ? ` · Scenario ${r.scenario_id}` : ""}
                  </p>
                  {r.created_at && (
                    <p className="mt-0.5 text-xs text-va-text2">
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
