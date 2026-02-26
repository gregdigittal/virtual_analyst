# UI/UX Overhaul Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restructure Virtual Analyst's navigation from a flat horizontal bar to a grouped vertical sidebar with workflow progress stepper, expand the template system, and remodel the landing page.

**Architecture:** Replace the current horizontal `<Nav />` component (imported per-page) with a persistent `<VASidebar />` rendered in a shared authenticated route-group layout `(app)/layout.tsx`. Add a `<ModelStepper />` component that renders contextually on baseline/draft/run pages. Expand the marketplace with new templates and AI detection. Remodel the landing page with new hero, feature showcase, and comparison page.

**Tech Stack:** Next.js 14 App Router, React 18, Tailwind CSS with VA design tokens, Vitest + React Testing Library, Python FastAPI backend, Supabase/PostgreSQL.

---

## Task 1: Create VASidebar Component

**Files:**
- Create: `apps/web/components/VASidebar.tsx`
- Create: `apps/web/tests/components/sidebar.test.tsx`
- Modify: `apps/web/components/ui/index.ts:1-13` (add export)

**Context:** The current nav is a horizontal bar in `components/nav.tsx` with 16+ flat links. We are replacing it with a vertical sidebar grouped into 4 workflow stages (Setup, Configure, Analyze, Report) plus utility items. The sidebar collapses to icon-only rail mode. Mobile uses a slide-out drawer.

**Step 1: Write the failing test**

Create `apps/web/tests/components/sidebar.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { VASidebar } from "@/components/VASidebar";

// Mock next/navigation
const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/baselines",
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

vi.mock("next/image", () => ({
  __esModule: true,
  default: (props: Record<string, unknown>) => <img {...props} />,
}));

vi.mock("@/lib/auth", () => ({
  getAuthContext: vi.fn(async () => ({
    tenantId: "t-1", userId: "u-1", accessToken: "tok", tenantIdIsFallback: false,
  })),
  signOut: vi.fn(async () => {}),
}));

vi.mock("@/lib/api", () => ({
  api: {
    setAccessToken: vi.fn(),
    notifications: { list: vi.fn(async () => ({ items: [], total: 0, unread_count: 0 })) },
  },
}));

describe("VASidebar", () => {
  it("renders all four workflow group headings", () => {
    render(<VASidebar />);
    expect(screen.getByText("SETUP")).toBeInTheDocument();
    expect(screen.getByText("CONFIGURE")).toBeInTheDocument();
    expect(screen.getByText("ANALYZE")).toBeInTheDocument();
    expect(screen.getByText("REPORT")).toBeInTheDocument();
  });

  it("renders navigation links in correct groups", () => {
    render(<VASidebar />);
    expect(screen.getByRole("link", { name: /Dashboard/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Marketplace/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Import Excel/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Baselines/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Runs/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Board Packs/i })).toBeInTheDocument();
  });

  it("highlights active link based on pathname", () => {
    render(<VASidebar />);
    const baselinesLink = screen.getByRole("link", { name: /Baselines/i });
    expect(baselinesLink.className).toContain("text-va-blue");
  });

  it("toggles group collapse on header click", () => {
    render(<VASidebar />);
    const setupHeader = screen.getByText("SETUP");
    const dashboard = screen.getByRole("link", { name: /Dashboard/i });
    expect(dashboard).toBeVisible();
    fireEvent.click(setupHeader);
    expect(dashboard).not.toBeVisible();
    fireEvent.click(setupHeader);
    expect(dashboard).toBeVisible();
  });

  it("renders sign out button", () => {
    render(<VASidebar />);
    expect(screen.getByRole("button", { name: /Sign out/i })).toBeInTheDocument();
  });

  it("toggles rail mode (collapsed sidebar)", () => {
    render(<VASidebar />);
    const collapseBtn = screen.getByRole("button", { name: /Collapse sidebar/i });
    fireEvent.click(collapseBtn);
    // In rail mode, group headings are hidden
    expect(screen.queryByText("SETUP")).not.toBeVisible();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/web" && npx vitest run tests/components/sidebar.test.tsx --reporter=verbose`
Expected: FAIL — `VASidebar` module not found

**Step 3: Write the VASidebar component**

Create `apps/web/components/VASidebar.tsx`:

```tsx
"use client";

import { api } from "@/lib/api";
import { getAuthContext, signOut } from "@/lib/auth";
import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

interface NavItem {
  href: string;
  label: string;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const workflowGroups: NavGroup[] = [
  {
    label: "SETUP",
    items: [
      { href: "/dashboard", label: "Dashboard" },
      { href: "/marketplace", label: "Marketplace" },
      { href: "/excel-import", label: "Import Excel" },
      { href: "/org-structures", label: "Groups" },
    ],
  },
  {
    label: "CONFIGURE",
    items: [
      { href: "/baselines", label: "Baselines" },
      { href: "/drafts", label: "Drafts" },
      { href: "/scenarios", label: "Scenarios" },
    ],
  },
  {
    label: "ANALYZE",
    items: [
      { href: "/runs", label: "Runs" },
      { href: "/budgets", label: "Budgets" },
      { href: "/covenants", label: "Covenants" },
    ],
  },
  {
    label: "REPORT",
    items: [
      { href: "/board-packs", label: "Board Packs" },
      { href: "/memos", label: "Memos" },
      { href: "/documents", label: "Documents" },
    ],
  },
];

const utilityItems: NavItem[] = [
  { href: "/workflows", label: "Workflows" },
  { href: "/changesets", label: "Changesets" },
  { href: "/inbox", label: "Inbox" },
  { href: "/notifications", label: "Notifications" },
  { href: "/settings", label: "Settings" },
];

export function VASidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
  const [unreadCount, setUnreadCount] = useState(0);

  function isActive(href: string) {
    return pathname === href || pathname.startsWith(href + "/");
  }

  function linkClass(href: string) {
    const active = isActive(href);
    return `flex items-center gap-3 rounded-va-xs px-3 py-2 text-sm font-medium transition-colors ${
      active
        ? "bg-va-blue/10 text-va-blue"
        : "text-va-text2 hover:bg-white/5 hover:text-va-text"
    } focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue`;
  }

  function toggleGroup(label: string) {
    setCollapsedGroups((prev) => ({ ...prev, [label]: !prev[label] }));
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
    return () => { cancelled = true; };
  }, []);

  async function handleSignOut() {
    api.setAccessToken(null);
    await signOut();
    router.push("/");
    router.refresh();
  }

  return (
    <aside
      className={`flex h-screen flex-col border-r border-va-border bg-va-panel/80 transition-all ${
        collapsed ? "w-16" : "w-56"
      }`}
    >
      {/* Logo + collapse toggle */}
      <div className="flex h-14 items-center justify-between border-b border-va-border px-3">
        <Link href="/baselines" className="flex items-center gap-2">
          <Image src="/va-icon.svg" alt="Virtual Analyst" width={28} height={28} />
          {!collapsed && (
            <span className="font-brand text-sm font-semibold text-va-text">VA</span>
          )}
        </Link>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="flex h-7 w-7 items-center justify-center rounded text-va-text2 hover:bg-white/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue"
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {collapsed ? (
              <path strokeLinecap="round" strokeLinejoin="round" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            )}
          </svg>
        </button>
      </div>

      {/* Scrollable nav */}
      <nav className="flex-1 overflow-y-auto px-2 py-3" aria-label="Main navigation">
        {workflowGroups.map((group) => (
          <div key={group.label} className="mb-2">
            <button
              type="button"
              onClick={() => toggleGroup(group.label)}
              className={`flex w-full items-center justify-between px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-va-muted hover:text-va-text2 ${
                collapsed ? "justify-center" : ""
              }`}
            >
              {!collapsed && <span>{group.label}</span>}
              {!collapsed && (
                <svg
                  className={`h-3 w-3 transition-transform ${collapsedGroups[group.label] ? "-rotate-90" : ""}`}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              )}
            </button>
            {!collapsedGroups[group.label] && (
              <div className="mt-0.5 space-y-0.5">
                {group.items.map((item) => (
                  <Link key={item.href} href={item.href} className={linkClass(item.href)}>
                    {collapsed ? (
                      <span className="text-xs" title={item.label}>
                        {item.label.charAt(0)}
                      </span>
                    ) : (
                      <span>{item.label}</span>
                    )}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Divider */}
        <div className="my-3 border-t border-va-border" />

        {/* Utility items */}
        <div className="space-y-0.5">
          {utilityItems.map((item) => (
            <Link key={item.href} href={item.href} className={linkClass(item.href)}>
              {collapsed ? (
                <span className="text-xs" title={item.label}>{item.label.charAt(0)}</span>
              ) : (
                <span className="flex-1">{item.label}</span>
              )}
              {item.href === "/notifications" && unreadCount > 0 && !collapsed && (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-va-danger px-1 text-[10px] font-medium text-va-text">
                  {unreadCount > 99 ? "99+" : unreadCount}
                </span>
              )}
            </Link>
          ))}
        </div>
      </nav>

      {/* Sign out */}
      <div className="border-t border-va-border px-2 py-3">
        <button
          type="button"
          onClick={handleSignOut}
          className="flex w-full items-center gap-3 rounded-va-xs px-3 py-2 text-sm font-medium text-va-text2 hover:bg-white/5 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue"
        >
          {collapsed ? (
            <span className="text-xs" title="Sign out">X</span>
          ) : (
            <span>Sign out</span>
          )}
        </button>
      </div>
    </aside>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd "apps/web" && npx vitest run tests/components/sidebar.test.tsx --reporter=verbose`
