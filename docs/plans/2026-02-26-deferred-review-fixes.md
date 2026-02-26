# Deferred Review Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Address all 6 deferred code review findings from the UI/UX overhaul: wire dead-code components, persist sidebar state, add ARIA labels, replace `window.prompt` with modal, extract shared layout, and add mobile drawer.

**Architecture:** Each fix is independent. Tasks are ordered by dependency (components that need to exist before wiring). The `VAFormDialog` component (Task 4) extends the existing `VAConfirmDialog` pattern. The mobile drawer (Task 6) modifies VASidebar to use an overlay approach on narrow viewports.

**Tech Stack:** Next.js 14 App Router, React 18, TypeScript, Tailwind CSS with VA design tokens, Vitest + Testing Library

---

### Task 1: Wire SoftGateBanner into Prerequisite Pages

The `SoftGateBanner` component exists at `apps/web/components/SoftGateBanner.tsx` but is not rendered anywhere. Wire it into 4 pages that represent later workflow stages.

**Files:**
- Modify: `apps/web/app/(app)/drafts/page.tsx:3,85-86`
- Modify: `apps/web/app/(app)/runs/page.tsx:3,68-69`
- Modify: `apps/web/app/(app)/budgets/page.tsx:3,55-56`
- Modify: `apps/web/app/(app)/board-packs/page.tsx:3,55-56`
- Modify: `apps/web/tests/pages/setup.tsx` (add `baselines.list` mock return for empty state)
- Create: `apps/web/tests/components/soft-gate-wiring.test.tsx`

**Step 1: Write the failing test**

Create `apps/web/tests/components/soft-gate-wiring.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import "../pages/setup"; // shared mocks

import { mockApi, mockGetAuthContext } from "../pages/setup";

describe("SoftGateBanner wiring", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
  });

  it("shows banner on Runs page when no baselines exist", async () => {
    // baselines.list returns empty -> banner should appear
    mockApi.baselines.list.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
    const RunsPage = (await import("@/app/(app)/runs/page")).default;
    render(<RunsPage />);
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(/create a baseline/i)).toBeInTheDocument();
  });

  it("hides banner on Runs page when baselines exist", async () => {
    mockApi.baselines.list.mockResolvedValue({
      items: [{ baseline_id: "b-1", label: "Test" }],
      total: 1, limit: 50, offset: 0,
    });
    const RunsPage = (await import("@/app/(app)/runs/page")).default;
    render(<RunsPage />);
    await screen.findByText("Runs");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run tests/components/soft-gate-wiring.test.tsx`
Expected: FAIL — no element with `role="alert"` found.

**Step 3: Wire SoftGateBanner into each page**

Each page gets the same pattern — import `SoftGateBanner`, add a state variable to track whether baselines exist, and conditionally render the banner after the heading.

**Drafts page** (`apps/web/app/(app)/drafts/page.tsx`):

Add import at line 7:
```tsx
import { SoftGateBanner } from "@/components/SoftGateBanner";
```

Add state after line 31:
```tsx
const [hasBaselines, setHasBaselines] = useState(true); // assume true until checked
```

Inside the auth useEffect (after `setTenantId`), add:
```tsx
try {
  const bl = await api.baselines.list(ctx.tenantId, { limit: 1 });
  setHasBaselines((bl.items?.length ?? 0) > 0);
} catch { /* non-critical */ }
```

Inside the return JSX, after the heading `<div className="mb-6 ...">` block and before the error display, insert:
```tsx
{!hasBaselines && !loading && (
  <SoftGateBanner
    message="No baselines yet — create one before starting drafts."
    actionLabel="Create baseline"
    actionHref="/marketplace"
  />
)}
```

**Runs page** (`apps/web/app/(app)/runs/page.tsx`):

Same pattern. Import SoftGateBanner. Add `hasBaselines` state. Check in the existing baselines fetch at line 52:
```tsx
setBaselines(blRes.items ?? []);
// Add this line:
// hasBaselines is already derived from baselines.length
```

