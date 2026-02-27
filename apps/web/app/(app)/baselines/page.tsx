"use client";

import { api, type BaselineSummary } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VASpinner, VAPagination, VAEmptyState, VAListToolbar } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

export default function BaselinesPage() {
  const router = useRouter();
  const [items, setItems] = useState<BaselineSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [search, setSearch] = useState("");

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.baselines.list(tenantId, {
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

  const displayed = search
    ? items.filter((b) =>
        b.baseline_id.toLowerCase().includes(search.toLowerCase())
      )
    : items;

  if (!tenantId && !loading) return null;

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Baselines
        </h1>
      </div>

      <VAListToolbar
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder="Search by baseline ID…"
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
        <VASpinner label="Loading baselines…" />
      ) : items.length === 0 ? (
        <VAEmptyState
          icon="layers"
          title="No baselines yet"
          description="Import data or browse the marketplace to create your first baseline."
          actionLabel="Browse marketplace"
          actionHref="/marketplace"
          variant="empty"
        />
      ) : displayed.length === 0 ? (
        <VAEmptyState
          title="No baselines match your search"
          actionLabel="Clear search"
          onAction={() => setSearch("")}
          variant="no-results"
        />
      ) : (
        <>
          <ul className="space-y-2">
            {displayed.map((b) => (
              <li key={b.baseline_id}>
                <Link
                  href={`/baselines/${b.baseline_id}`}
                  className="block cursor-pointer rounded-va-lg border border-va-border bg-va-panel/80 p-4 transition hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
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
