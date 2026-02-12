"use client";

import { api, type BaselineSummary } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
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
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">Baselines</h1>
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
          <p className="text-muted-foreground">Loading baselines…</p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-6 text-center text-muted-foreground">
            No baselines yet. Create one via the API (POST /api/v1/baselines with a model_config).
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((b) => (
              <li key={b.baseline_id}>
                <Link
                  href={`/baselines/${b.baseline_id}`}
                  className="block rounded-lg border border-border bg-card p-4 transition hover:bg-muted/50"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{b.baseline_id}</span>
                    <span className="text-sm text-muted-foreground">
                      {b.is_active ? "Active" : b.status} · v{b.baseline_version}
                    </span>
                  </div>
                  {b.created_at && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      Created {new Date(b.created_at).toLocaleString()}
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
