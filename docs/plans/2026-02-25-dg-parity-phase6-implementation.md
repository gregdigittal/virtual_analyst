# Phase 6 Frontend — DG Parity UI Components: Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Surface Phases 1-5 engine capabilities in the web app via 4 UI features: Funding editor, Revenue stream segmentation, Correlation matrix editing, and Consolidated results enhancements.

**Architecture:** Hybrid edit flow — baseline detail page stays read-only; an "Edit Configuration" button creates/resumes a draft with structured editor tabs (FundingEditor, RevenueStreamEditor, CorrelationMatrixEditor in editable mode). Each editor writes to the draft workspace via debounced PATCH. Recharts for charts.

**Tech Stack:** Next.js 14 App Router, Vitest + Testing Library, Recharts, Tailwind (VA design tokens), existing VA component library.

**Design doc:** `docs/plans/2026-02-25-dg-parity-phase6-frontend-design.md`

---

## Task 1: Infrastructure Setup

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/lib/api.ts:398-406` (drafts.list opts)
- Modify: `apps/web/tests/pages/setup.tsx:59-137` (add drafts mock)

### Step 1: Install recharts

Run: `cd apps/web && npm install recharts`

### Step 2: Add `parent_baseline_id` filter to `drafts.list()`

In `apps/web/lib/api.ts`, modify the `drafts.list` method to accept and pass a
`parent_baseline_id` query parameter:

```typescript
// apps/web/lib/api.ts:398
list: (tenantId: string, opts?: { status?: string; parent_baseline_id?: string; limit?: number; offset?: number }) =>
  request<DraftsResponse>(
    `/api/v1/drafts?${new URLSearchParams({
      ...(opts?.status && { status: opts.status }),
      ...(opts?.parent_baseline_id && { parent_baseline_id: opts.parent_baseline_id }),
      ...(opts?.limit != null && { limit: String(opts.limit) }),
      ...(opts?.offset != null && { offset: String(opts.offset) }),
    }).toString()}`,
    { tenantId }
  ),
```

### Step 3: Add `drafts` namespace to test mock

In `apps/web/tests/pages/setup.tsx`, add inside `mockApi` (after `scenarios`):

```typescript
drafts: {
  list: vi.fn(async () => ({ items: [], total: 0, limit: 50, offset: 0 })),
  get: vi.fn(async () => ({
    draft_session_id: "draft-1",
    parent_baseline_id: "b-1",
    parent_baseline_version: null,
    status: "active",
    created_at: "2026-01-01T00:00:00Z",
    workspace: { assumptions: {}, distributions: [], correlation_matrix: [] },
  })),
  create: vi.fn(async () => ({ draft_session_id: "draft-new", status: "active", storage_path: "/tmp" })),
  patch: vi.fn(async () => ({ draft_session_id: "draft-1" })),
  chat: vi.fn(async () => ({ messages: [], proposals: [] })),
  acceptProposal: vi.fn(async () => ({ proposal_id: "p-1", status: "accepted" })),
  rejectProposal: vi.fn(async () => ({ proposal_id: "p-1", status: "rejected" })),
  commit: vi.fn(async () => ({ baseline_id: "b-1", baseline_version: "v-2" })),
},
```

### Step 4: Run existing tests to verify no regressions

Run: `cd apps/web && npx vitest run`
Expected: All existing tests pass.

### Step 5: Commit

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/lib/api.ts apps/web/tests/pages/setup.tsx
git commit -m "chore: add recharts, drafts.list parent_baseline_id filter, test mock"
```

---

## Task 2: FundingEditor Component

**Files:**
- Create: `apps/web/components/FundingEditor.tsx`
- Test: `apps/web/tests/components/FundingEditor.test.tsx`

**Reference:** Read `apps/web/components/FundingPanel.tsx` for the existing
read-only component and its type interfaces (`FundingConfig`, `DebtFacility`,
`EquityRaise`, `DividendsPolicy`, `DrawRepayPoint`). The editor reuses the
same data shapes.

### Step 1: Write failing tests

