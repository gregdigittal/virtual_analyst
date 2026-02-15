"use client";

import { api, type BoardPackSummary } from "@/lib/api";
import { VACard } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function BoardPacksPage() {
  const [items, setItems] = useState<BoardPackSummary[]>([]);
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
      const tid = session.user.user_metadata?.tenant_id ?? session.user.id;
      setTenantId(tid);
      try {
        const res = await api.boardPacks.list(tid);
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
            Board packs
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Create and generate board packs; export as PDF, PPTX, or HTML.
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
          <p className="text-va-text2">Loading board packs…</p>
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No board packs yet. Create one from the pack detail page (link a run and optionally a budget).
          </VACard>
        ) : (
          <ul className="space-y-2">
            {items.map((p) => (
              <li key={p.pack_id}>
                <Link
                  href={`/board-packs/${p.pack_id}`}
                  className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-va-text">{p.label}</span>
                    <span
                      className={`text-sm ${
                        p.status === "ready"
                          ? "text-va-success"
                          : p.status === "draft"
                            ? "text-va-text2"
                            : p.status === "error"
                              ? "text-va-danger"
                              : "text-va-warning"
                      }`}
                    >
                      {p.status}
                    </span>
                  </div>
                  <p className="mt-1 text-sm text-va-text2">
                    Run: {p.run_id ?? "—"}
                    {p.budget_id ? ` · Budget: ${p.budget_id}` : ""}
                  </p>
                  {p.created_at && (
                    <p className="mt-0.5 text-xs text-va-text2">
                      {new Date(p.created_at).toLocaleString()}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-4 text-sm text-va-text2">
          Create new pack via API: <code className="rounded bg-va-panel px-1">POST /api/v1/board-packs</code> with label and run_id.
        </p>
      </main>
    </div>
  );
}