Expected: 6 tests PASS

**Step 5: Commit**

```bash
git add apps/web/components/VASidebar.tsx apps/web/tests/components/sidebar.test.tsx
git commit -m "feat(nav): add VASidebar component with grouped workflow navigation"
```

---

## Task 2: Create Authenticated Route Group Layout

**Files:**
- Create: `apps/web/app/(app)/layout.tsx`
- Modify: `apps/web/app/layout.tsx` (no changes needed — root layout stays)

**Context:** Currently every authenticated page imports `<Nav />` individually (e.g. `baselines/[id]/page.tsx` line 9). We need a shared layout that wraps authenticated pages with the sidebar. Next.js App Router supports route groups via `(name)` folders — pages inside `(app)/` share the layout without affecting URLs.

**Step 1: Create the authenticated layout**

Create `apps/web/app/(app)/layout.tsx`:

```tsx
import { VASidebar } from "@/components/VASidebar";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-screen overflow-hidden">
      <VASidebar />
      <main className="flex-1 overflow-y-auto">
        {children}
      </main>
    </div>
  );
}
```

**Step 2: Move authenticated pages into the route group**

Move each authenticated page directory into `(app)/`:

```bash
# From apps/web/app/ directory:
mkdir -p "(app)"
# Move all authenticated route folders:
mv baselines "(app)/"
mv drafts "(app)/"
mv runs "(app)/"
mv scenarios "(app)/"
mv changesets "(app)/"
mv budgets "(app)/"
mv workflows "(app)/"
mv covenants "(app)/"
mv memos "(app)/"
mv documents "(app)/"
mv board-packs "(app)/"
mv excel-import "(app)/"
mv org-structures "(app)/"
mv marketplace "(app)/"
mv dashboard "(app)/"
mv settings "(app)/"
mv notifications "(app)/"
mv inbox "(app)/"
mv assignments "(app)/"
```

Keep these at root (NOT in route group — they are public/unauthenticated):
- `app/page.tsx` (landing page)
- `app/login/`
- `app/signup/`
- `app/layout.tsx` (root layout)

**Step 3: Remove `<Nav />` import and usage from every page that has it**

In every page that currently has:
```tsx
import { Nav } from "@/components/nav";
// ...
<Nav />
```

Remove both the import and the `<Nav />` JSX element. The sidebar now comes from `(app)/layout.tsx`.

Also remove the outer `<div className="min-h-screen bg-va-midnight">` wrapper from each page since the layout handles that now. Each page's content should start with its `<main>` or content directly.

**Key pages to update** (search for `import { Nav }` to find all):
- `apps/web/app/(app)/baselines/[id]/page.tsx`
- `apps/web/app/(app)/baselines/page.tsx`
- `apps/web/app/(app)/drafts/[id]/page.tsx`
- `apps/web/app/(app)/runs/[id]/page.tsx`
- `apps/web/app/(app)/dashboard/page.tsx`
- ... and all other pages that import Nav

**Step 4: Run all existing tests**