Actually, the Runs page already fetches baselines at line 52. Use `baselines.length` directly. Insert after line 75:
```tsx
{baselines.length === 0 && !loading && (
  <SoftGateBanner
    message="No baselines found — create a baseline before running simulations."
    actionLabel="Create baseline"
    actionHref="/marketplace"
  />
)}
```

**Budgets page** (`apps/web/app/(app)/budgets/page.tsx`):

Import SoftGateBanner. Add `hasBaselines` state. Add baselines check in auth useEffect. Insert banner after heading div (line 64):
```tsx
{!hasBaselines && !loading && (
  <SoftGateBanner
    message="No baselines found — create one to start budgeting."
    actionLabel="Create baseline"
    actionHref="/marketplace"
  />
)}
```

**Board Packs page** (`apps/web/app/(app)/board-packs/page.tsx`):

Same pattern as Budgets. Banner message:
```tsx
{!hasBaselines && !loading && (
  <SoftGateBanner
    message="No baselines or runs yet — complete a run before creating board packs."
    actionLabel="Get started"
    actionHref="/marketplace"
  />
)}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npx vitest run tests/components/soft-gate-wiring.test.tsx`
Expected: PASS

**Step 5: Run full suite**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add apps/web/app/\(app\)/drafts/page.tsx apps/web/app/\(app\)/runs/page.tsx apps/web/app/\(app\)/budgets/page.tsx apps/web/app/\(app\)/board-packs/page.tsx apps/web/tests/components/soft-gate-wiring.test.tsx
git commit -m "feat(ux): wire SoftGateBanner into prerequisite pages"
```

---

### Task 2: Wire EntityHierarchyEditor into Excel Import Page

The `EntityHierarchyEditor` component exists at `apps/web/components/EntityHierarchyEditor.tsx` but is not rendered in the excel-import page.

**Files:**
- Modify: `apps/web/app/(app)/excel-import/page.tsx:259`

**Step 1: Add import and wire component**

In `apps/web/app/(app)/excel-import/page.tsx`:

Add import near top:
```tsx
import { EntityHierarchyEditor, type DetectedEntity } from "@/components/EntityHierarchyEditor";
```

Add state for entities:
```tsx
const [detectedEntities, setDetectedEntities] = useState<DetectedEntity[]>([]);
```

After the classification is set (after `setClassification(res)`), populate entities from the response:
```tsx
if (res.model_summary?.detected_entities) {
  setDetectedEntities(res.model_summary.detected_entities as DetectedEntity[]);
}
```

After line 258 (after the `detected_revenue_drivers` display, before the closing `</div>` of the detection card), add:
```tsx
{detectedEntities.length > 0 && (
  <div className="mt-4 border-t border-va-border pt-4">
    <h3 className="text-sm font-medium text-va-text mb-2">Detected entities</h3>
    <EntityHierarchyEditor
      entities={detectedEntities}
      onChange={setDetectedEntities}
    />
  </div>
)}
```

**Step 2: Run full test suite**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass (no test changes needed — entity editor is tested separately).

**Step 3: Commit**

```bash
git add apps/web/app/\(app\)/excel-import/page.tsx
git commit -m "feat(import): wire EntityHierarchyEditor into excel-import step 2"
```

---

### Task 3: Persist VASidebar Collapse State to localStorage

The sidebar's collapsed and group-collapsed states reset on page navigation.

**Files:**
- Modify: `apps/web/components/VASidebar.tsx:141-142,180-181,302`
- Modify: `apps/web/tests/components/sidebar.test.tsx` (add persistence tests)

**Step 1: Write the failing tests**

Add to `apps/web/tests/components/sidebar.test.tsx`:

```tsx
it("persists collapse state to localStorage", async () => {
  const user = userEvent.setup();
  render(<VASidebar />);
  await screen.findByRole("navigation");
  const collapseBtn = screen.getByRole("button", { name: /collapse sidebar/i });
  await user.click(collapseBtn);
  expect(localStorage.getItem("va-sidebar-collapsed")).toBe("true");
});

