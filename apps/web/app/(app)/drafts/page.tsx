"use client";

import { api, type DraftSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VASpinner, StatePill, VAPagination, VAEmptyState, VAListToolbar } from "@/components/ui";
import { SoftGateBanner } from "@/components/SoftGateBanner";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

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
  const router = useRouter();
  const [items, setItems] = useState<DraftSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [hasBaselines, setHasBaselines] = useState(true);

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
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const blRes = await api.baselines.list(ctx.tenantId, { limit: 1 });
        setHasBaselines((blRes.items ?? []).length > 0);
      } catch { /* baseline check is non-critical */ }
    })();
  }, [router]);

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

  const displayed = search
    ? items.filter((d) =>
        d.draft_session_id.toLowerCase().includes(search.toLowerCase())
      )
    : items;

  if (!tenantId && !loading) return null;

  return (
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

      {!loading && !hasBaselines && (
        <SoftGateBanner
          message="No baselines yet — create one before starting drafts."
          actionLabel="Create baseline"
          actionHref="/marketplace"
        />
      )}

      <VAListToolbar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by draft ID…"
        filters={[
          {
            key: "status",
            label: "Status",
            options: [
              { value: "", label: "All statuses" },
              { value: "active", label: "Active" },
              { value: "ready_to_commit", label: "Ready to commit" },
              { value: "committed", label: "Committed" },
            ],
          },
        ]}
        filterValues={{ status: statusFilter }}
        onFilterChange={(key, value) => {
          if (key === "status") setStatusFilter(value);
        }}
        className="mb-4"
      />

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
        <VAEmptyState
          icon="edit"
          title="No drafts yet"
          description="Create a draft to start modifying a baseline."
          actionLabel="New draft"
          onAction={createDraft}
          variant="empty"
        />
      ) : displayed.length === 0 ? (
        <VAEmptyState
          title="No drafts match your search"
          actionLabel="Clear search"
          onAction={() => setSearch("")}
          variant="no-results"
        />
      ) : (
        <>
          <ul className="space-y-2">
            {displayed.map((d) => {
              const state = statusToState(d.status);
              return (
                <li key={d.draft_session_id}>
                  <Link
                    href={`/drafts/${d.draft_session_id}`}
                    className="block cursor-pointer rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
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
  );
}