Run: `cd "apps/web" && npx vitest run --reporter=verbose`
Expected: All existing tests PASS (test imports use `@/` aliases, not relative paths, so moves don't break them)

**Step 5: Commit**

```bash
git add -A
git commit -m "feat(nav): create authenticated route group layout with VASidebar"
```

---

## Task 3: Create ModelStepper Component

**Files:**
- Create: `apps/web/components/ModelStepper.tsx`
- Create: `apps/web/tests/components/model-stepper.test.tsx`

**Context:** A horizontal progress stepper that shows the 7-step model creation flow. Each step derives its completion state from existing data (no new state to store). Steps: Start → Company → Historical → Assumptions → Correlations → Run → Review.

**Step 1: Write the failing test**

Create `apps/web/tests/components/model-stepper.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ModelStepper } from "@/components/ModelStepper";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/baselines/b-1",
  useParams: () => ({ id: "b-1" }),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("ModelStepper", () => {
  it("renders all 7 step labels", () => {
    render(<ModelStepper steps={{}} />);
    expect(screen.getByText("Start")).toBeInTheDocument();
    expect(screen.getByText("Company")).toBeInTheDocument();
    expect(screen.getByText("Historical")).toBeInTheDocument();
    expect(screen.getByText("Assumptions")).toBeInTheDocument();
    expect(screen.getByText("Correlations")).toBeInTheDocument();
    expect(screen.getByText("Run")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
  });

  it("marks completed steps with done state", () => {
    render(
      <ModelStepper
        steps={{
          start: "done",
          company: "done",
          historical: "current",
        }}
      />
    );
    const startStep = screen.getByText("Start").closest("[data-step]");
    expect(startStep?.getAttribute("data-state")).toBe("done");
    const historicalStep = screen.getByText("Historical").closest("[data-step]");
    expect(historicalStep?.getAttribute("data-state")).toBe("current");
  });

  it("marks locked steps", () => {
    render(
      <ModelStepper
        steps={{
          start: "done",
          run: "locked",
          review: "locked",
        }}
      />
    );
    const runStep = screen.getByText("Run").closest("[data-step]");
    expect(runStep?.getAttribute("data-state")).toBe("locked");
  });

  it("renders step links for done and current steps", () => {
    render(
      <ModelStepper
        baselineId="b-1"
        steps={{
          start: "done",
          company: "current",
        }}
      />
    );
    expect(screen.getByText("Start").closest("a")).toHaveAttribute("href");
    expect(screen.getByText("Company").closest("a")).toHaveAttribute("href");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/web" && npx vitest run tests/components/model-stepper.test.tsx --reporter=verbose`
Expected: FAIL — `ModelStepper` module not found

**Step 3: Write the ModelStepper component**

Create `apps/web/components/ModelStepper.tsx`:

```tsx
"use client";

import Link from "next/link";

export type StepState = "done" | "current" | "pending" | "locked";

export interface StepStates {
  start?: StepState;
  company?: StepState;
  historical?: StepState;
  assumptions?: StepState;
  correlations?: StepState;
  run?: StepState;
  review?: StepState;
}

interface StepDef {
  id: keyof StepStates;
  label: string;
  href: (baselineId: string) => string;
}

const STEPS: StepDef[] = [
  { id: "start", label: "Start", href: (id) => `/baselines/${id}` },
  { id: "company", label: "Company", href: (id) => `/baselines/${id}` },
  { id: "historical", label: "Historical", href: (id) => `/documents?baseline=${id}` },
  { id: "assumptions", label: "Assumptions", href: (id) => `/drafts?baseline=${id}` },
  { id: "correlations", label: "Correlations", href: (id) => `/drafts?baseline=${id}&tab=correlations` },
  { id: "run", label: "Run", href: (id) => `/baselines/${id}` },
  { id: "review", label: "Review", href: (id) => `/runs?baseline=${id}` },
];

const stateStyles: Record<StepState, string> = {
  done: "bg-va-success text-white",
  current: "bg-va-blue text-white",
  pending: "bg-va-border text-va-text2",
  locked: "bg-va-border/50 text-va-muted",
};

const stateIcons: Record<StepState, string> = {
  done: "\u2713",
  current: "\u2022",
  pending: "",
  locked: "\uD83D\uDD12",
};

interface ModelStepperProps {
  steps: StepStates;
  baselineId?: string;
}

export function ModelStepper({ steps, baselineId }: ModelStepperProps) {
  return (
    <div className="flex items-center gap-1 overflow-x-auto rounded-va-sm border border-va-border bg-va-panel/60 px-4 py-3">
      {STEPS.map((step, i) => {
        const state: StepState = steps[step.id] ?? "pending";
        const isClickable = baselineId && (state === "done" || state === "current");
        const content = (
          <div
            data-step={step.id}
            data-state={state}
            className="flex flex-col items-center gap-1"
          >
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-medium ${stateStyles[state]}`}
            >
              {stateIcons[state] || String(i + 1)}
            </span>
            <span className={`text-xs font-medium whitespace-nowrap ${
              state === "current" ? "text-va-blue" :
              state === "done" ? "text-va-success" :
              state === "locked" ? "text-va-muted" : "text-va-text2"
            }`}>
              {step.label}
            </span>
          </div>
        );

        return (
          <div key={step.id} className="flex items-center">
            {i > 0 && (
              <div className={`mx-1 h-px w-6 ${
                state === "done" || state === "current" ? "bg-va-blue/40" : "bg-va-border"
              }`} />
            )}
            {isClickable ? (
              <Link href={step.href(baselineId)}>{content}</Link>
            ) : (
              content
            )}
          </div>
        );
      })}
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd "apps/web" && npx vitest run tests/components/model-stepper.test.tsx --reporter=verbose`
Expected: 4 tests PASS

**Step 5: Commit**

```bash
git add apps/web/components/ModelStepper.tsx apps/web/tests/components/model-stepper.test.tsx
git commit -m "feat(stepper): add ModelStepper component with 7-step workflow progress"
```

---

## Task 4: Wire ModelStepper into Baseline Detail Page

**Files:**
- Modify: `apps/web/app/(app)/baselines/[id]/page.tsx`
- Modify: `apps/web/tests/pages/baselines-detail.test.tsx`

**Context:** The baseline detail page currently renders at `baselines/[id]/page.tsx` (will be in `(app)/baselines/[id]/` after Task 2 moves). We need to compute step states from the baseline's data and render the `<ModelStepper />` at the top of the page.

**Step 1: Write the failing test**

Add to `apps/web/tests/pages/baselines-detail.test.tsx`:

```tsx
it("renders the model stepper with Start step done", async () => {
  renderPage();
  await waitFor(() => {
    expect(screen.getByText("Start")).toBeInTheDocument();
    expect(screen.getByText("Company")).toBeInTheDocument();
  });
  // The stepper's Start step should be marked done since baseline exists
  const startStep = screen.getByText("Start").closest("[data-step]");
  expect(startStep?.getAttribute("data-state")).toBe("done");
});
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/web" && npx vitest run tests/pages/baselines-detail.test.tsx --reporter=verbose`
Expected: FAIL — "Start" text not found (stepper not yet rendered)

**Step 3: Add ModelStepper to the baseline page**

In `apps/web/app/(app)/baselines/[id]/page.tsx`:

Add import at top:
```tsx
import { ModelStepper, type StepStates } from "@/components/ModelStepper";
```

Add a function to compute step states from the config data:
```tsx
function computeStepStates(config: unknown): StepStates {
  const c = config as Record<string, unknown> | null;
  if (!c) return {};
  const meta = c.metadata as Record<string, unknown> | undefined;
  const assumptions = c.assumptions as Record<string, unknown> | undefined;
  const correlations = c.correlation_matrix as unknown[] | undefined;

  const hasEntity = Boolean(meta?.entity_name);
  const hasRevenue = Array.isArray((assumptions?.revenue_streams)) && (assumptions.revenue_streams as unknown[]).length > 0;
  const hasFunding = assumptions?.funding && typeof assumptions.funding === "object";
  const hasFundingItems = hasFunding && (
    Array.isArray((assumptions.funding as Record<string, unknown>).debt_facilities) &&
    ((assumptions.funding as Record<string, unknown>).debt_facilities as unknown[]).length > 0 ||
    Array.isArray((assumptions.funding as Record<string, unknown>).equity_raises) &&
    ((assumptions.funding as Record<string, unknown>).equity_raises as unknown[]).length > 0
  );
  const hasCorrelations = Array.isArray(correlations) && correlations.length > 0;

  return {
    start: "done",
    company: hasEntity ? "done" : "current",
    historical: hasEntity ? (hasRevenue ? "done" : "current") : "pending",
    assumptions: hasRevenue && hasFundingItems ? "done" : hasEntity ? "current" : "pending",
    correlations: hasCorrelations ? "done" : hasRevenue ? "current" : "pending",
    run: "pending",
    review: "locked",
  };
}
```

Render the stepper in the JSX, right after the heading and before the main content:
```tsx
{config && (
  <ModelStepper baselineId={id} steps={computeStepStates(config)} />
)}
```

**Step 4: Run tests to verify they pass**

Run: `cd "apps/web" && npx vitest run tests/pages/baselines-detail.test.tsx --reporter=verbose`
Expected: All tests PASS (including the new stepper test)

**Step 5: Commit**

```bash
git add apps/web/app/\(app\)/baselines/\[id\]/page.tsx apps/web/tests/pages/baselines-detail.test.tsx
git commit -m "feat(stepper): wire ModelStepper into baseline detail page"
```

---

## Task 5: Add Soft-Gate Contextual Banners

**Files:**
- Create: `apps/web/components/SoftGateBanner.tsx`
- Create: `apps/web/tests/components/soft-gate-banner.test.tsx`

**Context:** When users access a page whose prerequisites aren't met (e.g. trying to configure assumptions without a baseline), show a contextual banner with a link to the prerequisite step.

**Step 1: Write the failing test**

Create `apps/web/tests/components/soft-gate-banner.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SoftGateBanner } from "@/components/SoftGateBanner";

vi.mock("next/link", () => ({
  __esModule: true,
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [k: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

describe("SoftGateBanner", () => {
  it("renders message and action link", () => {
    render(
      <SoftGateBanner
        message="No baseline created yet"
        actionLabel="Start setup"
        actionHref="/marketplace"
      />
    );
    expect(screen.getByText("No baseline created yet")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Start setup" })).toHaveAttribute("href", "/marketplace");
  });

  it("renders with warning variant by default", () => {
    const { container } = render(
      <SoftGateBanner
        message="Test"
        actionLabel="Go"
        actionHref="/test"
      />
    );
    expect(container.firstChild).toHaveClass("border-va-warning/40");
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/web" && npx vitest run tests/components/soft-gate-banner.test.tsx --reporter=verbose`
Expected: FAIL — module not found

