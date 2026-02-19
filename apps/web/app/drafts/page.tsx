"use client";

import { api, type DraftSummary } from "@/lib/api";
import { VAButton, VACard, VASelect, VASpinner, StatePill, VAPagination } from "@/components/ui";
import { Nav } from "@/components/nav";
import { createClient } from "@/lib/supabase/client";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const PAGE_SIZE = 20;

function statusToState(
  status: string
): "draft" | "selected" | "committed" | null {
  if (status === "active") return "draft";
  if (status === "ready_to_commit") return "selected";
  if (status === "committed") return "committed";
  return null;
}

export default function DraftsPage() {
  const [items, setItems] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.drafts.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        ...(statusFilter && { status: statusFilter }),
      });
      setItems(res.items);
      setHasMore(res.items.length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page, statusFilter]);

  useEffect(() => {
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.user?.id) return;
      setTenantId(session.user.id);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  useEffect(() => {
    setPage(1);
  }, [statusFilter]);

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
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Drafts
          </h1>
          <VAButton
            variant="primary"
            type="button"
            onClick={createDraft}
            disabled={creating}
          >
            {creating ? "Creating…" : "New draft"}
          </VAButton>
        </div>

        <div className="mb-4">
          <VASelect
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="ready_to_commit">Ready to commit</option>
            <option value="committed">Committed</option>
          </VASelect>
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
          <VASpinner label="Loading drafts…" />
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No drafts yet. Create a draft to build a model with chat and
            assumptions, then commit to create a baseline.
          </VACard>
        ) : (
          <>
            <ul className="space-y-2">
              {items.map((d) => {
                const state = statusToState(d.status);
                return (
                  <li key={d.draft_session_id}>
                    <Link
                      href={`/drafts/${d.draft_session_id}`}
                      className="block rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-va-text">
                          {d.draft_session_id}
                        </span>
                        {state ? (
                          <StatePill state={state} />
                        ) : (
                          <span className="rounded-va-xs bg-va-muted/20 px-2 py-0.5 text-sm text-va-text2">
                            {d.status}
                          </span>
                        )}
                      </div>
                      {d.created_at && (
                        <p className="mt-1 text-sm text-va-text2">
                          Created {formatDateTime(d.created_at)}
                        </p>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
            <VAPagination
              page={page}
              pageSize={PAGE_SIZE}
              hasMore={hasMore}
              onPageChange={setPage}
            />
          </>
        )}
      </main>
    </div>
  );
}
