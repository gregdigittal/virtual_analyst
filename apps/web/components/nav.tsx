"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const navLinkClass =
  "text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1 block py-2";

export function Nav() {
  const router = useRouter();
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      try {
        const res = await api.notifications.list(ctx.tenantId, ctx.userId, false, 1, 0);
        if (!cancelled) setUnreadCount(res.unread_count);
      } catch {
        if (!cancelled) setUnreadCount(0);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("click", handleClickOutside);
      return () => document.removeEventListener("click", handleClickOutside);
    }
  }, [menuOpen]);

  async function handleSignOut() {
    setMenuOpen(false);
    api.setAccessToken(null);
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/");
    router.refresh();
  }

  const linkProps = { className: navLinkClass, onClick: () => setMenuOpen(false) };

  return (
    <nav className="border-b border-va-border bg-va-panel/80">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6" ref={menuRef}>
          {/* Desktop: full horizontal links */}
          <div className="hidden md:flex md:items-center md:gap-6">
            <Link href="/baselines" className="flex items-center gap-2 text-sm font-medium text-va-text hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded">
              <Image src="/va-icon.svg" alt="" width={28} height={28} aria-hidden />
              <span>Baselines</span>
            </Link>
            <Link href="/drafts" className={navLinkClass}>Drafts</Link>
            <Link href="/excel-import" className={navLinkClass}>Import Excel Model</Link>
            <Link href="/org-structures" className={navLinkClass}>Group Structures</Link>
            <Link href="/runs" className={navLinkClass}>Runs</Link>
            <Link href="/scenarios" className={navLinkClass}>Scenarios</Link>
            <Link href="/budgets" className={navLinkClass}>Budgets</Link>
            <Link href="/board-packs" className={navLinkClass}>Board packs</Link>
            <Link href="/dashboard" className={navLinkClass}>Dashboard</Link>
            <Link href="/notifications" className={`relative ${navLinkClass}`} aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}>
              <span aria-hidden>🔔</span>
              {unreadCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-va-danger px-1 text-[10px] font-medium text-va-text">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
            <Link href="/settings/teams" className={navLinkClass}>Teams</Link>
            <Link href="/inbox" className={navLinkClass}>Inbox</Link>
            <Link href="/inbox/feedback" className={navLinkClass}>Feedback</Link>
          </div>

          {/* Mobile: hamburger + dropdown */}
          <div className="relative md:hidden flex items-center">
            <button
              type="button"
              onClick={() => setMenuOpen((o) => !o)}
              className="flex h-10 w-10 items-center justify-center rounded text-va-text hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue"
              aria-expanded={menuOpen}
              aria-label={menuOpen ? "Close menu" : "Open menu"}
            >
              {menuOpen ? (
                <span className="text-lg leading-none" aria-hidden>✕</span>
              ) : (
                <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
            {menuOpen && (
              <div className="absolute left-0 top-full z-20 mt-1 w-56 rounded-lg border border-va-border bg-va-panel py-2 shadow-lg">
                <Link href="/baselines" {...linkProps}>Baselines</Link>
                <Link href="/drafts" {...linkProps}>Drafts</Link>
                <Link href="/excel-import" {...linkProps}>Import Excel Model</Link>
                <Link href="/org-structures" {...linkProps}>Group Structures</Link>
                <Link href="/runs" {...linkProps}>Runs</Link>
                <Link href="/scenarios" {...linkProps}>Scenarios</Link>
                <Link href="/budgets" {...linkProps}>Budgets</Link>
                <Link href="/board-packs" {...linkProps}>Board packs</Link>
                <Link href="/dashboard" {...linkProps}>Dashboard</Link>
                <Link href="/notifications" {...linkProps} className={`relative ${navLinkClass}`}>
                  Notifications {unreadCount > 0 && `(${unreadCount})`}
                </Link>
                <Link href="/settings/teams" {...linkProps}>Teams</Link>
                <Link href="/inbox" {...linkProps}>Inbox</Link>
                <Link href="/inbox/feedback" {...linkProps}>Feedback</Link>
              </div>
            )}
          </div>
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
