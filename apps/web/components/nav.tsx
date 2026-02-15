"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export function Nav() {
  const router = useRouter();
  const [unreadCount, setUnreadCount] = useState<number>(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      try {
        const res = await api.notifications.list(ctx.tenantId, false, 1, 0);
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
    api.setAccessToken(null);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <nav className="border-b border-va-border bg-va-panel/80">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6">
          <Link
            href="/baselines"
            className="flex items-center gap-2 text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
          >
            <Image
              src="/va-icon.svg"
              alt=""
              width={28}
              height={28}
              className="hidden sm:block"
              aria-hidden
            />
            <span>Baselines</span>
          </Link>
          <Link
            href="/drafts"
            className="text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
          >
            Drafts
          </Link>
          <Link
            href="/runs"
            className="text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
          >
            Runs
          </Link>
          <Link
            href="/scenarios"
            className="text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
          >
            Scenarios
          </Link>
          <Link
            href="/dashboard"
            className="text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
          >
            Dashboard
          </Link>
          <Link
            href="/notifications"
            className="relative text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
            aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ""}`}
          >
            <span aria-hidden>🔔</span>
            {unreadCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-va-danger px-1 text-[10px] font-medium text-va-text">
                {unreadCount > 99 ? "99+" : unreadCount}
              </span>
            )}
          </Link>
          <Link
            href="/settings/teams"
            className="text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
          >
            Teams
          </Link>
          <Link
            href="/inbox"
            className="text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
          >
            Inbox
          </Link>
          <Link
            href="/inbox/feedback"
            className="text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1"
          >
            Feedback
          </Link>
        </div>
        <button
          type="button"
          onClick={handleSignOut}
          className="text-sm font-medium text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-2 py-1"
        >
          Sign out
        </button>
      </div>
    </nav>
  );
}
