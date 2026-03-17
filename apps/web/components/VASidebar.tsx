"use client";

import { NavIcon } from "@/components/ui/NavIcon";
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
    key: "afs",
    label: "AFS",
    items: [
      { href: "/afs",            label: "Engagements", icon: "file-text" },
      { href: "/afs/frameworks", label: "Frameworks",  icon: "folder"    },
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
    key: "intelligence",
    label: "INTELLIGENCE",
    items: [
      { href: "/pim",           label: "Overview",  icon: "layers"     },
      { href: "/pim/sentiment", label: "Sentiment", icon: "play"       },
      { href: "/pim/universe",  label: "Universe",  icon: "store"      },
      { href: "/pim/economic",  label: "Economic",  icon: "workflow"   },
      { href: "/pim/markov",    label: "Markov",    icon: "layers"     },
      { href: "/pim/backtest",  label: "Backtest",  icon: "git-branch" },
      { href: "/pim/pe",        label: "PE",        icon: "dollar"     },
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
// VASidebar component
// ──────────────────────────────────────────────

interface VASidebarProps {
  mobileOpen?: boolean;
  onClose?: () => void;
}

export function VASidebar({ mobileOpen, onClose }: VASidebarProps = {}) {
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
    <>
      {mobileOpen && onClose && (
        <div
          data-testid="mobile-backdrop"
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={onClose}
        />
      )}
      <nav
        className={[
          "flex flex-col border-r border-va-border bg-va-panel/80 transition-all duration-200",
          collapsed ? "w-16" : "w-56",
          mobileOpen != null
            ? mobileOpen
              ? "fixed inset-y-0 left-0 z-50 md:relative md:z-auto"
              : "hidden md:flex"
            : "",
        ].join(" ")}
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
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="ml-auto text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-xs p-1"
            aria-label="Close menu"
          >
            <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        )}
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
    </>
  );
}