it("restores collapse state from localStorage", async () => {
  localStorage.setItem("va-sidebar-collapsed", "true");
  render(<VASidebar />);
  const nav = await screen.findByRole("navigation");
  expect(nav.className).toMatch(/w-16/);
});

it("persists group collapse state to localStorage", async () => {
  const user = userEvent.setup();
  render(<VASidebar />);
  await screen.findByRole("navigation");
  const setupHeader = screen.getByRole("button", { name: /SETUP/i });
  await user.click(setupHeader);
  const stored = JSON.parse(localStorage.getItem("va-sidebar-groups") ?? "{}");
  expect(stored.setup).toBe(true);
});
```

Also add `beforeEach` cleanup:
```tsx
// In the existing beforeEach block, add:
localStorage.clear();
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run tests/components/sidebar.test.tsx`
Expected: FAIL — localStorage not set after click.

**Step 3: Implement localStorage persistence**

In `apps/web/components/VASidebar.tsx`:

Replace lines 141-142:
```tsx
const [collapsed, setCollapsed] = useState(false);
const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>({});
```
With:
```tsx
const [collapsed, setCollapsed] = useState(() => {
  if (typeof window === "undefined") return false;
  return localStorage.getItem("va-sidebar-collapsed") === "true";
});
const [collapsedGroups, setCollapsedGroups] = useState<Record<string, boolean>>(() => {
  if (typeof window === "undefined") return {};
  try { return JSON.parse(localStorage.getItem("va-sidebar-groups") ?? "{}"); } catch { return {}; }
});
```

Replace the collapse toggle at line 302:
```tsx
onClick={() => setCollapsed((c) => !c)}
```
With:
```tsx
onClick={() => setCollapsed((c) => {
  const next = !c;
  localStorage.setItem("va-sidebar-collapsed", String(next));
  return next;
})}
```

Replace the toggleGroup function at lines 180-182:
```tsx
function toggleGroup(key: string) {
  setCollapsedGroups((prev) => ({ ...prev, [key]: !prev[key] }));
}
```
With:
```tsx
function toggleGroup(key: string) {
  setCollapsedGroups((prev) => {
    const next = { ...prev, [key]: !prev[key] };
    localStorage.setItem("va-sidebar-groups", JSON.stringify(next));
    return next;
  });
}
```

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npx vitest run tests/components/sidebar.test.tsx`
Expected: PASS — all 16 tests (13 original + 3 new).

**Step 5: Run full suite**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add apps/web/components/VASidebar.tsx apps/web/tests/components/sidebar.test.tsx
git commit -m "feat(sidebar): persist collapse state to localStorage"
```

---

### Task 4: Replace window.prompt with VAFormDialog for Save-as-Template

Replace `window.prompt()` calls with a proper modal dialog following the `VAConfirmDialog` pattern.

**Files:**
- Create: `apps/web/components/ui/VAFormDialog.tsx`
- Modify: `apps/web/components/ui/index.ts` (add export)
- Modify: `apps/web/app/(app)/baselines/[id]/page.tsx:180-199`
- Create: `apps/web/tests/components/VAFormDialog.test.tsx`

**Step 1: Write the failing test**

Create `apps/web/tests/components/VAFormDialog.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { VAFormDialog } from "@/components/ui/VAFormDialog";

