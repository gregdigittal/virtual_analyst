"use client";

import { api, type DraftSummary } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function DraftsPage() {
  const [items, setItems] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

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
        const res = await api.drafts.list(tid);
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

  async function createDraft() {
    if (!tenantId) return;
    setCreating(true);
    setError(null);
    try {
      const res = await api.drafts.create(tenantId);
      window.location.href = `/drafts/${res.draft_session_id}`;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">Drafts</h1>
          <button
            type="button"
            onClick={createDraft}
            disabled={creating}
            className="rounded-md bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {creating ? "Creating…" : "New draft"}
          </button>
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
          <p className="text-muted-foreground">Loading drafts…</p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-6 text-center text-muted-foreground">
            No drafts yet. Create a draft to build a model with chat and assumptions, then commit to create a baseline.
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((d) => (
              <li key={d.draft_session_id}>
                <Link
                  href={`/drafts/${d.draft_session_id}`}
                  className="block rounded-lg border border-border bg-card p-4 transition hover:bg-muted/50"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{d.draft_session_id}</span>
                    <span
                      className={`rounded px-2 py-0.5 text-sm ${
                        d.status === "active"
                          ? "bg-blue-100 text-blue-800"
                          : d.status === "ready_to_commit"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {d.status}
                    </span>
                  </div>
                  {d.created_at && (
                    <p className="mt-1 text-sm text-muted-foreground">
                      Created {new Date(d.created_at).toLocaleString()}
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
