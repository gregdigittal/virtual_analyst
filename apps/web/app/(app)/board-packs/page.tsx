"use client";

import { api, type BoardPackSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VAListSkeleton, VAPagination, VAEmptyState, VAListToolbar } from "@/components/ui";
import { SoftGateBanner } from "@/components/SoftGateBanner";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

export default function BoardPacksPage() {
  const router = useRouter();
  const [items, setItems] = useState<BoardPackSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [hasBaselines, setHasBaselines] = useState(true);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.boardPacks.list(tenantId, {
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setItems(res.items);
      setHasMore(res.items.length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, page]);

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

  if (!tenantId && !loading) return null;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Board packs
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Create and generate board packs; export as PDF, PPTX, or HTML.
          </p>
        </div>
        <Link href="/runs">
          <VAButton aria-label="Create board pack">Create Board Pack</VAButton>
        </Link>
      </div>

      {!loading && !hasBaselines && (
        <SoftGateBanner
          message="No baselines or runs yet — complete a run before creating board packs."
          actionLabel="Create baseline"
          actionHref="/marketplace"
        />
      )}

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}
      {loading ? (
        <VAListSkeleton count={4} />
      ) : items.length === 0 ? (
        <VAEmptyState
          icon="briefcase"
          title="No board packs yet"
          description="Create a board pack from your completed runs."
          actionLabel="View runs"
          actionHref="/runs"
          variant="empty"
        />
      ) : (() => {
        const displayed = search
          ? items.filter((i) => i.label.toLowerCase().includes(search.toLowerCase()))
          : items;
        return (
        <>
          <VAListToolbar
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search board packs…"
            className="mb-4"
          />
          {displayed.length === 0 ? (
            <VAEmptyState
              title="No matching board packs"
              description="Try a different search term."
              actionLabel="Clear search"
              onAction={() => setSearch("")}
              variant="no-results"
            />
          ) : (
          <>
          <ul className="space-y-2">
            {displayed.map((p) => (
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
                      {formatDateTime(p.created_at)}
                    </p>
                  )}
                </Link>
              </li>
            ))}
          </ul>
          <VAPagination
            page={page}
            pageSize={PAGE_SIZE}
            hasMore={hasMore}
            onPageChange={setPage}
          />
          </>
          )}
        </>
        );
      })()}
      <p className="mt-4 text-sm text-va-text2">
        Create new pack via API: <code className="rounded bg-va-panel px-1">POST /api/v1/board-packs</code> with label and run_id.
      </p>
    </main>
  );
}
