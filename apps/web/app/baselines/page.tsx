"use client";

import { api, type BaselineSummary } from "@/lib/api";
import { VACard, VASpinner } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { formatDateTime } from "@/lib/format";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function BaselinesPage() {
  const [items, setItems] = useState<BaselineSummary[]>([]);
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
        const res = await api.baselines.list(tid);
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
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Baselines
          </h1>
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
          <VASpinner label="Loading baselines…" />
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No baselines yet. Create one via the API (POST /api/v1/baselines
            with a model_config).
          </VACard>
        ) : (
          <ul className="space-y-2">
            {items.map((b) => (
              <li key={b.baseline_id}>
                <Link
                  href={`/baselines/${b.baseline_id}`}
                  className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-va-text">
                      {b.baseline_id}
                    </span>
                    <span className="text-sm text-va-text2">
                      {b.is_active ? "Active" : b.status} · v{b.baseline_version}
                    </span>
                  </div>
                  {b.created_at && (
                    <p className="mt-1 text-sm text-va-text2">
                      Created {formatDateTime(b.created_at)}
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