describe("VAFormDialog", () => {
  it("renders form fields when open", () => {
    render(
      <VAFormDialog
        open
        title="Save Template"
        fields={[
          { name: "name", label: "Template name", placeholder: "My template" },
          { name: "industry", label: "Industry tag", placeholder: "software" },
        ]}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        submitLabel="Save"
      />
    );
    expect(screen.getByText("Save Template")).toBeInTheDocument();
    expect(screen.getByLabelText("Template name")).toBeInTheDocument();
    expect(screen.getByLabelText("Industry tag")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("returns form values on submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(
      <VAFormDialog
        open
        title="Test"
        fields={[
          { name: "name", label: "Name" },
        ]}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
        submitLabel="Save"
      />
    );
    await user.type(screen.getByLabelText("Name"), "My Template");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "My Template" });
  });

  it("calls onCancel when Cancel is clicked", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(
      <VAFormDialog
        open
        title="Test"
        fields={[{ name: "x", label: "X" }]}
        onSubmit={vi.fn()}
        onCancel={onCancel}
        submitLabel="Save"
      />
    );
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalled();
  });

  it("does not render when closed", () => {
    render(
      <VAFormDialog
        open={false}
        title="Test"
        fields={[{ name: "x", label: "X" }]}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
        submitLabel="Save"
      />
    );
    expect(screen.queryByText("Test")).not.toBeInTheDocument();
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run tests/components/VAFormDialog.test.tsx`
Expected: FAIL — module not found.

**Step 3: Implement VAFormDialog**

Create `apps/web/components/ui/VAFormDialog.tsx`:

```tsx
"use client";

import { useEffect, useState } from "react";
import { VAButton } from "./VAButton";
import { VAInput } from "./VAInput";

interface FormField {
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
}

interface VAFormDialogProps {
  open: boolean;
  title: string;
  description?: string;
  fields: FormField[];
  onSubmit: (values: Record<string, string>) => void;
  onCancel: () => void;
  submitLabel?: string;
  loading?: boolean;
}

export function VAFormDialog({
  open,
  title,
  description,
  fields,
  onSubmit,
  onCancel,
  submitLabel = "Submit",
  loading = false,
}: VAFormDialogProps) {
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (open) setValues({});
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [open, onCancel]);

  if (!open) return null;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit(values);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <form
        onSubmit={handleSubmit}
        className="mx-4 w-full max-w-md rounded-va-lg border border-va-border bg-va-panel p-6 shadow-va-md"
      >
        <h3 className="text-lg font-semibold text-va-text">{title}</h3>
        {description && (
          <p className="mt-2 text-sm text-va-text2">{description}</p>
        )}
        <div className="mt-4 space-y-3">
          {fields.map((field) => (
            <div key={field.name}>
              <label
                htmlFor={`form-${field.name}`}
                className="mb-1 block text-sm font-medium text-va-text"
              >
                {field.label}
              </label>
              <VAInput
                id={`form-${field.name}`}
                value={values[field.name] ?? ""}
                onChange={(e) =>
                  setValues((prev) => ({ ...prev, [field.name]: e.target.value }))
                }
                placeholder={field.placeholder}
                required={field.required}
              />
            </div>
          ))}
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <VAButton type="button" variant="secondary" onClick={onCancel}>
            Cancel
          </VAButton>
          <VAButton type="submit" variant="primary" disabled={loading}>
            {loading ? "Saving..." : submitLabel}
          </VAButton>
        </div>
      </form>
    </div>
  );
}
```

Add export to `apps/web/components/ui/index.ts`:
```tsx
export { VAFormDialog } from "./VAFormDialog";
```

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npx vitest run tests/components/VAFormDialog.test.tsx`
Expected: PASS — 4 tests.

**Step 5: Wire VAFormDialog into baselines detail page**

In `apps/web/app/(app)/baselines/[id]/page.tsx`:

Add import:
```tsx
import { VAFormDialog } from "@/components/ui";
```

Add state (near other state declarations):
```tsx
const [templateDialogOpen, setTemplateDialogOpen] = useState(false);
```

Replace the `handleSaveAsTemplate` function (lines 180-199):
```tsx
function handleSaveAsTemplate() {
  setTemplateDialogOpen(true);
}

async function confirmSaveAsTemplate(values: Record<string, string>) {
  if (!tenantId) return;
  const name = values.name?.trim();
  const industry = values.industry?.trim();
  if (!name || !industry) return;
  setTemplateSaving(true);
  try {
    const res = await api.marketplace.saveAsTemplate(tenantId, {
      source_baseline_id: id,
      name,
      industry,
    });
    toast.success(`Template "${res.name}" saved (${res.template_id})`);
    setTemplateDialogOpen(false);
  } catch (e) {
    toast.error(e instanceof Error ? e.message : "Failed to save template");
  } finally {
    setTemplateSaving(false);
  }
}
```

