# Phase 6 — Frontend: DG Parity UI Components

## Overview

Four UI features to surface Phases 1-5 engine capabilities in the web app.
All data shapes already exist in the API — no backend changes needed.

**Stack:** Next.js 14 App Router, custom VA component library (Tailwind),
Supabase auth, `apps/web/lib/api.ts` client.

---

## Task 1 — Funding Configuration Panel

**Problem:** Users can't configure debt facilities, equity raises, or
dividend policy from the UI. The `model_config.assumptions.funding` field
exists but has no editor.

**Where it lives:** Baseline detail page (`/baselines/[id]/page.tsx`) or
draft workspace (`/drafts/[id]/page.tsx`). Add a "Funding" tab alongside
existing assumptions.

### Files

| # | File | Action |
|---|------|--------|
| 1 | `apps/web/components/FundingPanel.tsx` | CREATE |
| 2 | `apps/web/app/baselines/[id]/page.tsx` | MODIFY — add Funding tab |

### Component: `FundingPanel`

Three collapsible sections:

**A. Debt Facilities** — table with add/edit/delete rows
- Columns: Label, Type (term_loan / revolver / overdraft), Limit, Interest
  Rate, Is Cash Plug
- Expandable row: Draw Schedule (month + amount pairs), Repayment Schedule
  (month + amount pairs)
- Validation: limit > 0, 0 ≤ interest_rate ≤ 1, draw amounts ≤ limit

**B. Equity Raises** — simple table
- Columns: Label, Amount, Month
- Add/delete rows

**C. Dividend Policy** — radio group + value input
- Options: None, Fixed Amount ($/period), Payout Ratio (% of NI)
- When "none" selected, value input is hidden

### Data flow
- Read: `model_config.assumptions.funding` from baseline GET response
- Write: PATCH baseline with updated `model_config` (same as existing
  assumption editing pattern)

---

## Task 2 — Business Line Segmentation

**Problem:** Revenue streams have `business_line` and `market` fields but
no UI to set them. Run results include `revenue_by_segment` but it's not
displayed.

### Files

| # | File | Action |
|---|------|--------|
| 1 | `apps/web/app/baselines/[id]/page.tsx` | MODIFY — add business_line/market fields to revenue stream editor |
| 2 | `apps/web/app/runs/[id]/page.tsx` | MODIFY — add segment breakdown section |

### Baseline editor changes

Each revenue stream in the assumptions editor gains two optional fields:
- `business_line`: text input (free-form string)
- `market`: text input (free-form string)
- `launch_month`: number input (0-indexed month, optional)
- `ramp_up_months`: number input (optional, shown when launch_month set)
- `ramp_curve`: select (linear / s_curve / step, shown when ramp_up_months set)

### Run results changes

Below the existing IS table, add a "Revenue by Segment" section:
- Stacked bar chart (one bar per period, segments colored)
- Table below chart: rows = segments, columns = periods, values = revenue
- Data source: `revenue_by_segment` dict from run statements response

This requires the API to return `revenue_by_segment` in the statements
endpoint response. Currently `generate_statements` populates it on the
`Statements` dataclass. The runs router needs to include it in the
serialized response — **check if it's already there; if not, add it to
the runs router serialization** (small backend change, ~3 lines).

---

## Task 3 — MC Correlation Matrix Editor

**Problem:** The `correlation_matrix` field on ModelConfig supports
Cholesky-based correlated sampling (Phase 3), but there's no UI to define
driver-pair correlations.

### Files

| # | File | Action |
|---|------|--------|
| 1 | `apps/web/components/CorrelationMatrixEditor.tsx` | CREATE |
| 2 | `apps/web/app/baselines/[id]/page.tsx` | MODIFY — add Correlations tab |

### Component: `CorrelationMatrixEditor`

**Input:** list of driver refs (extracted from `model_config.distributions`)
and existing `correlation_matrix` entries.

**UI:** NxN grid (heatmap-style) where N = number of distribution refs.
- Diagonal cells = 1.0 (fixed, greyed out)
- Off-diagonal cells: click to edit, input accepts -1.0 to 1.0
- Symmetric: editing (A,B) auto-updates (B,A)
- Color scale: red (-1) → white (0) → blue (+1)
- Below grid: list view of non-zero pairs for accessibility

**Data shape:**
```typescript
{ ref_a: string; ref_b: string; rho: number }[]
```

**Validation:** rho must be in [-1, 1]. Matrix should be positive
semi-definite — warn (don't block) if eigenvalues go negative.

**When to show:** Only when `distributions` has ≥ 2 entries. Otherwise
show a message: "Add at least 2 driver distributions to configure
correlations."

---

## Task 4 — Consolidated Run Results View

**Problem:** The org-structures page triggers consolidated runs but doesn't
show detailed results: entity breakdowns, NCI, IC eliminations, FX rates.

### Files

| # | File | Action |
|---|------|--------|
| 1 | `apps/web/components/ConsolidatedResults.tsx` | CREATE |
| 2 | `apps/web/app/org-structures/[orgId]/page.tsx` | MODIFY — add results tab/section |

### Component: `ConsolidatedResults`

**Props:** consolidated run result from
`api.orgStructures.getRun(orgId, runId)`

**Layout:** Tabbed view with 5 tabs:

**A. Consolidated Statements**
- IS, BS, CF tables (same layout as individual run `/runs/[id]` page)
- Data source: `result.consolidated_is`, `result.consolidated_bs`,
  `result.consolidated_cf`

**B. Entity Breakdown**
- Table: rows = entity names, columns = key metrics (revenue, NI, total
  assets) per period
- Clicking an entity row links to its standalone run page

**C. NCI (Non-Controlling Interest)**
- Show `result.minority_interest.nci_profit` as a line chart
- Show `result.minority_interest.nci_equity` in a table
- Label which entities have NCI and their ownership %

**D. Intercompany Eliminations**
- Table of elimination entries: from → to, type, amount per period
- Summarize total eliminated revenue, expense, loan amounts

**E. FX & Integrity**
- Table of FX rates used: currency pair, avg rate, closing rate
- Integrity warnings/errors list (from `result.integrity`)

---

## Sequencing

| Task | Dependencies | Estimated Scope |
|------|-------------|-----------------|
| 1. Funding Panel | None | 1 new component, 1 page mod |
| 2. Business Line Segmentation | None (may need small API tweak) | 2 page mods |
| 3. Correlation Matrix Editor | None | 1 new component, 1 page mod |
| 4. Consolidated Results View | None | 1 new component, 1 page mod |

Tasks are independent and can be implemented in any order or in parallel.
Recommended order: 1 → 2 → 3 → 4 (funding and segmentation are highest
user value; correlation matrix is less frequently used; consolidated view
builds on familiarity with the results pattern).

---

## Patterns to Follow

All new components should follow existing conventions:

- `"use client"` directive for interactive pages
- Auth via `getAuthContext()` → `api.setAccessToken()` pattern
- Loading: `VASpinner` component
- Error display: inline alert with `text-va-danger`
- Form inputs: `VAInput`, `VASelect`, `VAButton`
- Cards: `VACard` for section containers
- Confirmations: `VAConfirmDialog` for destructive actions
- Toasts: `useToast()` for success/error feedback
- Colors: `va-blue` primary, `va-success`/`va-danger` for status
- Font: Inter for body, JetBrains Mono for numbers/code

---

## Out of Scope

- New API endpoints (data already exists in model_config)
- Schema changes (Phases 1-5 added all needed fields)
- Engine or statement generator changes
- New database tables or migrations
- Mobile responsiveness (follow existing breakpoint patterns)