Create `apps/web/tests/components/FundingEditor.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FundingEditor } from "@/components/FundingEditor";

const emptyFunding = { debt_facilities: [], equity_raises: [], dividends: null };

const sampleFunding = {
  debt_facilities: [
    {
      facility_id: "f-1",
      label: "Term Loan A",
      type: "term_loan",
      limit: 500000,
      interest_rate: 0.05,
      draw_schedule: [{ month: 0, amount: 250000 }],
      repayment_schedule: [{ month: 6, amount: 125000 }],
      is_cash_plug: false,
    },
  ],
  equity_raises: [{ label: "Series A", amount: 1000000, month: 3 }],
  dividends: { policy: "fixed_amount", value: 50000 },
};

describe("FundingEditor", () => {
  it("renders empty state with add buttons", () => {
    const onChange = vi.fn();
    render(<FundingEditor funding={emptyFunding} onChange={onChange} />);
    expect(screen.getByText(/Add Facility/i)).toBeInTheDocument();
    expect(screen.getByText(/Add Raise/i)).toBeInTheDocument();
  });

  it("renders existing debt facility rows", () => {
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("Term Loan A")).toBeInTheDocument();
    expect(screen.getByDisplayValue("500000")).toBeInTheDocument();
  });

  it("calls onChange when adding a new debt facility", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={emptyFunding} onChange={onChange} />);
    await user.click(screen.getByText(/Add Facility/i));
    expect(onChange).toHaveBeenCalledTimes(1);
    const call = onChange.mock.calls[0][0];
    expect(call.debt_facilities).toHaveLength(1);
  });

  it("calls onChange when adding an equity raise", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={emptyFunding} onChange={onChange} />);
    await user.click(screen.getByText(/Add Raise/i));
    expect(onChange).toHaveBeenCalledTimes(1);
    const call = onChange.mock.calls[0][0];
    expect(call.equity_raises).toHaveLength(1);
  });

  it("renders dividend policy radio group", () => {
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    expect(screen.getByLabelText(/None/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Fixed Amount/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Payout Ratio/i)).toBeInTheDocument();
  });

  it("shows value input when Fixed Amount is selected", () => {
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    // sampleFunding has fixed_amount policy
    const valueInput = screen.getByDisplayValue("50000");
    expect(valueInput).toBeInTheDocument();
  });

  it("hides value input when None is selected", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={sampleFunding} onChange={onChange} />);
    await user.click(screen.getByLabelText(/^None$/));
    const call = onChange.mock.calls[0][0];
    expect(call.dividends.policy).toBe("none");
  });

  it("validates interest rate is between 0 and 1", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<FundingEditor funding={sampleFunding} onChange={onChange} />);
    const rateInput = screen.getByDisplayValue("0.05");
    await user.clear(rateInput);
    await user.type(rateInput, "1.5");
    await user.tab(); // trigger blur
    expect(screen.getByText(/0 and 1/i)).toBeInTheDocument();
  });

  it("expands draw schedule when chevron is clicked", async () => {
    const user = userEvent.setup();
    render(<FundingEditor funding={sampleFunding} onChange={vi.fn()} />);
    const expandBtn = screen.getByTitle(/expand/i);
    await user.click(expandBtn);
    expect(screen.getByText(/Draw Schedule/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("250000")).toBeInTheDocument();
  });
});
```

### Step 2: Run tests to verify they fail

Run: `cd apps/web && npx vitest run tests/components/FundingEditor.test.tsx`
Expected: FAIL — module `@/components/FundingEditor` not found.

### Step 3: Implement FundingEditor

Create `apps/web/components/FundingEditor.tsx`.

The component should:
- Accept `{ funding: FundingConfig | null, onChange: (f: FundingConfig) => void }`
- Use `"use client"` directive
- Import `VAInput`, `VASelect`, `VAButton`, `VAConfirmDialog` from `@/components/ui`
- Render 3 collapsible sections (Debt Facilities, Equity Raises, Dividend Policy)
- **Debt Facilities:** Editable table rows with inline VAInput/VASelect fields.
  Each row has an expand/collapse chevron button (title="expand") that reveals
  draw_schedule and repayment_schedule sub-tables. [+ Add Facility] appends a
  row with defaults `{ facility_id: crypto.randomUUID(), label: "", type: "term_loan", limit: 0, interest_rate: 0, is_cash_plug: false }`.
  Delete uses VAConfirmDialog.
- **Equity Raises:** Simple editable table. [+ Add Raise] appends
  `{ label: "", amount: 0, month: 0 }`. Direct delete (no confirm).
- **Dividend Policy:** Radio group (None / Fixed Amount / Payout Ratio).
  Conditional VAInput for value, hidden when "none" selected.
- **Validation:** Inline error text below fields. `interest_rate` must be 0–1,
  `limit` must be > 0, draw amounts must not exceed facility limit.
- Call `onChange` with the full updated `FundingConfig` on every field change.

Reuse the type interfaces from `FundingPanel.tsx` — extract them to a shared
types file or re-declare in FundingEditor (keep it simple).

### Step 4: Run tests to verify they pass

Run: `cd apps/web && npx vitest run tests/components/FundingEditor.test.tsx`
Expected: All 8 tests PASS.

### Step 5: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

### Step 6: Commit

```bash
git add apps/web/components/FundingEditor.tsx apps/web/tests/components/FundingEditor.test.tsx
git commit -m "feat: add FundingEditor component with inline editing and validation"
```

---

## Task 3: RevenueStreamEditor Component

**Files:**
- Create: `apps/web/components/RevenueStreamEditor.tsx`
- Test: `apps/web/tests/components/RevenueStreamEditor.test.tsx`

**Reference:** Read the revenue streams table on `apps/web/app/baselines/[id]/page.tsx`
(around line 253) for the existing read-only display and the data shape it expects.

### Step 1: Write failing tests