Add the dialog JSX before the closing `</main>` tag:
```tsx
<VAFormDialog
  open={templateDialogOpen}
  title="Save as Template"
  description="Save this baseline's configuration as a reusable marketplace template."
  fields={[
    { name: "name", label: "Template name", placeholder: "My Industry Template", required: true },
    { name: "industry", label: "Industry tag", placeholder: "e.g. software, manufacturing", required: true },
  ]}
  onSubmit={confirmSaveAsTemplate}
  onCancel={() => setTemplateDialogOpen(false)}
  submitLabel="Save template"
  loading={templateSaving}
/>
```

**Step 6: Run full suite**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add apps/web/components/ui/VAFormDialog.tsx apps/web/components/ui/index.ts apps/web/app/\(app\)/baselines/\[id\]/page.tsx apps/web/tests/components/VAFormDialog.test.tsx
git commit -m "feat(ui): add VAFormDialog and replace window.prompt in save-as-template"
```

---

### Task 5: Add ARIA Labels to ModelStepper Steps

Individual steps lack screen-reader-friendly labels communicating their state.

**Files:**
- Modify: `apps/web/components/ModelStepper.tsx:196-214`
- Modify: `apps/web/tests/components/model-stepper.test.tsx`

**Step 1: Write the failing test**

Add to `apps/web/tests/components/model-stepper.test.tsx`:

```tsx
it("sets aria-label on each step with state information", () => {
  render(
    <ModelStepper
      steps={{ start: "done", company: "current", historical: "pending", assumptions: "locked" }}
      baselineId="b-1"
    />
  );
  const startStep = screen.getByLabelText(/Step 1: Start \(done\)/);
  expect(startStep).toBeInTheDocument();
  const companyStep = screen.getByLabelText(/Step 2: Company \(current\)/);
  expect(companyStep).toBeInTheDocument();
  const historicalStep = screen.getByLabelText(/Step 3: Historical \(pending\)/);
  expect(historicalStep).toBeInTheDocument();
  const assumptionsStep = screen.getByLabelText(/Step 4: Assumptions \(locked\)/);
  expect(assumptionsStep).toBeInTheDocument();
});

