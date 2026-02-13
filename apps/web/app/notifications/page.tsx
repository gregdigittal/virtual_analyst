"use client";

import { api, type NotificationItem } from "@/lib/api";
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
        const res = await api.notifications.list(tid, false, 50, 0);
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
    if (!tenantId) return;
    try {
      await api.notifications.markRead(tenantId, id);
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
    <div className="min-h-screen bg-background">
      <Nav />
      <main className="mx-auto max-w-2xl px-4 py-8">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-semibold tracking-tight">
            Notifications
          </h1>
          {unreadCount > 0 && (
            <span className="text-sm text-muted-foreground">
              {unreadCount} unread
            </span>
          )}
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
          <p className="text-muted-foreground">Loading…</p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-border bg-card p-6 text-center text-muted-foreground">
            No notifications yet. Notifications are created when a draft is
            marked ready to commit or when a run completes.
          </div>
        ) : (
          <ul className="space-y-2">
            {items.map((n) => (
              <li
                key={n.id}
                className={`rounded-lg border border-border bg-card p-4 ${
                  n.read_at ? "opacity-75" : ""
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-foreground">{n.title}</p>
                    {n.body && (
                      <p className="mt-1 text-sm text-muted-foreground">
                        {n.body}
                      </p>
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
                        className="mt-2 inline-block text-sm text-blue-600 hover:underline"
                      >
                        View →
                      </Link>
                    )}
                    {n.created_at && (
                      <p className="mt-1 text-xs text-muted-foreground">
                        {new Date(n.created_at).toLocaleString()}
                      </p>
                    )}
                  </div>
                  {!n.read_at && (
                    <button
                      type="button"
                      onClick={() => markRead(n.id)}
                      className="shrink-0 rounded border border-border px-2 py-1 text-xs font-medium hover:bg-muted"
                    >
                      Mark read
                    </button>
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
