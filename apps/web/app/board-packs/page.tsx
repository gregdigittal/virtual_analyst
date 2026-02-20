"use client";

import { api, type BoardPackSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VASpinner, VAPagination } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { Nav } from "@/components/nav";
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
    })();
  }, [router]);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

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
          <VASpinner label="Loading board packs…" />
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No board packs yet. Create one from the pack detail page (link a run and optionally a budget).
          </VACard>
        ) : (
          <>
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
        <p className="mt-4 text-sm text-va-text2">
          Create new pack via API: <code className="rounded bg-va-panel px-1">POST /api/v1/board-packs</code> with label and run_id.
        </p>
      </main>
    </div>
  );
}
