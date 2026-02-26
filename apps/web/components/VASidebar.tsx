"use client";

import { api } from "@/lib/api";
import { getAuthContext, signOut } from "@/lib/auth";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

// ──────────────────────────────────────────────
// Navigation data
// ──────────────────────────────────────────────

interface NavItem {
  href: string;
  label: string;
  icon: string;
}

interface NavGroup {
  key: string;
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    key: "setup",
    label: "SETUP",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: "grid" },
      { href: "/marketplace", label: "Marketplace", icon: "store" },
      { href: "/excel-import", label: "Import Excel", icon: "upload" },
      { href: "/org-structures", label: "Groups", icon: "users" },
    ],
  },
  {
    key: "configure",
    label: "CONFIGURE",
    items: [
      { href: "/baselines", label: "Baselines", icon: "layers" },
      { href: "/drafts", label: "Drafts", icon: "edit" },
      { href: "/scenarios", label: "Scenarios", icon: "git-branch" },
    ],
  },
  {
    key: "analyze",
    label: "ANALYZE",
    items: [
      { href: "/runs", label: "Runs", icon: "play" },
      { href: "/budgets", label: "Budgets", icon: "dollar" },
      { href: "/covenants", label: "Covenants", icon: "shield" },
    ],
  },
  {
    key: "report",
    label: "REPORT",
    items: [
      { href: "/board-packs", label: "Board Packs", icon: "briefcase" },
      { href: "/memos", label: "Memos", icon: "file-text" },
      { href: "/documents", label: "Documents", icon: "folder" },
    ],
  },
];

const UTILITY_ITEMS: NavItem[] = [
  { href: "/workflows", label: "Workflows", icon: "workflow" },
  { href: "/changesets", label: "Changesets", icon: "diff" },
  { href: "/inbox", label: "Inbox", icon: "inbox" },
  { href: "/notifications", label: "Notifications", icon: "bell" },
  { href: "/settings", label: "Settings", icon: "settings" },
];

// ──────────────────────────────────────────────
// Simple icon component (SVG inline icons)
// ──────────────────────────────────────────────