**Step 3: Write the SoftGateBanner component**

Create `apps/web/components/SoftGateBanner.tsx`:

```tsx
import Link from "next/link";

interface SoftGateBannerProps {
  message: string;
  actionLabel: string;
  actionHref: string;
}

export function SoftGateBanner({ message, actionLabel, actionHref }: SoftGateBannerProps) {
  return (
    <div className="mb-6 flex items-center justify-between rounded-va-sm border border-va-warning/40 bg-va-warning/10 px-4 py-3">
      <span className="text-sm text-va-warning">{message}</span>
      <Link
        href={actionHref}
        className="rounded-va-xs bg-va-warning/20 px-3 py-1 text-sm font-medium text-va-warning hover:bg-va-warning/30"
      >
        {actionLabel} →
      </Link>
    </div>
  );
}
```

**Step 4: Run test to verify it passes**

Run: `cd "apps/web" && npx vitest run tests/components/soft-gate-banner.test.tsx --reporter=verbose`
Expected: 2 tests PASS

**Step 5: Commit**

```bash
git add apps/web/components/SoftGateBanner.tsx apps/web/tests/components/soft-gate-banner.test.tsx
git commit -m "feat(ux): add SoftGateBanner for prerequisite step warnings"
```

---

## Task 6: Expand Pre-built Industry Templates

**Files:**
- Modify: `apps/api/app/data/budget_templates.json`
- Modify: `apps/api/app/db/migrations/0037_marketplace_templates.sql` (or create new migration)
- Create: `apps/api/tests/test_expanded_templates.py`

**Context:** The marketplace currently has 4 budget templates: manufacturing, saas, services, wholesale. We need to add 8-10 more: discrete manufacturing, process manufacturing, consulting, legal, software dev, staffing, wholesale-local, wholesale-import, retail, construction-gc, construction-specialty, healthcare-practice, healthcare-services.

**Step 1: Write the failing test**

Create `apps/api/tests/test_expanded_templates.py`:

```python
"""Test that all expected industry templates exist and have required fields."""
import json
from pathlib import Path

import pytest


def load_templates():
    path = Path(__file__).resolve().parent.parent / "app" / "data" / "budget_templates.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


EXPECTED_TEMPLATE_IDS = [
    "manufacturing",
    "saas",
    "services",
    "wholesale",
    "consulting",
    "legal",
    "software_dev",
    "staffing",
    "wholesale_import",
    "retail",
    "construction_gc",
    "construction_specialty",
    "healthcare_practice",
    "healthcare_services",
]


def test_all_expected_templates_present():
    catalog = load_templates()
    template_ids = [t["template_id"] for t in catalog["templates"]]
    for expected in EXPECTED_TEMPLATE_IDS:
        assert expected in template_ids, f"Missing template: {expected}"


@pytest.mark.parametrize("template_id", EXPECTED_TEMPLATE_IDS)
def test_template_has_required_fields(template_id):
    catalog = load_templates()
    template = next((t for t in catalog["templates"] if t["template_id"] == template_id), None)
    assert template is not None, f"Template {template_id} not found"
    assert "label" in template
    assert "industry" in template
    assert "question_plan" in template
    assert isinstance(template["question_plan"], list)
    assert len(template["question_plan"]) > 0
    assert "default_account_refs" in template
    assert isinstance(template["default_account_refs"], list)
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/api" && python -m pytest tests/test_expanded_templates.py -v`
Expected: FAIL — missing template IDs (consulting, legal, etc.)

**Step 3: Add the new templates to budget_templates.json**

Modify `apps/api/app/data/budget_templates.json` — add 10 new template entries after the existing 4. Each needs: `template_id`, `label`, `industry`, `question_plan` (array of section objects with questions), and `default_account_refs` (array of account names).

Example for consulting:
```json
{
  "template_id": "consulting",
  "label": "Consulting Services",
  "industry": "consulting",
  "question_plan": [
    {
      "section": "Team & Utilization",
      "questions": [
        { "key": "consultant_count", "text": "How many billable consultants do you have?", "type": "number" },
        { "key": "target_utilization", "text": "What is your target utilization rate (%)?", "type": "number" },
        { "key": "avg_bill_rate", "text": "What is the average hourly billing rate?", "type": "number" }
      ]
    },
    {
      "section": "Revenue Structure",
      "questions": [
        { "key": "project_mix", "text": "Approximate split between fixed-fee and T&M (%)?", "type": "text" },
        { "key": "avg_project_duration", "text": "Average project duration in months?", "type": "number" }
      ]
    },
    {
      "section": "Overhead & Growth",
      "questions": [
        { "key": "support_ratio", "text": "Support staff to consultant ratio (e.g. 1:5)?", "type": "text" },
        { "key": "annual_growth", "text": "Expected annual headcount growth (%)?", "type": "number" }
      ]
    }
  ],
  "default_account_refs": ["Revenue", "Consultant Salaries", "Support Salaries", "Rent", "Travel", "Technology", "Professional Fees", "Other OpEx", "EBITDA"]
}
```

Repeat for: legal, software_dev, staffing, wholesale_import, retail, construction_gc, construction_specialty, healthcare_practice, healthcare_services. Each with industry-appropriate question plans and account refs.

**Step 4: Create a new migration for marketplace_templates seed data**

Create `apps/api/app/db/migrations/0045_expanded_marketplace_templates.sql`:

```sql
-- Add expanded industry templates to marketplace
INSERT INTO marketplace_templates (template_id, name, industry, template_type, description)
VALUES
  ('consulting', 'Consulting Services', 'consulting', 'budget', 'Professional consulting with utilization-based revenue, project mix, and overhead management.'),
  ('legal', 'Legal Practice', 'legal', 'budget', 'Law firm budgeting with billable hours, practice areas, and associate/partner structure.'),
  ('software_dev', 'Software Development', 'software_dev', 'budget', 'Software dev shop with project-based revenue, sprint capacity, and technology costs.'),
  ('staffing', 'Staffing Agency', 'staffing', 'budget', 'Temporary staffing with placement fees, fill rates, and contractor management.'),
  ('wholesale_import', 'Wholesale (Import)', 'wholesale_import', 'budget', 'Import-focused wholesale with FX exposure, shipping lead times, and tariff considerations.'),
  ('retail', 'Retail', 'retail', 'budget', 'Retail operations with store-level P&L, foot traffic, and inventory management.'),
  ('construction_gc', 'Construction (General Contractor)', 'construction', 'budget', 'General contracting with project pipeline, completion percentage, and subcontractor management.'),
  ('construction_specialty', 'Construction (Specialty Trade)', 'construction', 'budget', 'Specialty trade with crew-based capacity, material costs, and project backlog.'),
  ('healthcare_practice', 'Medical Practice', 'healthcare', 'budget', 'Medical practice with patient volume, reimbursement rates, and payer mix.'),
  ('healthcare_services', 'Healthcare Services', 'healthcare', 'budget', 'Healthcare services with facility-based revenue, staffing ratios, and regulatory compliance.')
ON CONFLICT (template_id) DO NOTHING;
```

**Step 5: Run tests to verify they pass**

Run: `cd "apps/api" && python -m pytest tests/test_expanded_templates.py -v`
Expected: All 15 parametrized tests PASS

**Step 6: Commit**

```bash
git add apps/api/app/data/budget_templates.json apps/api/app/db/migrations/0045_expanded_marketplace_templates.sql apps/api/tests/test_expanded_templates.py
git commit -m "feat(templates): expand marketplace with 10 new industry templates"
```

---

## Task 7: Add "Save as Template" Flow

