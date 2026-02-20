"use client";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { createClient } from "@/lib/supabase/client";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const baseClass =
  "text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded px-1 block py-2";

const navLinks = [
  { href: "/baselines", label: "Baselines" },
  { href: "/drafts", label: "Drafts" },
  { href: "/runs", label: "Runs" },
  { href: "/scenarios", label: "Scenarios" },
  { href: "/changesets", label: "Changesets" },
  { href: "/budgets", label: "Budgets" },
  { href: "/covenants", label: "Covenants" },
  { href: "/memos", label: "Memos" },
  { href: "/documents", label: "Documents" },
  { href: "/board-packs", label: "Board packs" },
  { href: "/excel-import", label: "Import Excel" },
  { href: "/org-structures", label: "Groups" },
  { href: "/marketplace", label: "Marketplace" },
  { href: "/dashboard", label: "Dashboard" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const router = useRouter();
  const pathname = usePathname();
  const [unreadCount, setUnreadCount] = useState<number>(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  function linkClass(href: string) {
    const active = pathname === href || pathname.startsWith(href + "/");
    return `${baseClass} ${active ? "text-va-blue" : "text-va-text hover:text-va-text2"}`;
  }

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

  return (
    <nav className="border-b border-va-border bg-va-panel/80">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
        <div className="flex items-center gap-6" ref={menuRef}>
          {/* Desktop: horizontal links */}
          <div className="hidden md:flex md:items-center md:gap-4">
            <Link
              href="/baselines"
              className={`flex items-center gap-2 ${linkClass("/baselines")}`}
            >
              <Image src="/va-icon.svg" alt="" width={28} height={28} aria-hidden />
              <span>Baselines</span>
            </Link>
            {navLinks.slice(1).map((item) => (
              <Link key={item.href} href={item.href} className={linkClass(item.href)}>
                {item.label}
              </Link>
            ))}
            <Link
              href="/notifications"
              className={`relative ${linkClass("/notifications")}`}
              aria-label={unreadCount > 0 ? `Notifications, ${unreadCount} unread` : "Notifications"}
            >
              <span aria-hidden>🔔</span>
              {unreadCount > 0 && (
                <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-va-danger px-1 text-[10px] font-medium text-va-text">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
            <Link href="/inbox" className={linkClass("/inbox")}>Inbox</Link>
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
              <div className="absolute left-0 top-full z-20 mt-1 w-56 max-h-[80vh] overflow-y-auto rounded-lg border border-va-border bg-va-panel py-2 shadow-lg">
                {navLinks.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={linkClass(item.href)}
                    onClick={() => setMenuOpen(false)}
                  >
                    {item.label}
                  </Link>
                ))}
                <Link
                  href="/notifications"
                  className={linkClass("/notifications")}
                  onClick={() => setMenuOpen(false)}
                >
                  Notifications {unreadCount > 0 && `(${unreadCount})`}
                </Link>
                <Link
                  href="/inbox"
                  className={linkClass("/inbox")}
                  onClick={() => setMenuOpen(false)}
                >
                  Inbox
                </Link>
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