Create `apps/web/tests/components/RevenueStreamEditor.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RevenueStreamEditor } from "@/components/RevenueStreamEditor";

const sampleStreams = [
  {
    label: "SaaS Revenue",
    stream_type: "recurring",
    business_line: "Cloud",
    market: "US",
    launch_month: 3,
    ramp_up_months: 6,
    ramp_curve: "s_curve",
  },
];

describe("RevenueStreamEditor", () => {
  it("renders existing stream fields", () => {
    render(<RevenueStreamEditor streams={sampleStreams} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("SaaS Revenue")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Cloud")).toBeInTheDocument();
    expect(screen.getByDisplayValue("US")).toBeInTheDocument();
  });

  it("shows ramp fields when launch_month is set", () => {
    render(<RevenueStreamEditor streams={sampleStreams} onChange={vi.fn()} />);
    expect(screen.getByDisplayValue("6")).toBeInTheDocument(); // ramp_up_months
    expect(screen.getByDisplayValue("s_curve")).toBeInTheDocument();
  });

  it("hides ramp_up_months when launch_month is empty", () => {
    const noLaunch = [{ ...sampleStreams[0], launch_month: null, ramp_up_months: null, ramp_curve: null }];
    render(<RevenueStreamEditor streams={noLaunch} onChange={vi.fn()} />);
    expect(screen.queryByDisplayValue("6")).not.toBeInTheDocument();
  });

  it("adds a new empty stream row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RevenueStreamEditor streams={[]} onChange={onChange} />);
    await user.click(screen.getByText(/Add Stream/i));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange.mock.calls[0][0]).toHaveLength(1);
  });

  it("deletes a stream row", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RevenueStreamEditor streams={sampleStreams} onChange={onChange} />);
    await user.click(screen.getByTitle(/delete/i));
    expect(onChange).toHaveBeenCalled();
    expect(onChange.mock.calls[0][0]).toHaveLength(0);
  });

  it("updates business_line on change", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(<RevenueStreamEditor streams={sampleStreams} onChange={onChange} />);
    const blInput = screen.getByDisplayValue("Cloud");
    await user.clear(blInput);
    await user.type(blInput, "Enterprise");
    // onChange called per keystroke; last call should have updated value
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    expect(lastCall[0].business_line).toBe("Enterprise");
  });
});
```

### Step 2: Run tests to verify they fail

Run: `cd apps/web && npx vitest run tests/components/RevenueStreamEditor.test.tsx`
Expected: FAIL — module not found.

### Step 3: Implement RevenueStreamEditor

Create `apps/web/components/RevenueStreamEditor.tsx`.

The component should:
- Accept `{ streams: RevenueStream[], onChange: (s: RevenueStream[]) => void }`
- `"use client"` directive
- Import `VAInput`, `VASelect`, `VAButton` from `@/components/ui`
- Render an editable table: Label, Type (VASelect), Business Line, Market,
  Launch Month, Ramp Up Months, Ramp Curve (VASelect)
- **Progressive disclosure:** `ramp_up_months` only visible when `launch_month`
  is set. `ramp_curve` only visible when `ramp_up_months` is set.
- [+ Add Stream] appends `{ label: "", stream_type: "recurring", business_line: "", market: "" }`
- Delete icon button (title="delete") per row, direct removal (no confirm)
- Call `onChange` with the full updated array on every field change

```typescript
interface RevenueStream {
  label: string;
  stream_type: string;
  business_line?: string | null;
  market?: string | null;
  launch_month?: number | null;
  ramp_up_months?: number | null;
  ramp_curve?: string | null;
}
```

### Step 4: Run tests to verify they pass

Run: `cd apps/web && npx vitest run tests/components/RevenueStreamEditor.test.tsx`
Expected: All 6 tests PASS.

### Step 5: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

### Step 6: Commit

```bash
git add apps/web/components/RevenueStreamEditor.tsx apps/web/tests/components/RevenueStreamEditor.test.tsx
git commit -m "feat: add RevenueStreamEditor with progressive disclosure"
```

---

## Task 4: CorrelationMatrixEditor — Interactive Mode

**Files:**
- Modify: `apps/web/components/CorrelationMatrixEditor.tsx` (135 lines)
- Create: `apps/web/tests/components/CorrelationMatrixEditor.test.tsx`

### Step 1: Write failing tests

Create `apps/web/tests/components/CorrelationMatrixEditor.test.tsx`:

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CorrelationMatrixEditor } from "@/components/CorrelationMatrixEditor";

const distributions = [
  { ref: "drv:revenue_growth", family: "normal" },
  { ref: "drv:cost_inflation", family: "normal" },
  { ref: "drv:churn_rate", family: "beta" },
];

const correlationMatrix = [
  { ref_a: "drv:revenue_growth", ref_b: "drv:cost_inflation", rho: 0.3 },
];

describe("CorrelationMatrixEditor (read-only)", () => {
  it("renders placeholder when fewer than 2 distributions", () => {
    render(<CorrelationMatrixEditor distributions={[{ ref: "drv:x", family: "normal" }]} correlationMatrix={[]} />);
    expect(screen.getByText(/at least 2/i)).toBeInTheDocument();
  });

  it("renders NxN grid with correct values", () => {
    render(<CorrelationMatrixEditor distributions={distributions} correlationMatrix={correlationMatrix} />);
    // Diagonal should show 1.00
    const cells = screen.getAllByText("1.00");
    expect(cells.length).toBe(3); // 3 diagonal cells
    // Off-diagonal pair should show 0.30
    expect(screen.getAllByText("0.30").length).toBeGreaterThanOrEqual(2); // symmetric
  });

  it("shows active correlations list", () => {
    render(<CorrelationMatrixEditor distributions={distributions} correlationMatrix={correlationMatrix} />);
    expect(screen.getByText(/Active correlations/i)).toBeInTheDocument();
  });
});