**Files:**
- Modify: `apps/api/app/routers/marketplace.py` (add POST endpoint)
- Modify: `apps/web/lib/api.ts` (add API client method)
- Modify: `apps/web/app/(app)/baselines/[id]/page.tsx` (add button)
- Create: `apps/api/tests/test_save_as_template.py`

**Context:** Users should be able to save a completed baseline configuration as a reusable template. The template captures the assumption structure (revenue stream types, funding types, OpEx categories, distribution shapes, correlation matrix) but NOT actual values. Templates are tenant-scoped by default.

**Step 1: Write the failing backend test**

Create `apps/api/tests/test_save_as_template.py`:

```python
"""Test saving a baseline as a marketplace template."""
import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.anyio
async def test_save_as_template_creates_entry(test_db, auth_headers):
    """POST /marketplace/templates/from-baseline creates a tenant-scoped template."""
    # First create a baseline (use existing test fixtures)
    body = {
        "source_baseline_id": "b-1",
        "name": "My Custom Template",
        "industry": "consulting",
        "description": "Custom consulting template from our firm's baseline.",
    }
    async with AsyncClient(app=app, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/marketplace/templates/from-baseline",
            json=body,
            headers=auth_headers,
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["template_id"]
    assert data["name"] == "My Custom Template"
    assert data["industry"] == "consulting"
    assert data["template_type"] == "model"
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/api" && python -m pytest tests/test_save_as_template.py -v`
Expected: FAIL — 404, endpoint does not exist

**Step 3: Add the backend endpoint**

In `apps/api/app/routers/marketplace.py`, add:

```python
class SaveAsTemplateBody(BaseModel):
    source_baseline_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)


@router.post("/api/v1/marketplace/templates/from-baseline", status_code=201)
async def save_baseline_as_template(
    body: SaveAsTemplateBody,
    request: Request,
):
    """Save a baseline's structure as a reusable marketplace template."""
    tenant_id = request.headers.get("x-tenant-id", "")
    user_id = request.headers.get("x-user-id", "")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="Missing tenant ID")

    # Load baseline config
    db = get_db()
    baseline = await db.fetchrow(
        "SELECT artifact FROM model_baselines WHERE baseline_id = $1 AND tenant_id = $2",
        body.source_baseline_id, tenant_id,
    )
    if not baseline:
        raise HTTPException(status_code=404, detail="Baseline not found")

    import json, uuid
    config = json.loads(baseline["artifact"]) if isinstance(baseline["artifact"], str) else baseline["artifact"]
    template_id = f"user-{uuid.uuid4().hex[:12]}"

    # Extract structure (types, categories) without values
    assumptions = config.get("assumptions", {})
    question_plan = _extract_question_plan_from_assumptions(assumptions)
    account_refs = _extract_account_refs(assumptions)

    template_data = {
        "template_id": template_id,
        "label": body.name,
        "industry": body.industry,
        "question_plan": question_plan,
        "default_account_refs": account_refs,
    }

    await db.execute(
        """INSERT INTO marketplace_templates (template_id, name, industry, template_type, description, tenant_id)
           VALUES ($1, $2, $3, 'model', $4, $5)""",
        template_id, body.name, body.industry, body.description, tenant_id,
    )

    return {
        "template_id": template_id,
        "name": body.name,
        "industry": body.industry,
        "template_type": "model",
        "description": body.description,
    }


def _extract_question_plan_from_assumptions(assumptions: dict) -> list:
    """Extract question structure from assumption shapes without values."""
    plan = []
    revenue = assumptions.get("revenue_streams", [])
    if revenue:
        plan.append({
            "section": "Revenue Streams",
            "questions": [
                {"key": f"rev_{i}", "text": f"Describe revenue stream: {s.get('name', f'Stream {i+1}')}", "type": "text"}
                for i, s in enumerate(revenue)
            ],
        })
    funding = assumptions.get("funding", {})
    if funding.get("debt_facilities") or funding.get("equity_raises"):
        plan.append({
            "section": "Funding",
            "questions": [
                {"key": "funding_structure", "text": "Describe your funding structure", "type": "text"},
            ],
        })
    return plan


def _extract_account_refs(assumptions: dict) -> list:
    """Extract unique account reference names from assumptions."""
    refs = ["Revenue"]
    cost = assumptions.get("cost_structure", {})
    for category in ["cogs", "sga", "rnd", "other_opex"]:
        items = cost.get(category, [])
        for item in items:
            name = item.get("name", item.get("label", category.upper()))
            if name not in refs:
                refs.append(name)
    refs.append("EBITDA")
    return refs
```

**Step 4: Add the API client method**

In `apps/web/lib/api.ts`, add to the `marketplace` namespace:

```typescript
saveAsTemplate: (tenantId: string, body: {
  source_baseline_id: string;
  name: string;
  industry: string;
  description?: string;
}) =>
  request<{ template_id: string; name: string; industry: string; template_type: string }>(
    "/api/v1/marketplace/templates/from-baseline",
    { tenantId, method: "POST", body }
  ),
```

**Step 5: Add the "Save as Template" button to baseline detail page**

In the baseline detail page, add a button in the action bar:

```tsx
<VAButton
  variant="ghost"
  onClick={async () => {
    const name = prompt("Template name:");
    if (!name || !tenantId) return;
    const industry = prompt("Industry tag (e.g. consulting, manufacturing):");
    if (!industry) return;
    try {
      const result = await api.marketplace.saveAsTemplate(tenantId, {
        source_baseline_id: id,
        name,
        industry,
      });
      toast.success(`Template saved: ${result.name}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save template");
    }
  }}
>
  Save as Template
</VAButton>
```

**Step 6: Run tests**

Run: `cd "apps/api" && python -m pytest tests/test_save_as_template.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/api/app/routers/marketplace.py apps/web/lib/api.ts apps/web/app/\(app\)/baselines/\[id\]/page.tsx apps/api/tests/test_save_as_template.py
git commit -m "feat(templates): add Save as Template flow from baselines"
```

---

## Task 8: AI Industry Detection from AFS Upload

**Files:**
- Modify: `apps/api/app/routers/excel_ingestion.py` (enhance classification prompt)
- Modify: `apps/web/app/(app)/excel-import/page.tsx` (show detection UI)
- Create: `apps/api/tests/test_industry_detection.py`

**Context:** The Excel ingestion pipeline already classifies uploads via LLM. Currently `model_summary.industry` is a free-text string. We need to enhance the classification prompt to also output: NAICS code guess, matched template ID from our catalog, confidence score, and detected revenue drivers.

**Step 1: Write the failing test**

Create `apps/api/tests/test_industry_detection.py`:

```python
"""Test that classification response includes industry detection fields."""
import pytest


def test_classification_schema_has_detection_fields():
    """Verify the classification JSON schema requests industry detection."""
    from app.routers.excel_ingestion import CLASSIFICATION_SCHEMA

    model_summary = CLASSIFICATION_SCHEMA["properties"]["model_summary"]
    props = model_summary["properties"]
    assert "naics_code" in props, "model_summary should have naics_code"
    assert "matched_template_id" in props, "model_summary should have matched_template_id"
    assert "detection_confidence" in props, "model_summary should have detection_confidence"
    assert "detected_revenue_drivers" in props, "model_summary should have detected_revenue_drivers"
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/api" && python -m pytest tests/test_industry_detection.py -v`
Expected: FAIL — fields not in schema

**Step 3: Enhance the classification schema**

In `apps/api/app/routers/excel_ingestion.py`, find the `CLASSIFICATION_SCHEMA` dict and add to `model_summary.properties`:

```python
"naics_code": {"type": "string", "description": "Best-guess 4-6 digit NAICS code for this business"},
"matched_template_id": {
    "type": "string",
    "description": "Best-matching template from catalog: manufacturing, saas, services, wholesale, consulting, legal, software_dev, staffing, wholesale_import, retail, construction_gc, construction_specialty, healthcare_practice, healthcare_services",
},
"detection_confidence": {"type": "number", "minimum": 0, "maximum": 1, "description": "Confidence 0-1 in industry detection"},
"detected_revenue_drivers": {
    "type": "array",
    "items": {"type": "string"},
    "description": "Key revenue drivers detected from year-over-year analysis (e.g. 'MRR growth', 'billable hours', 'project completions')",
},
```

**Step 4: Update the classification prompt**

In the same file, find where the LLM prompt is built for classification. Add instructions like:

```python
# Add to the classification prompt text:
"Also analyze year-over-year trends in the financial data to detect:\n"
"- The most likely NAICS code for this business\n"
"- Which of our template catalog best matches (see matched_template_id enum)\n"
"- Key revenue drivers based on line item growth patterns\n"
"- Your confidence (0.0-1.0) in this classification\n"
```

**Step 5: Update the Excel import frontend to show detection results**

In `apps/web/app/(app)/excel-import/page.tsx`, in Step 2 (Review Classification), add a section showing the detected template match:

```tsx
{classification?.model_summary?.matched_template_id && (
  <div className="mt-4 rounded-va-sm border border-va-success/40 bg-va-success/10 p-4">
    <p className="text-sm font-medium text-va-success">
      Industry detected: {classification.model_summary.industry}
      {classification.model_summary.detection_confidence &&
        ` (${Math.round(classification.model_summary.detection_confidence * 100)}% confidence)`
      }
    </p>
    <p className="mt-1 text-sm text-va-text2">
      Suggested template: <strong>{classification.model_summary.matched_template_id}</strong>
    </p>
    {classification.model_summary.detected_revenue_drivers?.length > 0 && (
      <p className="mt-1 text-sm text-va-text2">
        Revenue drivers: {classification.model_summary.detected_revenue_drivers.join(", ")}
      </p>
    )}
  </div>
)}
```

**Step 6: Run tests**

Run: `cd "apps/api" && python -m pytest tests/test_industry_detection.py -v`
Expected: PASS

**Step 7: Commit**

```bash
git add apps/api/app/routers/excel_ingestion.py apps/web/app/\(app\)/excel-import/page.tsx apps/api/tests/test_industry_detection.py
git commit -m "feat(ai): enhance AFS classification with industry detection and template matching"
```

---

## Task 9: Multi-Entity Hierarchy Detection

**Files:**
- Modify: `apps/api/app/routers/excel_ingestion.py` (add entity detection to schema)
- Create: `apps/web/components/EntityHierarchyEditor.tsx`
- Create: `apps/web/tests/components/entity-hierarchy-editor.test.tsx`

**Context:** When uploaded AFS contains consolidated financial statements with subsidiaries, the AI should detect the org hierarchy and present it for user confirmation/adjustment. The user sees a tree view of detected entities with their industry classifications and can edit before proceeding.

**Step 1: Write the failing test for EntityHierarchyEditor**

Create `apps/web/tests/components/entity-hierarchy-editor.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EntityHierarchyEditor } from "@/components/EntityHierarchyEditor";

describe("EntityHierarchyEditor", () => {
  const mockEntities = [
    { entity_name: "Parent Corp", industry: "manufacturing", is_parent: true, children: ["Sub A", "Sub B"] },
    { entity_name: "Sub A", industry: "saas", is_parent: false, children: [] },
    { entity_name: "Sub B", industry: "consulting", is_parent: false, children: [] },
  ];

  it("renders detected entities in tree structure", () => {
    render(<EntityHierarchyEditor entities={mockEntities} onChange={vi.fn()} />);
    expect(screen.getByText("Parent Corp")).toBeInTheDocument();
    expect(screen.getByText("Sub A")).toBeInTheDocument();
    expect(screen.getByText("Sub B")).toBeInTheDocument();
  });

  it("shows industry classification for each entity", () => {
    render(<EntityHierarchyEditor entities={mockEntities} onChange={vi.fn()} />);
    expect(screen.getByText("manufacturing")).toBeInTheDocument();
    expect(screen.getByText("saas")).toBeInTheDocument();
    expect(screen.getByText("consulting")).toBeInTheDocument();
  });

  it("allows editing entity industry", () => {
    const onChange = vi.fn();
    render(<EntityHierarchyEditor entities={mockEntities} onChange={onChange} />);
    // The industry field should be editable
    const industryInputs = screen.getAllByRole("textbox");
    expect(industryInputs.length).toBeGreaterThanOrEqual(3);
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd "apps/web" && npx vitest run tests/components/entity-hierarchy-editor.test.tsx --reporter=verbose`
Expected: FAIL — module not found

**Step 3: Write the EntityHierarchyEditor component**

Create `apps/web/components/EntityHierarchyEditor.tsx`:

```tsx
"use client";

import { VAInput } from "@/components/ui";

export interface DetectedEntity {
  entity_name: string;
  industry: string;
  is_parent: boolean;
  children: string[];
}

interface Props {
  entities: DetectedEntity[];
  onChange: (entities: DetectedEntity[]) => void;
}

export function EntityHierarchyEditor({ entities, onChange }: Props) {
  function updateIndustry(index: number, industry: string) {
    const updated = entities.map((e, i) => (i === index ? { ...e, industry } : e));
    onChange(updated);
  }

  function updateName(index: number, entity_name: string) {
    const updated = entities.map((e, i) => (i === index ? { ...e, entity_name } : e));
    onChange(updated);
  }

  const parents = entities.filter((e) => e.is_parent);
  const childMap = new Map<string, DetectedEntity[]>();
  for (const parent of parents) {
    childMap.set(
      parent.entity_name,
      entities.filter((e) => parent.children.includes(e.entity_name))
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-medium text-va-text">
        Detected entity hierarchy — review and adjust:
      </p>
      {parents.map((parent) => {
        const parentIdx = entities.indexOf(parent);
        return (
          <div key={parent.entity_name} className="rounded-va-sm border border-va-border bg-va-panel/60 p-3">
            <div className="flex items-center gap-3">
              <span className="text-xs font-semibold uppercase text-va-muted">Parent</span>
              <VAInput
                value={parent.entity_name}
                onChange={(e) => updateName(parentIdx, e.target.value)}
                className="flex-1"
              />
              <VAInput
                value={parent.industry}
                onChange={(e) => updateIndustry(parentIdx, e.target.value)}
                placeholder="Industry"
                className="w-40"
              />
            </div>
            {(childMap.get(parent.entity_name) ?? []).map((child) => {
              const childIdx = entities.indexOf(child);
              return (
                <div key={child.entity_name} className="ml-8 mt-2 flex items-center gap-3">
                  <span className="text-xs text-va-muted">└</span>
                  <VAInput
                    value={child.entity_name}
                    onChange={(e) => updateName(childIdx, e.target.value)}
                    className="flex-1"
                  />
                  <VAInput
                    value={child.industry}
                    onChange={(e) => updateIndustry(childIdx, e.target.value)}
                    placeholder="Industry"
                    className="w-40"
                  />
                </div>
              );
            })}
          </div>
        );
      })}
      {/* Show orphan entities (no parent) */}
      {entities.filter((e) => !e.is_parent && !parents.some((p) => p.children.includes(e.entity_name))).map((orphan) => {
        const idx = entities.indexOf(orphan);
        return (
          <div key={orphan.entity_name} className="flex items-center gap-3 rounded-va-sm border border-va-border bg-va-panel/60 p-3">
            <span className="text-xs font-semibold uppercase text-va-warning">Unlinked</span>
            <VAInput
              value={orphan.entity_name}
              onChange={(e) => updateName(idx, e.target.value)}
              className="flex-1"
            />
            <VAInput
              value={orphan.industry}
              onChange={(e) => updateIndustry(idx, e.target.value)}
              placeholder="Industry"
              className="w-40"
            />
          </div>
        );
      })}
    </div>
  );
}
```

