"use client";

import { Nav } from "@/components/nav";
import { VAButton, VACard, VAInput, VASpinner, VAPagination } from "@/components/ui";
import { api, type ActivityItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { useCallback, useEffect, useState } from "react";

const PAGE_SIZE = 20;

export default function ActivityPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [items, setItems] = useState<ActivityItem[]>([]);
  const [filters, setFilters] = useState({
    user_id: "",
    resource_type: "",
    resource_id: "",
    since: "",
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const load = useCallback(async () => {
    if (!tenantId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.activity.list(tenantId, {
        user_id: filters.user_id || undefined,
        resource_type: filters.resource_type || undefined,
        resource_id: filters.resource_id || undefined,
        since: filters.since || undefined,
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
      });
      setItems(res.items ?? []);
      setTotal(res.total);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, filters, page]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
    })();
  }, []);

  useEffect(() => {
    if (tenantId) load();
  }, [tenantId, load]);

  useEffect(() => {
    setPage(1);
  }, [filters]);

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Activity Feed
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Recent actions across your tenant with filters by user and entity.
          </p>
        </div>

        <VACard className="mb-4 p-4">
          <div className="grid gap-3 md:grid-cols-4">
            <VAInput
              placeholder="User ID"
              value={filters.user_id}
              onChange={(e) =>
                setFilters((prev) => ({ ...prev, user_id: e.target.value }))
              }
            />
            <VAInput
              placeholder="Resource type"
              value={filters.resource_type}
              onChange={(e) =>
                setFilters((prev) => ({
                  ...prev,
                  resource_type: e.target.value,
                }))
              }
            />
            <VAInput
              placeholder="Resource ID"
              value={filters.resource_id}
              onChange={(e) =>
                setFilters((prev) => ({ ...prev, resource_id: e.target.value }))
              }
            />
            <VAInput
              type="datetime-local"
              value={filters.since}
              onChange={(e) =>
                setFilters((prev) => ({ ...prev, since: e.target.value }))
              }
            />
          </div>
          <VAButton className="mt-3" onClick={load}>
            Apply filters
          </VAButton>
        </VACard>

        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        {loading ? (
          <VASpinner label="Loading activity…" />
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No activity recorded yet. Actions across your workspace will appear here.
          </VACard>
        ) : (
          <>
            <div className="space-y-3">
              {items.map((item) => (
                <VACard key={item.id} className="p-4">
                  <div className="flex items-center justify-between text-sm text-va-text2">
                    <span>{item.type.toUpperCase()}</span>
                    <span>
                      {formatDateTime(item.timestamp)}
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-va-text">
                    {item.summary}
                  </p>
                  <p className="mt-1 text-xs text-va-text2">
                    {item.resource_type} {item.resource_id}
                  </p>
                </VACard>
              ))}
            </div>
            <VAPagination
              page={page}
              pageSize={PAGE_SIZE}
              total={total}
              onPageChange={setPage}
            />
          </>
        )}
      </main>
    </div>
  );
}