describe("CorrelationMatrixEditor (editable)", () => {
  it("makes off-diagonal cells clickable when editable", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={correlationMatrix}
        editable
        onChange={onChange}
      />
    );
    // Click on a cell showing "0.00" (an off-diagonal zero cell)
    const zeroCells = screen.getAllByText("0.00");
    await user.click(zeroCells[0]);
    // Should show an input
    const input = screen.getByRole("spinbutton");
    expect(input).toBeInTheDocument();
  });

  it("enforces symmetry on edit", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={[]}
        editable
        onChange={onChange}
      />
    );
    // Click a zero cell and type a value
    const zeroCells = screen.getAllByText("0.00");
    await user.click(zeroCells[0]);
    const input = screen.getByRole("spinbutton");
    await user.clear(input);
    await user.type(input, "0.5");
    await user.keyboard("{Enter}");
    // onChange should be called with symmetric entries
    expect(onChange).toHaveBeenCalled();
    const entries = onChange.mock.calls[onChange.mock.calls.length - 1][0];
    const pair = entries.find((e: { ref_a: string; ref_b: string }) =>
      (e.ref_a.includes("revenue") && e.ref_b.includes("cost")) ||
      (e.ref_a.includes("cost") && e.ref_b.includes("revenue"))
    );
    expect(pair).toBeDefined();
  });

  it("does not allow editing diagonal cells", async () => {
    const user = userEvent.setup();
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={[]}
        editable
        onChange={vi.fn()}
      />
    );
    const diagCells = screen.getAllByText("1.00");
    await user.click(diagCells[0]);
    // No input should appear
    expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
  });

  it("shows PSD warning when matrix is not positive semi-definite", async () => {
    // A correlation matrix that is NOT PSD: all pairs at -0.9
    const badMatrix = [
      { ref_a: "drv:revenue_growth", ref_b: "drv:cost_inflation", rho: -0.9 },
      { ref_a: "drv:revenue_growth", ref_b: "drv:churn_rate", rho: -0.9 },
      { ref_a: "drv:cost_inflation", ref_b: "drv:churn_rate", rho: -0.9 },
    ];
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={badMatrix}
        editable
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText(/not positive semi-definite/i)).toBeInTheDocument();
  });

  it("shows valid message when matrix is PSD", () => {
    const goodMatrix = [
      { ref_a: "drv:revenue_growth", ref_b: "drv:cost_inflation", rho: 0.3 },
    ];
    render(
      <CorrelationMatrixEditor
        distributions={distributions}
        correlationMatrix={goodMatrix}
        editable
        onChange={vi.fn()}
      />
    );
    expect(screen.getByText(/valid/i)).toBeInTheDocument();
  });
});
```

### Step 2: Run tests to verify they fail

Run: `cd apps/web && npx vitest run tests/components/CorrelationMatrixEditor.test.tsx`
Expected: Read-only tests may pass. Editable tests FAIL (no `editable` prop,
no click-to-edit, no PSD validation).

### Step 3: Implement interactive mode

Modify `apps/web/components/CorrelationMatrixEditor.tsx`:

1. **Update the component signature** (line 29) to accept optional `editable`
   and `onChange` props:
   ```typescript
   export function CorrelationMatrixEditor({
     distributions,
     correlationMatrix,
     editable = false,
     onChange,
   }: {
     distributions: DistributionConfig[];
     correlationMatrix: CorrelationEntry[];
     editable?: boolean;
     onChange?: (entries: CorrelationEntry[]) => void;
   }) {
   ```

2. **Add state** for the currently edited cell: `useState<{ row: string; col: string } | null>(null)`
   and `useState<string>("")` for the input value.

3. **Add a `computeEigenvalues` helper** — implement Jacobi eigenvalue algorithm
   for small symmetric matrices (N typically ≤ 10). Returns array of eigenvalues.
   Check if all ≥ -1e-10 (tolerance for floating point).

4. **Make off-diagonal cells clickable** when `editable=true`:
   - On click: set editing state to `{ row, col }`, populate input with current rho
   - Render `<input type="number" role="spinbutton">` in that cell
   - On Enter/blur: commit value, enforce symmetry (update both A→B and B→A),
     call `onChange` with updated entries, clear editing state
   - On Escape: cancel, clear editing state
   - Diagonal cells: no click handler

5. **Add PSD validation banner** below the grid when `editable=true`:
   - Build full NxN matrix, compute eigenvalues
   - All ≥ 0 → green text: "Matrix is valid"
   - Any < 0 → amber warning: "Matrix is not positive semi-definite. MC sampling
     may produce unexpected correlations."

### Step 4: Run tests to verify they pass

Run: `cd apps/web && npx vitest run tests/components/CorrelationMatrixEditor.test.tsx`
Expected: All 8 tests PASS.

### Step 5: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass (existing baseline-detail test still passes since
the `editable` prop defaults to `false`).

### Step 6: Commit

```bash
git add apps/web/components/CorrelationMatrixEditor.tsx apps/web/tests/components/CorrelationMatrixEditor.test.tsx
git commit -m "feat: add interactive editing mode to CorrelationMatrixEditor with PSD validation"
```

---

## Task 5: Draft Workspace — Structured Editor Tabs

**Files:**
- Modify: `apps/web/app/drafts/[id]/page.tsx` (580 lines)
- Modify: `apps/web/tests/pages/setup.tsx` (if not already done in Task 1)

**Reference:** Read the existing draft workspace page to understand the current
layout — chat panel (right), AssumptionTree (left), and the detail/workspace
data flow.

### Step 1: Write failing test

Add to existing tests or create `apps/web/tests/pages/drafts-detail.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockApi, mockGetAuthContext } from "./setup";

import { ToastProvider } from "@/components/ui";
import DraftDetailPage from "@/app/drafts/[id]/page";

function renderPage() {
  return render(
    <ToastProvider>
      <DraftDetailPage />
    </ToastProvider>,
  );
}