**Step 4: Enhance the Excel ingestion classification schema for multi-entity**

In `apps/api/app/routers/excel_ingestion.py`, add to the classification schema:

```python
"detected_entities": {
    "type": "array",
    "items": {
        "type": "object",
        "required": ["entity_name", "industry", "is_parent"],
        "properties": {
            "entity_name": {"type": "string"},
            "industry": {"type": "string"},
            "is_parent": {"type": "boolean"},
            "children": {"type": "array", "items": {"type": "string"}},
        },
    },
    "description": "If consolidated AFS with subsidiaries, list each entity with parent-child relationships",
},
```

**Step 5: Run tests**

Run: `cd "apps/web" && npx vitest run tests/components/entity-hierarchy-editor.test.tsx --reporter=verbose`
Expected: 3 tests PASS

**Step 6: Commit**

```bash
git add apps/web/components/EntityHierarchyEditor.tsx apps/web/tests/components/entity-hierarchy-editor.test.tsx apps/api/app/routers/excel_ingestion.py
git commit -m "feat(ai): add multi-entity hierarchy detection and editor component"
```

---

## Task 10: Redesign Landing Page Hero

**Files:**
- Modify: `apps/web/app/page.tsx:26-94` (hero section)

**Context:** The current hero says "Build better models in less time." Redesign with larger logo, new tagline "One Platform for the Full Financial Modeling Workflow," and a secondary CTA "See How It Works" that scrolls to the features section.

**Step 1: Modify the hero section**

In `apps/web/app/page.tsx`, replace the hero section (lines 66-94) with:

```tsx
{/* Hero */}
<section className="relative overflow-hidden border-b border-va-border bg-gradient-to-b from-va-panel/50 to-va-midnight">
  <div className="mx-auto max-w-6xl px-4 py-20 sm:px-6 sm:py-28">
    <div className="mx-auto max-w-3xl text-center">
      <Image
        src="/va-icon.svg"
        alt="Virtual Analyst"
        width={80}
        height={80}
        className="mx-auto h-20 w-20 sm:h-24 sm:w-24"
      />
      <h1 className="mt-6 font-brand text-4xl font-bold tracking-tight text-va-text sm:text-5xl md:text-6xl">
        One Platform for the Full Financial Modeling Workflow
      </h1>
      <p className="mt-6 text-lg leading-relaxed text-va-text2 sm:text-xl">
        From AFS upload to board pack — AI-powered modeling, Monte Carlo simulation, and automated reporting.
      </p>
      <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
        <Link
          href="/signup"
          className="inline-flex w-full items-center justify-center rounded-va-sm bg-va-blue px-6 py-3 text-base font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue sm:w-auto"
        >
          Get started free
        </Link>
        <a
          href="#features"
          className="inline-flex w-full items-center justify-center rounded-va-sm border border-va-border bg-transparent px-6 py-3 text-base font-medium text-va-text hover:bg-white/5 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight sm:w-auto"
        >
          See how it works →
        </a>
      </div>
    </div>
  </div>
</section>
```

**Step 2: Run existing tests to verify no regressions**

Run: `cd "apps/web" && npx vitest run --reporter=verbose`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add apps/web/app/page.tsx
git commit -m "feat(landing): redesign hero with prominent logo and new tagline"
```

---

## Task 11: Workflow-Organized Feature Showcase

**Files:**
- Modify: `apps/web/app/page.tsx:96-186` (value props + feature highlights sections)

**Context:** Replace the current 4 value-prop cards and 4 feature-highlight bullets with a workflow-organized showcase matching the new sidebar groups: SETUP, CONFIGURE, ANALYZE, REPORT.

**Step 1: Replace the value props and feature sections**

In `apps/web/app/page.tsx`, replace lines 96-186 (both `value-heading` and `features-heading` sections) with:

```tsx
{/* Feature Showcase */}
<section id="features" className="border-b border-va-border bg-va-midnight py-16 sm:py-24" aria-labelledby="features-heading">
  <div className="mx-auto max-w-6xl px-4 sm:px-6">
    <h2 id="features-heading" className="font-brand text-2xl font-bold text-va-text sm:text-3xl text-center">
      Everything you need, organized by workflow
    </h2>
    <p className="mx-auto mt-4 max-w-2xl text-center text-va-text2">
      Four stages take you from raw data to stakeholder-ready outputs.
    </p>
    <div className="mt-12 grid gap-8 sm:grid-cols-2">
      {/* SETUP */}
      <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-blue/20 text-va-blue" aria-hidden>
          <span className="text-lg font-bold">1</span>
        </div>
        <h3 className="mt-4 font-brand text-lg font-semibold text-va-blue">Setup</h3>
        <ul className="mt-3 space-y-2 text-sm text-va-text2">
          <li>Import Excel models or upload annual financial statements</li>
          <li>Choose from 14+ industry templates or let AI detect your industry</li>
          <li>Create multi-entity group structures for consolidated reporting</li>
        </ul>
      </div>
      {/* CONFIGURE */}
      <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-violet/20 text-va-violet" aria-hidden>
          <span className="text-lg font-bold">2</span>
        </div>
        <h3 className="mt-4 font-brand text-lg font-semibold text-va-violet">Configure</h3>
        <ul className="mt-3 space-y-2 text-sm text-va-text2">
          <li>Structured assumption editor for revenue, funding, and OpEx</li>
          <li>AI-assisted driver detection from uploaded financials</li>
          <li>Scenario comparison with side-by-side diffs</li>
          <li>Correlation matrix for variable relationships</li>
        </ul>
      </div>
      {/* ANALYZE */}
      <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-success/20 text-va-success" aria-hidden>
          <span className="text-lg font-bold">3</span>
        </div>
        <h3 className="mt-4 font-brand text-lg font-semibold text-va-success">Analyze</h3>
        <ul className="mt-3 space-y-2 text-sm text-va-text2">
          <li>One-click Monte Carlo simulation with configurable iterations</li>
          <li>Sensitivity analysis with tornado charts and heatmaps</li>
          <li>Budget tracking with variance analysis and reforecasting</li>
          <li>Covenant monitoring with breach detection</li>
        </ul>
      </div>
      {/* REPORT */}
      <div className="rounded-va-lg border border-va-border bg-va-panel/80 p-6">
        <div className="flex h-10 w-10 items-center justify-center rounded-va-sm bg-va-magenta/20 text-va-magenta" aria-hidden>
          <span className="text-lg font-bold">4</span>
        </div>
        <h3 className="mt-4 font-brand text-lg font-semibold text-va-magenta">Report</h3>
        <ul className="mt-3 space-y-2 text-sm text-va-text2">
          <li>Auto-generated board packs with drag-and-drop section ordering</li>
          <li>Executive memos with evidence-backed summaries</li>
          <li>Document management with version tracking</li>
        </ul>
      </div>
    </div>
  </div>
</section>
```

**Step 2: Run tests**

Run: `cd "apps/web" && npx vitest run --reporter=verbose`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add apps/web/app/page.tsx
git commit -m "feat(landing): replace feature cards with workflow-organized showcase"
```

---

## Task 12: Competitor Comparison Page

**Files:**
- Create: `apps/web/app/compare/page.tsx`
- Modify: `apps/web/app/page.tsx` (add link to /compare in footer and CTA)

**Context:** New public page at `/compare` with a two-tier comparison: Virtual Analyst vs. Spreadsheets and vs. Enterprise FP&A tools. This is a public page (NOT in the `(app)` route group — no auth required).

