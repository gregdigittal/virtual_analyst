"use client";

import { api, type NotificationItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard, VASpinner, VAPagination } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

const PAGE_SIZE = 20;

export default function NotificationsPage() {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = useCallback(async () => {
    if (!tenantId || !userId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.notifications.list(
        tenantId,
        userId,
        unreadOnly,
        PAGE_SIZE,
        (page - 1) * PAGE_SIZE,
      );
      setItems(res.items);
      setUnreadCount(res.unread_count);
      setHasMore(res.items.length === PAGE_SIZE);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, userId, page, unreadOnly]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, [router]);

  useEffect(() => {
    if (tenantId && userId) load();
  }, [tenantId, userId, load]);

  useEffect(() => {
    setPage(1);
  }, [unreadOnly]);

  async function markRead(id: string) {
    if (!tenantId || !userId) return;
    try {
      await api.notifications.markRead(tenantId, userId, id);
      setItems((prev) =>
        prev.map((n) =>
          n.id === id ? { ...n, read_at: new Date().toISOString() } : n
        )
      );
      setUnreadCount((c) => Math.max(0, c - 1));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Notifications
        </h1>
        {unreadCount > 0 && (
          <span className="text-sm text-va-text2">{unreadCount} unread</span>
        )}
      </div>

      <div className="mb-4">
        <label className="inline-flex cursor-pointer items-center gap-2 text-sm text-va-text">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => setUnreadOnly(e.target.checked)}
            className="accent-va-blue"
          />
          Show unread only
        </label>
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
        <VASpinner label="Loading…" />
      ) : items.length === 0 ? (
        <VACard className="p-6 text-center text-va-text2">
          No notifications yet. Notifications are created when a draft is
          marked ready to commit or when a run completes.
        </VACard>
      ) : (
        <>
          <ul className="space-y-2">
            {items.map((n) => (
              <li
                key={n.id}
                className={`rounded-va-lg border border-va-border bg-va-panel/80 p-4 ${
                  n.read_at ? "opacity-75" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-va-text">{n.title}</p>
                    {n.body && (
                      <p className="mt-1 text-sm text-va-text2">{n.body}</p>
                    )}
                    {n.entity_type && n.entity_id && (
                      <Link
                        href={
                          n.entity_type === "draft_session"
                            ? `/drafts/${n.entity_id}`
                            : n.entity_type === "run"
                              ? `/runs/${n.entity_id}`
                              : "#"
                        }
                        className="mt-2 inline-block text-sm text-va-blue hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
                      >
                        View →
                      </Link>
                    )}
                    {n.created_at && (
                      <p className="mt-1 text-xs text-va-text2">
                        {formatDateTime(n.created_at)}
                      </p>
                    )}
                  </div>
                  {!n.read_at && (
                    <VAButton
                      type="button"
                      variant="secondary"
                      onClick={() => markRead(n.id)}
                      className="shrink-0 !py-1 !text-xs"
                    >
                      Mark read
                    </VAButton>
                  )}
                </div>
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