describe("DraftDetailPage", () => {
  beforeEach(() => {
    mockGetAuthContext.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
    mockApi.drafts.get.mockResolvedValue({
      draft_session_id: "draft-1",
      parent_baseline_id: "b-1",
      parent_baseline_version: null,
      status: "active",
      created_at: "2026-01-01T00:00:00Z",
      workspace: {
        assumptions: {
          funding: { debt_facilities: [], equity_raises: [], dividends: null },
          revenue_streams: [],
        },
        distributions: [],
        correlation_matrix: [],
        chat_history: [],
        pending_proposals: [],
      },
    });
  });

  it("renders structured editor tabs", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Funding")).toBeInTheDocument();
      expect(screen.getByText("Revenue")).toBeInTheDocument();
      expect(screen.getByText("Correlations")).toBeInTheDocument();
    });
  });
});
```

### Step 2: Run test to verify it fails

Run: `cd apps/web && npx vitest run tests/pages/drafts-detail.test.tsx`
Expected: FAIL — either the tabs don't exist yet or mock issues.

### Step 3: Implement structured editor tabs

Modify `apps/web/app/drafts/[id]/page.tsx`:

1. **Add imports** at the top (after existing imports):
   ```typescript
   import { FundingEditor } from "@/components/FundingEditor";
   import { RevenueStreamEditor } from "@/components/RevenueStreamEditor";
   import { CorrelationMatrixEditor } from "@/components/CorrelationMatrixEditor";
   import { useSearchParams } from "next/navigation";
   ```

2. **Add tab state** using `useSearchParams` for deep-linking:
   ```typescript
   const searchParams = useSearchParams();
   const initialTab = searchParams.get("tab") ?? "overview";
   const [editorTab, setEditorTab] = useState(initialTab);
   ```

3. **Add a debounced save helper:**
   ```typescript
   const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

   const debouncedPatch = useCallback((updatedWorkspace: Record<string, unknown>) => {
     if (saveTimeoutRef.current) clearTimeout(saveTimeoutRef.current);
     saveTimeoutRef.current = setTimeout(async () => {
       try {
         await api.drafts.patch(tenantId!, id, { workspace: updatedWorkspace });
         toast.success("Saved");
       } catch (e) {
         toast.error(e instanceof Error ? e.message : "Save failed");
       }
     }, 300);
   }, [tenantId, id, toast]);
   ```

4. **Add VATabs section** in the main content area (before or replacing the
   raw AssumptionTree block around line 317). The tabs should be:

   ```tsx
   <VATabs
     activeId={editorTab}
     onSelect={setEditorTab}
     tabs={[
       {
         id: "overview",
         label: "Overview",
         content: <>{/* existing AssumptionTree rendering */}</>,
       },
       {
         id: "funding",
         label: "Funding",
         content: (
           <FundingEditor
             funding={(workspace?.assumptions as Record<string, unknown>)?.funding as FundingConfig | null}
             onChange={(f) => {
               const ws = { ...workspace, assumptions: { ...(workspace?.assumptions as Record<string, unknown>), funding: f } };
               setDetail((d) => d ? { ...d, workspace: ws } : d);
               debouncedPatch(ws);
             }}
           />
         ),
       },
       {
         id: "revenue",
         label: "Revenue",
         content: (
           <RevenueStreamEditor
             streams={((workspace?.assumptions as Record<string, unknown>)?.revenue_streams ?? []) as RevenueStream[]}
             onChange={(s) => {
               const ws = { ...workspace, assumptions: { ...(workspace?.assumptions as Record<string, unknown>), revenue_streams: s } };
               setDetail((d) => d ? { ...d, workspace: ws } : d);
               debouncedPatch(ws);
             }}
           />
         ),
       },
       {
         id: "correlations",
         label: "Correlations",
         content: (
           <CorrelationMatrixEditor
             distributions={(workspace?.distributions ?? []) as DistributionConfig[]}
             correlationMatrix={(workspace?.correlation_matrix ?? []) as CorrelationEntry[]}
             editable
             onChange={(entries) => {
               const ws = { ...workspace, correlation_matrix: entries };
               setDetail((d) => d ? { ...d, workspace: ws } : d);
               debouncedPatch(ws);
             }}
           />
         ),
       },
     ]}
   />
   ```

   Where `workspace` is derived from `detail?.workspace`.

### Step 4: Run tests to verify they pass

Run: `cd apps/web && npx vitest run tests/pages/drafts-detail.test.tsx`
Expected: PASS.

### Step 5: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

### Step 6: Commit

```bash
git add apps/web/app/drafts/[id]/page.tsx apps/web/tests/pages/drafts-detail.test.tsx
git commit -m "feat: add structured editor tabs (Funding, Revenue, Correlations) to draft workspace"
```

---

## Task 6: Baseline Detail — "Edit Configuration" Button

**Files:**
- Modify: `apps/web/app/baselines/[id]/page.tsx:14,156` (imports + button placement)
- Modify: `apps/web/tests/pages/baselines-detail.test.tsx`

### Step 1: Write failing test

Add to `apps/web/tests/pages/baselines-detail.test.tsx`:

```tsx
it("renders Edit Configuration button", async () => {
  renderPage();
  await waitFor(() => {
    expect(screen.getByRole("button", { name: /Edit Configuration/i })).toBeInTheDocument();
  });
});

it("navigates to existing active draft when Edit Configuration is clicked", async () => {
  mockApi.drafts.list.mockResolvedValue({
    items: [{ draft_session_id: "draft-existing", status: "active" }],
    total: 1,
    limit: 50,
    offset: 0,
  });
  const user = userEvent.setup();
  renderPage();
  await waitFor(() => screen.getByRole("button", { name: /Edit Configuration/i }));
  await user.click(screen.getByRole("button", { name: /Edit Configuration/i }));
  await waitFor(() => {
    expect(mockPush).toHaveBeenCalledWith("/drafts/draft-existing?tab=funding");
  });
});