**Step 1: Create the comparison page**

Create `apps/web/app/compare/page.tsx`:

```tsx
import Image from "next/image";
import Link from "next/link";

export const metadata = {
  title: "Compare | Virtual Analyst",
  description: "See how Virtual Analyst compares to spreadsheets and enterprise FP&A tools.",
};

function CheckIcon() {
  return <span className="text-va-success">&#10003;</span>;
}
function XIcon() {
  return <span className="text-va-danger">&#10007;</span>;
}
function PartialIcon() {
  return <span className="text-va-warning">~</span>;
}

interface ComparisonRow {
  feature: string;
  competitor: React.ReactNode;
  va: React.ReactNode;
}

function ComparisonTable({ title, description, rows, competitorLabel }: {
  title: string;
  description: string;
  rows: ComparisonRow[];
  competitorLabel: string;
}) {
  return (
    <section className="mt-12">
      <h2 className="font-brand text-xl font-bold text-va-text sm:text-2xl">{title}</h2>
      <p className="mt-2 text-va-text2">{description}</p>
      <div className="mt-6 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-va-border">
              <th className="py-3 pr-4 text-left font-medium text-va-text2">Feature</th>
              <th className="px-4 py-3 text-center font-medium text-va-text2">{competitorLabel}</th>
              <th className="px-4 py-3 text-center font-medium text-va-blue">Virtual Analyst</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.feature} className="border-b border-va-border/50">
                <td className="py-3 pr-4 text-va-text">{row.feature}</td>
                <td className="px-4 py-3 text-center">{row.competitor}</td>
                <td className="px-4 py-3 text-center">{row.va}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function ComparePage() {
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-va-border bg-va-midnight/95 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <Image src="/va-icon.svg" alt="" width={32} height={32} className="h-8 w-8" />
            <span className="font-brand text-lg font-semibold text-va-text">Virtual Analyst</span>
          </Link>
          <nav className="flex items-center gap-3">
            <Link href="/login" className="rounded-va-xs px-3 py-2 text-sm font-medium text-va-text2 hover:text-va-text">Sign in</Link>
            <Link href="/signup" className="inline-flex items-center rounded-va-sm bg-va-blue px-4 py-2 text-sm font-medium text-white hover:bg-va-blue/90 shadow-va-glow-blue">Get started</Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <div className="mx-auto max-w-4xl px-4 py-16 sm:px-6 sm:py-24">
          <h1 className="font-brand text-3xl font-bold text-va-text sm:text-4xl text-center">
            How Virtual Analyst Compares
          </h1>
          <p className="mt-4 text-center text-lg text-va-text2">
            Whether you are upgrading from spreadsheets or looking for a modern alternative to enterprise FP&amp;A tools.
          </p>

          <ComparisonTable
            title="vs. Spreadsheets"
            description="Excel and Google Sheets are flexible but lack the automation and rigor that financial modeling demands."
            competitorLabel="Excel / Sheets"
            rows={[
              { feature: "Monte Carlo simulation", competitor: <span className="text-va-text2">Manual VBA macros</span>, va: <><CheckIcon /> Built-in, one click</> },
              { feature: "Scenario comparison", competitor: <span className="text-va-text2">Copy worksheets</span>, va: <><CheckIcon /> Side-by-side diff</> },
              { feature: "Collaboration", competitor: <span className="text-va-text2">File sharing</span>, va: <><CheckIcon /> Real-time, versioned</> },
              { feature: "AI assistance", competitor: <><XIcon /> None</>, va: <><CheckIcon /> Industry detection, driver analysis</> },
              { feature: "Audit trail", competitor: <><XIcon /> None</>, va: <><CheckIcon /> Full version history</> },
              { feature: "Sensitivity analysis", competitor: <span className="text-va-text2">Manual data tables</span>, va: <><CheckIcon /> Tornado charts, heatmaps</> },
              { feature: "Board pack generation", competitor: <><XIcon /> Manual</>, va: <><CheckIcon /> Automated, drag-and-drop</> },
            ]}
          />

          <ComparisonTable
            title="vs. Enterprise FP&A"
            description="Anaplan, Adaptive Planning, and Vena are powerful but come with enterprise complexity and cost."
            competitorLabel="Enterprise FP&A"
            rows={[
              { feature: "Time to first model", competitor: <span className="text-va-text2">Weeks to months</span>, va: <><CheckIcon /> Minutes</> },
              { feature: "Pricing", competitor: <span className="text-va-text2">$50K-500K+/year</span>, va: <><CheckIcon /> Fraction of the cost</> },
              { feature: "AI-native", competitor: <><PartialIcon /> Bolt-on</>, va: <><CheckIcon /> Built from ground up</> },
              { feature: "Monte Carlo simulation", competitor: <><PartialIcon /> Limited or add-on</>, va: <><CheckIcon /> Core feature</> },
              { feature: "Template marketplace", competitor: <span className="text-va-text2">Vendor-locked</span>, va: <><CheckIcon /> Open, community-driven</> },
              { feature: "Implementation support", competitor: <span className="text-va-text2">Requires consultants</span>, va: <><CheckIcon /> Self-service with AI guidance</> },
            ]}
          />

          <div className="mt-16 text-center">
            <Link
              href="/signup"
              className="inline-flex items-center rounded-va-sm bg-va-blue px-6 py-3 text-base font-medium text-white hover:bg-va-blue/90 shadow-va-glow-blue"
            >
              Start your free trial
            </Link>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-va-border bg-va-ink py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
          <div className="flex items-center gap-2">
            <Image src="/va-icon.svg" alt="" width={24} height={24} className="h-6 w-6" />
            <span className="font-brand text-sm font-medium text-va-text2">Virtual Analyst</span>
          </div>
          <nav className="flex items-center gap-6">
            <Link href="/" className="text-sm text-va-text2 hover:text-va-text">Home</Link>
            <Link href="/login" className="text-sm text-va-text2 hover:text-va-text">Sign in</Link>
            <Link href="/signup" className="text-sm text-va-text2 hover:text-va-text">Sign up</Link>
          </nav>
          <p className="text-xs text-va-muted">
            &copy; {new Date().getFullYear()} Virtual Analyst. All rights reserved.
          </p>
        </div>
      </footer>
    </div>
  );
}
```

**Step 2: Add link to /compare from landing page**

In `apps/web/app/page.tsx`, add a "Compare" link in the footer navigation (after "Sign up"):

```tsx
<Link
  href="/compare"
  className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
>
  Compare
</Link>
```

**Step 3: Run all tests**

Run: `cd "apps/web" && npx vitest run --reporter=verbose`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add apps/web/app/compare/page.tsx apps/web/app/page.tsx
git commit -m "feat(landing): add competitor comparison page at /compare"
```

---

## Verification Checklist

After all tasks are complete, verify:

1. **Navigation**: Sidebar renders with 4 workflow groups + utility items. Collapse/expand works. Rail mode works. Active link highlighting works.
2. **Layout**: All authenticated pages render inside the sidebar layout. Landing page, login, signup, compare do NOT have the sidebar.
3. **Stepper**: Baseline detail page shows the 7-step progress stepper with correct completion states.
4. **Soft gates**: Navigating to CONFIGURE pages without a baseline shows the warning banner.
5. **Templates**: 14+ templates available in marketplace. "Save as Template" button works on baseline detail page.
6. **AI detection**: Excel import shows industry detection results with confidence score and matched template.
7. **Entity hierarchy**: Multi-entity AFS uploads show the hierarchy editor.
8. **Landing page**: New hero with large logo, workflow-organized features, link to /compare.
9. **Comparison page**: Two-tier table renders at /compare.
10. **Tests**: All tests pass — `cd "apps/web" && npx vitest run` and `cd "apps/api" && python -m pytest`.