function NavIcon({ name, className = "" }: { name: string; className?: string }) {
  const base = `shrink-0 ${className}`;
  const props = { className: base, width: 18, height: 18, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

  switch (name) {
    case "grid":
      return <svg {...props}><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></svg>;
    case "store":
      return <svg {...props}><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg>;
    case "upload":
      return <svg {...props}><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>;
    case "users":
      return <svg {...props}><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4-4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87" /><path d="M16 3.13a4 4 0 010 7.75" /></svg>;
    case "layers":
      return <svg {...props}><polygon points="12 2 2 7 12 12 22 7 12 2" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg>;
    case "edit":
      return <svg {...props}><path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>;
    case "git-branch":
      return <svg {...props}><line x1="6" y1="3" x2="6" y2="15" /><circle cx="18" cy="6" r="3" /><circle cx="6" cy="18" r="3" /><path d="M18 9a9 9 0 01-9 9" /></svg>;
    case "play":
      return <svg {...props}><polygon points="5 3 19 12 5 21 5 3" /></svg>;
    case "dollar":
      return <svg {...props}><line x1="12" y1="1" x2="12" y2="23" /><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6" /></svg>;
    case "shield":
      return <svg {...props}><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" /></svg>;
    case "briefcase":
      return <svg {...props}><rect x="2" y="7" width="20" height="14" rx="2" ry="2" /><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16" /></svg>;
    case "file-text":
      return <svg {...props}><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" /><polyline points="10 9 9 9 8 9" /></svg>;
    case "folder":
      return <svg {...props}><path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" /></svg>;
    case "workflow":
      return <svg {...props}><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
    case "diff":
      return <svg {...props}><path d="M12 3v18" /><path d="M18 9l-6-6-6 6" /><path d="M6 15l6 6 6-6" /></svg>;
    case "inbox":
      return <svg {...props}><polyline points="22 12 16 12 14 15 10 15 8 12 2 12" /><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z" /></svg>;
    case "bell":
      return <svg {...props}><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 01-3.46 0" /></svg>;
    case "settings":
      return <svg {...props}><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" /></svg>;
    case "chevron-down":
      return <svg {...props}><polyline points="6 9 12 15 18 9" /></svg>;
    case "chevron-right":
      return <svg {...props}><polyline points="9 18 15 12 9 6" /></svg>;
    case "panel-left-close":
      return <svg {...props}><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" /><path d="M16 15l-3-3 3-3" /></svg>;
    case "panel-left-open":
      return <svg {...props}><rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 3v18" /><path d="M14 9l3 3-3 3" /></svg>;
    case "log-out":
      return <svg {...props}><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>;
    default:
      return <svg {...props}><circle cx="12" cy="12" r="10" /></svg>;
  }
}

// ──────────────────────────────────────────────
// VASidebar component
// ──────────────────────────────────────────────

export function VASidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return localStorage.getItem("va-sidebar-collapsed") === "true";
  });
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(() => {
    if (typeof window === "undefined") return {};
    try { return JSON.parse(localStorage.getItem("va-sidebar-groups") ?? "{}"); } catch { return {}; }
  });
  const [unreadCount, setUnreadCount] = useState<number>(0);

  // Fetch notification count
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

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(href + "/");
  }

  function linkClass(href: string) {
    const active = isActive(href);
    return [
      "flex items-center gap-3 rounded-va-xs px-3 py-1.5 text-sm font-medium transition-colors",
      "focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue",
      active
        ? "text-va-blue bg-va-blue/10"
        : "text-va-text hover:text-va-text2 hover:bg-white/5",
      collapsed ? "justify-center px-0" : "",
    ].join(" ");
  }

  function toggleGroup(key: string) {
    setCollapsedGroups((prev) => {
      const next = { ...prev, [key]: !prev[key] };
      localStorage.setItem("va-sidebar-groups", JSON.stringify(next));
      return next;
    });
  }

  async function handleSignOut() {
    api.setAccessToken(null);
    await signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <nav
      className={`flex flex-col border-r border-va-border bg-va-panel/80 transition-all duration-200 ${
        collapsed ? "w-16" : "w-56"
      }`}
      aria-label="Main navigation"
    >
      {/* Logo */}
      <div className="flex h-14 shrink-0 items-center border-b border-va-border px-4">
        <Link
          href="/baselines"
          className="flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-xs"
        >
          <Image src="/va-icon.svg" alt="Virtual Analyst" width={28} height={28} />
          {!collapsed && (
            <span className="font-brand text-sm font-semibold text-va-text">
              VA
            </span>
          )}
        </Link>
      </div>

      {/* Scrollable nav area */}
      <div className="flex-1 overflow-y-auto px-2 py-3">
        {/* Workflow groups */}
        {NAV_GROUPS.map((group) => {
          const isGroupCollapsed = collapsedGroups[group.key] ?? false;
          return (
            <div key={group.key} className="mb-3">
              <button
                type="button"
                onClick={() => toggleGroup(group.key)}
                className={[
                  "flex w-full items-center gap-2 rounded-va-xs px-3 py-1 text-[11px] font-semibold tracking-wider text-va-muted",
                  "hover:text-va-text2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue",
                  collapsed ? "justify-center px-0" : "",
                ].join(" ")}
                aria-expanded={!isGroupCollapsed}
                aria-label={group.label}
              >
                {!collapsed && (
                  <>
                    <span>{group.label}</span>
                    <NavIcon
                      name={isGroupCollapsed ? "chevron-right" : "chevron-down"}
                      className="ml-auto h-3 w-3"
                    />
                  </>
                )}
                {collapsed && (
                  <span className="text-[9px]" aria-hidden="true">
                    {group.label.slice(0, 2)}
                  </span>
                )}
              </button>
              <div
                className="mt-1 flex flex-col gap-0.5"
                hidden={isGroupCollapsed}
              >
                {group.items.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={linkClass(item.href)}
                    title={collapsed ? item.label : undefined}
                    aria-current={isActive(item.href) ? "page" : undefined}
                  >
                    <NavIcon name={item.icon} className="h-4 w-4" />
                    {!collapsed && <span>{item.label}</span>}
                  </Link>
                ))}
              </div>
            </div>
          );
        })}

        {/* Divider */}
        <div className="my-3 border-t border-va-border" />

        {/* Utility items */}
        <div className="flex flex-col gap-0.5">
          {UTILITY_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`relative ${linkClass(item.href)}`}
              title={collapsed ? item.label : undefined}
              aria-current={isActive(item.href) ? "page" : undefined}
              aria-label={
                item.href === "/notifications" && unreadCount > 0
                  ? `Notifications, ${unreadCount} unread`
                  : undefined
              }
            >
              <NavIcon name={item.icon} className="h-4 w-4" />
              {!collapsed && <span>{item.label}</span>}
              {item.href === "/notifications" && unreadCount > 0 && (
                <span className="absolute right-2 top-1/2 -translate-y-1/2 flex h-4 min-w-4 items-center justify-center rounded-full bg-va-danger px-1 text-[10px] font-medium text-va-text">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
          ))}
        </div>
      </div>

      {/* Bottom controls */}
      <div className="shrink-0 border-t border-va-border px-2 py-2 flex flex-col gap-1">
        {/* Collapse / Expand toggle */}
        <button
          type="button"
          onClick={() => setCollapsed((c) => {
            const next = !c;
            localStorage.setItem("va-sidebar-collapsed", String(next));
            return next;
          })}
          className={[
            "flex items-center gap-3 rounded-va-xs px-3 py-1.5 text-sm font-medium text-va-text2",
            "hover:text-va-text hover:bg-white/5",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue",
            collapsed ? "justify-center px-0" : "",
          ].join(" ")}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <NavIcon
            name={collapsed ? "panel-left-open" : "panel-left-close"}
            className="h-4 w-4"
          />
          {!collapsed && <span>Collapse</span>}
        </button>

        {/* Sign out */}
        <button
          type="button"
          onClick={handleSignOut}
          className={[
            "flex items-center gap-3 rounded-va-xs px-3 py-1.5 text-sm font-medium text-va-text2",
            "hover:text-va-text hover:bg-white/5",
            "focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue",
            collapsed ? "justify-center px-0" : "",
          ].join(" ")}
          aria-label="Sign out"
        >
          <NavIcon name="log-out" className="h-4 w-4" />
          {!collapsed && <span>Sign out</span>}
        </button>
      </div>
    </nav>
  );
}