it("creates a new draft when no active draft exists", async () => {
  mockApi.drafts.list.mockResolvedValue({ items: [], total: 0, limit: 50, offset: 0 });
  mockApi.drafts.create.mockResolvedValue({ draft_session_id: "draft-new", status: "active", storage_path: "/tmp" });
  const user = userEvent.setup();
  renderPage();
  await waitFor(() => screen.getByRole("button", { name: /Edit Configuration/i }));
  await user.click(screen.getByRole("button", { name: /Edit Configuration/i }));
  await waitFor(() => {
    expect(mockApi.drafts.create).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith("/drafts/draft-new?tab=funding");
  });
});
```

Add `import userEvent from "@testing-library/user-event"` and `mockPush` to
the imports at the top.

### Step 2: Run tests to verify they fail

Run: `cd apps/web && npx vitest run tests/pages/baselines-detail.test.tsx`
Expected: FAIL — button not found.

### Step 3: Implement the Edit Configuration button

Modify `apps/web/app/baselines/[id]/page.tsx`:

1. **Add state** for the edit flow:
   ```typescript
   const [editLoading, setEditLoading] = useState(false);
   ```

2. **Add handler:**
   ```typescript
   async function handleEditConfig() {
     if (!tenantId) return;
     setEditLoading(true);
     try {
       // Check for existing active draft
       const draftsRes = await api.drafts.list(tenantId, {
         status: "active",
         parent_baseline_id: id,
       });
       if (draftsRes.items.length > 0) {
         router.push(`/drafts/${draftsRes.items[0].draft_session_id}?tab=funding`);
       } else {
         const newDraft = await api.drafts.create(tenantId, { parent_baseline_id: id });
         router.push(`/drafts/${newDraft.draft_session_id}?tab=funding`);
       }
     } catch (e) {
       toast.error(e instanceof Error ? e.message : "Failed to open editor");
     } finally {
       setEditLoading(false);
     }
   }
   ```

3. **Add button** near the "Run configuration" heading (around line 156), e.g.
   just above it or in a button row:
   ```tsx
   <div className="mb-4 flex gap-3">
     <VAButton variant="secondary" onClick={handleEditConfig} disabled={editLoading}>
       {editLoading ? "Opening…" : "Edit Configuration"}
     </VAButton>
     <VAButton variant="primary" onClick={() => setShowRunForm(!showRunForm)}>
       {showRunForm ? "Hide run form" : "Run model"}
     </VAButton>
   </div>
   ```

### Step 4: Run tests to verify they pass

Run: `cd apps/web && npx vitest run tests/pages/baselines-detail.test.tsx`
Expected: All tests PASS.

### Step 5: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

### Step 6: Commit

```bash
git add apps/web/app/baselines/[id]/page.tsx apps/web/tests/pages/baselines-detail.test.tsx
git commit -m "feat: add Edit Configuration button to baseline detail page with draft reuse"
```

---

## Task 7: Revenue Segment Stacked Bar Chart

**Files:**
- Modify: `apps/web/app/runs/[id]/page.tsx:11,346-381`
- Create: `apps/web/tests/pages/runs-segment-chart.test.tsx`

### Step 1: Write failing test

Create `apps/web/tests/pages/runs-segment-chart.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { mockApi, mockGetAuthContext } from "./setup";

import { ToastProvider } from "@/components/ui";
import RunDetailPage from "@/app/runs/[id]/page";

function renderPage() {
  return render(
    <ToastProvider>
      <RunDetailPage />
    </ToastProvider>,
  );
}

