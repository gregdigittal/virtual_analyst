"use client";

import { api, type NotificationItem } from "@/lib/api";
import { VAButton, VACard } from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useEffect, useState } from "react";

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user?.id) return;
      const tid =
        (user.app_metadata?.tenant_id as string) ??
        (user.user_metadata?.tenant_id as string) ??
        user.id;
      setTenantId(tid);
      setUserId(user.id);
      try {
        const res = await api.notifications.list(tid, user.id, false, 50, 0);
        if (!cancelled) {
          setItems(res.items);
          setUnreadCount(res.unread_count);
        }
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
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Notifications
          </h1>
          {unreadCount > 0 && (
            <span className="text-sm text-va-text2">{unreadCount} unread</span>
          )}
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
          <p className="text-va-text2">Loading…</p>
        ) : items.length === 0 ? (
          <VACard className="p-6 text-center text-va-text2">
            No notifications yet. Notifications are created when a draft is
            marked ready to commit or when a run completes.
          </VACard>
        ) : (
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
                        {new Date(n.created_at).toLocaleString()}
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
        )}
      </main>
    </div>
  );
}
