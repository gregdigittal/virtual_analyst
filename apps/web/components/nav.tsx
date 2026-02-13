"use client";

import { api } from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function Nav() {
  const router = useRouter();
  const [unreadCount, setUnreadCount] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.user?.id) return;
      try {
        const res = await api.notifications.list(session.user.id, false, 1, 0);
        if (!cancelled) setUnreadCount(res.unread_count);
      } catch {
        if (!cancelled) setUnreadCount(0);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <nav className="border-b border-border bg-card">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link
            href="/baselines"
            className="text-sm font-medium text-foreground hover:text-muted-foreground"
          >
            Baselines
          </Link>
          <Link
            href="/drafts"
            className="text-sm font-medium text-foreground hover:text-muted-foreground"
          >
            Drafts
          </Link>
          <Link
            href="/runs"
            className="text-sm font-medium text-foreground hover:text-muted-foreground"
          >
            Runs
          </Link>
          <Link
            href="/dashboard"
            className="text-sm font-medium text-foreground hover:text-muted-foreground"
          >
            Dashboard
          </Link>
          <Link
            href="/notifications"
            className="relative text-sm font-medium text-foreground hover:text-muted-foreground"
            aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
          >
            <span aria-hidden>🔔</span>
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-600 px-1 text-[10px] font-medium text-white">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </Link>
        </div>
        <button
          type="button"
          onClick={handleSignOut}
          className="text-sm font-medium text-muted-foreground hover:text-foreground"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