it("sets aria-current='step' on current step link", () => {
  render(
    <ModelStepper
      steps={{ start: "done", company: "current" }}
      baselineId="b-1"
    />
  );
  const companyLink = screen.getByRole("link", { name: /Company/ });
  expect(companyLink).toHaveAttribute("aria-current", "step");
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run tests/components/model-stepper.test.tsx`
Expected: FAIL — no element found with `aria-label` matching pattern.

**Step 3: Add ARIA attributes**

In `apps/web/components/ModelStepper.tsx`:

On the step wrapper `<div>` at line 203, add `aria-label`:
```tsx
<div
  data-step={def.id}
  data-state={state}
  aria-label={`Step ${idx + 1}: ${def.label} (${state})`}
>
```

On the `<Link>` at line 205-207, add `aria-current`:
```tsx
<Link
  href={def.href(baselineId)}
  className="focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-sm"
  aria-current={state === "current" ? "step" : undefined}
>
```

**Step 4: Run test to verify it passes**

Run: `cd apps/web && npx vitest run tests/components/model-stepper.test.tsx`
Expected: PASS — 7 tests (5 original + 2 new).

**Step 5: Commit**

```bash
git add apps/web/components/ModelStepper.tsx apps/web/tests/components/model-stepper.test.tsx
git commit -m "a11y(stepper): add ARIA labels and aria-current to ModelStepper steps"
```

---

### Task 6: Extract PublicHeader and PublicFooter Components

The header and footer markup is duplicated between the landing page and compare page.

**Files:**
- Create: `apps/web/components/PublicHeader.tsx`
- Create: `apps/web/components/PublicFooter.tsx`
- Modify: `apps/web/app/page.tsx:29-62,187-217`
- Modify: `apps/web/app/compare/page.tsx:249-282,343-373`

**Step 1: Create PublicHeader component**

Create `apps/web/components/PublicHeader.tsx`:

```tsx
import Image from "next/image";
import Link from "next/link";

export function PublicHeader() {
  return (
    <header className="sticky top-0 z-50 border-b border-va-border bg-va-midnight/95 backdrop-blur supports-[backdrop-filter]:bg-va-midnight/80">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          aria-label="Virtual Analyst home"
        >
          <Image
            src="/va-icon.svg"
            alt=""
            width={32}
            height={32}
            className="h-8 w-8"
          />
          <span className="font-brand text-lg font-semibold text-va-text">
            Virtual Analyst
          </span>
        </Link>
        <nav className="flex items-center gap-3" aria-label="Main navigation">
          <Link
            href="/login"
            className="rounded-va-xs px-3 py-2 text-sm font-medium text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="inline-flex items-center rounded-va-sm bg-va-blue px-4 py-2 text-sm font-medium text-white hover:bg-va-blue/90 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight shadow-va-glow-blue"
          >
            Get started
          </Link>
        </nav>
      </div>
    </header>
  );
}
```

**Step 2: Create PublicFooter component**

Create `apps/web/components/PublicFooter.tsx`:

```tsx
import Image from "next/image";
import Link from "next/link";

export function PublicFooter() {
  return (
    <footer className="border-t border-va-border bg-va-ink py-8">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
        <div className="flex items-center gap-2">
          <Image src="/va-icon.svg" alt="" width={24} height={24} className="h-6 w-6" />
          <span className="font-brand text-sm font-medium text-va-text2">Virtual Analyst</span>
        </div>
        <nav className="flex items-center gap-6" aria-label="Footer navigation">
          <Link
            href="/login"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          >
            Sign in
          </Link>
          <Link
            href="/signup"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          >
            Sign up
          </Link>
          <Link
            href="/compare"
            className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded-va-xs"
          >
            Compare
          </Link>
        </nav>
        <p className="text-xs text-va-muted">
          &copy; {new Date().getFullYear()} Virtual Analyst. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
```

**Step 3: Replace inline markup in landing page**

In `apps/web/app/page.tsx`:

Replace the `import Image from "next/image"` with:
```tsx
import Image from "next/image";
import { PublicHeader } from "@/components/PublicHeader";
import { PublicFooter } from "@/components/PublicFooter";
```

Replace the entire `<header>...</header>` block (lines 29-62) with:
```tsx
<PublicHeader />
```

Replace the entire `<footer>...</footer>` block (lines 187-217) with:
```tsx
<PublicFooter />
```

Note: The `Image` import is still needed for the hero logo. The `Link` import is still needed for CTA buttons.

**Step 4: Replace inline markup in compare page**

In `apps/web/app/compare/page.tsx`:

Add imports:
```tsx
import { PublicHeader } from "@/components/PublicHeader";
import { PublicFooter } from "@/components/PublicFooter";
```

Replace the header block (lines 249-282) with:
```tsx
<PublicHeader />
```

Replace the footer block (lines 343-373) with:
```tsx
<PublicFooter />
```

Note: The compare page's `Image` import may only be needed for the header. If it's no longer used elsewhere, remove it.

**Step 5: Run full test suite**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass. (The existing page rendering doesn't have dedicated tests for header/footer; if anything breaks, the page-level tests would catch it.)

**Step 6: Commit**

```bash
git add apps/web/components/PublicHeader.tsx apps/web/components/PublicFooter.tsx apps/web/app/page.tsx apps/web/app/compare/page.tsx
git commit -m "refactor(public): extract PublicHeader and PublicFooter shared components"
```

---

### Task 7: Add Mobile Drawer to VASidebar

On viewports narrower than `md` (768px), the sidebar should be hidden by default and show as a slide-out drawer with backdrop overlay. A hamburger button in the layout triggers it.

**Files:**
- Modify: `apps/web/components/VASidebar.tsx`
- Modify: `apps/web/app/(app)/layout.tsx`
- Modify: `apps/web/tests/components/sidebar.test.tsx`

**Step 1: Write the failing test**

Add to `apps/web/tests/components/sidebar.test.tsx`:

```tsx
it("accepts onClose prop for mobile drawer", async () => {
  const onClose = vi.fn();
  render(<VASidebar mobileOpen onClose={onClose} />);
  const nav = await screen.findByRole("navigation");
  expect(nav).toBeInTheDocument();
  // Click close button
  const user = userEvent.setup();
  const closeBtn = screen.getByRole("button", { name: /close menu/i });
  await user.click(closeBtn);
  expect(onClose).toHaveBeenCalled();
});

it("renders backdrop when mobileOpen is true", async () => {
  render(<VASidebar mobileOpen onClose={vi.fn()} />);
  await screen.findByRole("navigation");
  expect(document.querySelector("[data-testid='mobile-backdrop']")).toBeInTheDocument();
});
```

**Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run tests/components/sidebar.test.tsx`
Expected: FAIL — VASidebar doesn't accept `mobileOpen` or `onClose` props.

**Step 3: Implement mobile drawer support**

In `apps/web/components/VASidebar.tsx`:

Update the component signature:
```tsx
interface VASidebarProps {
  mobileOpen?: boolean;
  onClose?: () => void;
}

export function VASidebar({ mobileOpen, onClose }: VASidebarProps = {}) {
```

Add a close button inside the logo section (after the logo `<Link>`, visible only when `onClose` is provided):
```tsx
{onClose && (
  <button
    type="button"
    onClick={onClose}
    className="ml-auto text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-xs p-1 md:hidden"
    aria-label="Close menu"
  >
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  </button>
)}
```

Wrap the sidebar in a fragment that includes the backdrop:
```tsx
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
        // Mobile: fixed overlay when open, hidden when closed
        mobileOpen != null
          ? mobileOpen
            ? "fixed inset-y-0 left-0 z-50 md:relative md:z-auto"
            : "hidden md:flex"
          : "",
      ].join(" ")}
      aria-label="Main navigation"
    >
```

**Step 4: Update authenticated layout with mobile toggle**

In `apps/web/app/(app)/layout.tsx`:

```tsx
"use client";

import { useState } from "react";
import { VASidebar } from "@/components/VASidebar";

export default function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden">
      <VASidebar mobileOpen={mobileOpen} onClose={() => setMobileOpen(false)} />
      <div className="flex-1 overflow-y-auto">
        {/* Mobile hamburger */}
        <div className="sticky top-0 z-30 flex h-12 items-center border-b border-va-border bg-va-panel/95 px-4 md:hidden">
          <button
            type="button"
            onClick={() => setMobileOpen(true)}
            className="text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded-va-xs p-1"
            aria-label="Open menu"
          >
            <svg width={20} height={20} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
              <line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="18" x2="21" y2="18" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
```

**Step 5: Run test to verify it passes**

Run: `cd apps/web && npx vitest run tests/components/sidebar.test.tsx`
Expected: PASS — all tests (existing + 2 new).

**Step 6: Run full suite**

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

**Step 7: Commit**

```bash
git add apps/web/components/VASidebar.tsx apps/web/app/\(app\)/layout.tsx apps/web/tests/components/sidebar.test.tsx
git commit -m "feat(sidebar): add mobile drawer with backdrop overlay and hamburger toggle"
```

---

## Summary

| Task | Description | Est. Complexity |
|------|-------------|-----------------|
| 1 | Wire SoftGateBanner into 4 pages | Medium — 4 files + test |
| 2 | Wire EntityHierarchyEditor into excel-import | Small — 1 file |
| 3 | Persist sidebar collapse to localStorage | Small — state init + sync |
| 4 | VAFormDialog + replace window.prompt | Medium — new component + wire |
| 5 | ARIA labels on ModelStepper | Small — attributes only |
| 6 | Extract PublicHeader/PublicFooter | Small — extract + replace |
| 7 | Mobile drawer for VASidebar | Medium — responsive overlay |

Total: 7 tasks, ~7 commits.