describe("RunDetailPage - Revenue Segment Chart", () => {
  beforeEach(() => {
    mockGetAuthContext.mockClear();
    mockGetAuthContext.mockResolvedValue({
      tenantId: "tenant-test",
      userId: "user-test",
      accessToken: "mock-token",
      tenantIdIsFallback: false,
    });
    mockApi.runs.get.mockResolvedValue({
      run_id: "run-1",
      baseline_id: "b-1",
      status: "completed",
      created_at: "2026-01-01T00:00:00Z",
    });
    mockApi.runs.getStatements.mockResolvedValue({
      income_statement: [{ label: "Revenue", P0: 100, P1: 200 }],
      balance_sheet: [],
      cash_flow: [],
      periods: ["P0", "P1"],
      revenue_by_segment: {
        saas: [80, 150],
        services: [20, 50],
      },
    });
    mockApi.runs.getKpis.mockResolvedValue([]);
  });

  it("renders the revenue by segment section with chart", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText(/Revenue by Segment/i)).toBeInTheDocument();
    });
    // Recharts renders an SVG — check that the chart container exists
    // The BarChart renders inside a div; segment names should appear in legend
    await waitFor(() => {
      expect(screen.getByText("saas")).toBeInTheDocument();
      expect(screen.getByText("services")).toBeInTheDocument();
    });
  });
});
```

### Step 2: Run test to verify it fails

Run: `cd apps/web && npx vitest run tests/pages/runs-segment-chart.test.tsx`
Expected: FAIL — no chart rendering, just the existing table.

Note: Recharts uses `ResizeObserver` internally. If tests fail with
`ResizeObserver is not defined`, add to `apps/web/tests/setup.ts`:
```typescript
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
};
```

### Step 3: Add stacked bar chart

Modify `apps/web/app/runs/[id]/page.tsx`:

1. **Add import** (after existing imports):
   ```typescript
   import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from "recharts";
   ```

2. **Add a color palette constant** near the top of the file:
   ```typescript
   const SEGMENT_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16"];
   ```

3. **Insert chart** before the existing segment table (above line 346).
   Transform `revenue_by_segment` into Recharts-compatible data:

   ```tsx
   {/* Revenue by Segment Chart */}
   {statements?.revenue_by_segment &&
     typeof statements.revenue_by_segment === "object" &&
     Object.keys(statements.revenue_by_segment as Record<string, unknown>).length > 1 && (() => {
       const segments = statements.revenue_by_segment as Record<string, number[]>;
       const segNames = Object.keys(segments);
       const chartData = periods.map((p, idx) => {
         const row: Record<string, string | number> = { period: p };
         for (const seg of segNames) {
           row[seg] = (segments[seg] ?? [])[idx] ?? 0;
         }
         return row;
       });
       return (
         <div className="mb-4" style={{ width: "100%", height: 300 }}>
           <ResponsiveContainer>
             <BarChart data={chartData}>
               <XAxis dataKey="period" tick={{ fontSize: 12 }} />
               <YAxis tick={{ fontSize: 12 }} />
               <Tooltip />
               <Legend />
               {segNames.map((seg, i) => (
                 <Bar key={seg} dataKey={seg} stackId="rev" fill={SEGMENT_COLORS[i % SEGMENT_COLORS.length]} />
               ))}
             </BarChart>
           </ResponsiveContainer>
         </div>
       );
     })()}
   ```

### Step 4: Run tests to verify they pass

Run: `cd apps/web && npx vitest run tests/pages/runs-segment-chart.test.tsx`
Expected: PASS.

### Step 5: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

### Step 6: Commit

```bash
git add apps/web/app/runs/[id]/page.tsx apps/web/tests/pages/runs-segment-chart.test.tsx apps/web/tests/setup.ts
git commit -m "feat: add stacked bar chart for revenue by segment on run results page"
```

---

## Task 8: ConsolidatedResults Enhancements

**Files:**
- Modify: `apps/web/components/ConsolidatedResults.tsx` (302 lines)
- Create: `apps/web/tests/components/ConsolidatedResults.test.tsx`

### Step 1: Write failing tests

Create `apps/web/tests/components/ConsolidatedResults.test.tsx`:

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConsolidatedResults } from "@/components/ConsolidatedResults";

const sampleResult = {
  consolidated_is: { income_statement: [{ label: "Revenue", P0: 100000 }] },
  consolidated_bs: { balance_sheet: [] },
  consolidated_cf: { cash_flow: [] },
  entity_results: [
    { entity_id: "entity-a", currency: "USD", ownership_pct: 100 },
    { entity_id: "entity-b", currency: "EUR", ownership_pct: 60 },
  ],
  minority_interest: {
    nci_profit: [5000, 6000, 7000],
    nci_equity: [20000, 26000, 33000],
  },
  eliminations: [
    { from_entity_id: "entity-a", to_entity_id: "entity-b", link_type: "revenue", amount_per_period: [10000, 12000] },
    { from_entity_id: "entity-a", to_entity_id: "entity-b", link_type: "loan", amount_per_period: [50000, 50000] },
  ],
  fx_rates_used: { "EUR/USD": 1.08 },
  integrity: { warnings: ["FX mismatch on entity-b"], errors: [] },
};

const entityRunMap = { "entity-a": "run-a", "entity-b": "run-b" };

describe("ConsolidatedResults", () => {
  it("renders entity breakdown with clickable rows when entityRunMap provided", () => {
    render(<ConsolidatedResults result={sampleResult} entityRunMap={entityRunMap} />);
    // Switch to Entity Breakdown tab — find and click it
    const tab = screen.getByText("Entity Breakdown");
    tab.click();
    // entity-a should be a link
    const link = screen.getByRole("link", { name: /entity-a/i });
    expect(link).toHaveAttribute("href", "/runs/run-a");
  });

  it("renders NCI line chart", () => {
    render(<ConsolidatedResults result={sampleResult} />);
    const tab = screen.getByText("NCI");
    tab.click();
    // Recharts renders SVG — look for the data values or container
    expect(screen.getByText(/NCI Share of Profit/i)).toBeInTheDocument();
  });

  it("renders IC elimination summary totals", () => {
    render(<ConsolidatedResults result={sampleResult} />);
    const tab = screen.getByText("IC Eliminations");
    tab.click();
    // Should show summary: revenue total = 22000, loan total = 100000
    expect(screen.getByText(/revenue/i)).toBeInTheDocument();
    // Check that a total row exists
    expect(screen.getByText(/Total/i)).toBeInTheDocument();
  });

  it("renders integrity warnings", () => {
    render(<ConsolidatedResults result={sampleResult} />);
    const tab = screen.getByText("FX & Integrity");
    tab.click();
    expect(screen.getByText(/FX mismatch/i)).toBeInTheDocument();
  });
});
```

### Step 2: Run tests to verify they fail

Run: `cd apps/web && npx vitest run tests/components/ConsolidatedResults.test.tsx`
Expected: FAIL — no `entityRunMap` prop, no link rendering, no totals row.

### Step 3: Implement enhancements

Modify `apps/web/components/ConsolidatedResults.tsx`:

1. **Update props** (line 91) to accept optional `entityRunMap`:
   ```typescript
   export function ConsolidatedResults({
     result,
     entityRunMap,
   }: {
     result: ConsolidatedRunResult;
     entityRunMap?: Record<string, string>;
   }) {
   ```

2. **Add imports:**
   ```typescript
   import Link from "next/link";
   import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
   ```

3. **Entity Breakdown tab** — make rows clickable when `entityRunMap` is
   provided. Wrap entity_id cell in `<Link href={/runs/${entityRunMap[e.entity_id]}}>`
   when the entity has a mapping. Otherwise plain text.

4. **NCI tab** — add a Recharts `<LineChart>` above or replacing the VACard
   grid for `nci_profit`:
   ```tsx
   const nciChartData = (nci?.nci_profit ?? []).map((v, i) => ({ period: `P${i}`, nci_profit: v }));
   // render <ResponsiveContainer><LineChart>...</LineChart></ResponsiveContainer>
   ```

5. **IC Eliminations tab** — add a summary footer row that groups by
   `link_type` and sums total amounts:
   ```tsx
   {/* Summary totals */}
   <tr className="border-t-2 border-va-border bg-va-surface font-medium">
     <td colSpan={3} className="px-3 py-2">Total</td>
     <td className="px-3 py-2 text-right font-mono">
       {fmt(elims.reduce((s, e) => s + (e.amount_per_period ?? []).reduce((a, b) => a + b, 0), 0))}
     </td>
   </tr>
   ```

6. **FX tab** — if `fx_rates_used` contains objects with `{ avg, closing }`,
   split into two columns. If values are plain numbers (current format), keep
   single Rate column. This makes the enhancement backwards-compatible.

### Step 4: Run tests to verify they pass

Run: `cd apps/web && npx vitest run tests/components/ConsolidatedResults.test.tsx`
Expected: All 4 tests PASS.

### Step 5: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

### Step 6: Commit

```bash
git add apps/web/components/ConsolidatedResults.tsx apps/web/tests/components/ConsolidatedResults.test.tsx
git commit -m "feat: enhance ConsolidatedResults with clickable entities, NCI chart, IC totals"
```

---

## Task 9: Org Structures Page — Pass entityRunMap

**Files:**
- Modify: `apps/web/app/org-structures/[orgId]/page.tsx:442`

**Reference:** Read the org-structures page to understand how `selectedRunResult`
is populated and what entity run data is available.

### Step 1: Write failing test (if page test exists) or manual verification

This is a small wiring change — pass the `entityRunMap` prop to
`ConsolidatedResults`. If the consolidated run result includes per-entity
`run_id` values, build the map from those. If not, the prop is simply omitted
and entity rows remain non-clickable (graceful degradation).

### Step 2: Implement

Modify `apps/web/app/org-structures/[orgId]/page.tsx` around line 442:

1. Build `entityRunMap` from the run result's entity data (if available):
   ```typescript
   const entityRunMap: Record<string, string> = {};
   for (const entity of selectedRunResult?.entity_results ?? []) {
     if ((entity as Record<string, unknown>).run_id) {
       entityRunMap[entity.entity_id] = String((entity as Record<string, unknown>).run_id);
     }
   }
   ```

2. Pass it to ConsolidatedResults:
   ```tsx
   <ConsolidatedResults
     result={selectedRunResult}
     entityRunMap={Object.keys(entityRunMap).length > 0 ? entityRunMap : undefined}
   />
   ```

### Step 3: Run full test suite

Run: `cd apps/web && npx vitest run`
Expected: All tests pass.

### Step 4: Commit

```bash
git add apps/web/app/org-structures/[orgId]/page.tsx
git commit -m "feat: pass entityRunMap to ConsolidatedResults for clickable entity breakdown"
```

---

## Sequencing Summary

| Task | Depends On | Files Created | Files Modified |
|------|-----------|---------------|----------------|
| 1. Infrastructure | — | — | package.json, api.ts, setup.tsx |
| 2. FundingEditor | 1 | FundingEditor.tsx, test | — |
| 3. RevenueStreamEditor | 1 | RevenueStreamEditor.tsx, test | — |
| 4. CorrelationMatrix edit | 1 | test | CorrelationMatrixEditor.tsx |
| 5. Draft workspace tabs | 2, 3, 4 | test | drafts/[id]/page.tsx |
| 6. Baseline Edit button | 1 | — | baselines/[id]/page.tsx, test |
| 7. Segment bar chart | 1 | test | runs/[id]/page.tsx, setup.ts |
| 8. ConsolidatedResults | 1 | test | ConsolidatedResults.tsx |
| 9. Org structures wiring | 8 | — | org-structures/[orgId]/page.tsx |

Tasks 2, 3, 4 are independent and can run in parallel.
Tasks 6, 7, 8 are independent and can run in parallel.
Task 5 depends on 2+3+4. Task 9 depends on 8.

---

## Verification Checklist

After all tasks are complete:

1. `cd apps/web && npx vitest run` — all unit/component tests pass
2. `cd apps/web && npx tsc --noEmit` — no TypeScript errors
3. `cd apps/web && npm run build` — Next.js production build succeeds
4. Manual smoke test: open baseline detail → click Edit Configuration → verify
   draft opens with Funding/Revenue/Correlations tabs
5. Manual smoke test: run results page → verify stacked bar chart renders
   above segment table
6. Manual smoke test: org structures → consolidated run → verify entity
   rows are clickable, NCI chart renders, IC totals row appears
