# Phase 6 Frontend — DG Parity UI Components: Design

**Date:** 2026-02-25
**Status:** Approved
**Depends on:** Phases 1-5 engine (complete), existing component library

---

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Edit pattern | Hybrid (read-only baseline + draft editor) | Preserves draft/commit versioning, audit trail, integrity checks |
| Draft reuse | Reuse active draft if one exists | Prevents orphaned drafts, lets users resume work |
| Charting library | Recharts | Lightweight, React-native, tree-shakeable (~40KB gz) |
| PSD validation | Client-side warning | Immediate feedback; warn but don't block save |

---

## 1. Edit Flow Architecture

Baseline detail page stays read-only. An "Edit Configuration" button creates
(or resumes) a draft with structured editor tabs. Users edit via forms, then
commit to create a new baseline version.

```
Baseline detail page (/baselines/[id])
│
├─ Read-only display (existing): FundingPanel, Revenue Streams, Correlations
│
└─ [Edit Configuration] button
     │
     ├─ Active draft exists for this baseline?
     │   ├─ YES → navigate to /drafts/{existingDraftId}?tab=funding
     │   └─ NO  → POST api.drafts.create({ parent_baseline_id: id })
     │            → navigate to /drafts/{newDraftId}?tab=funding
     │
     ▼
Draft workspace (/drafts/[id])
│
├─ Existing: Chat panel + proposals + AssumptionTree
│
├─ NEW: Structured editor tabs (alongside chat)
│   ├─ "Funding" tab      → FundingEditor component
│   ├─ "Revenue" tab      → RevenueStreamEditor component
│   └─ "Correlations" tab → CorrelationMatrixEditor (editable mode)
│
├─ Each tab edit → debounced PATCH api.drafts.patch(tenantId, id, { workspace })
│
└─ Commit → integrity checks → new baseline version
```

The `?tab=` query param deep-links to the relevant editor tab. Existing chat
and proposals continue to work alongside structured editors.

---

## 2. FundingEditor Component

**New file:** `apps/web/components/FundingEditor.tsx`

Replaces the read-only FundingPanel when in draft edit mode. Three collapsible
sections with full CRUD.

### Props

```typescript
interface FundingEditorProps {
  funding: FundingConfig | null;
  onChange: (updated: FundingConfig) => void;
}
```

### Sections

**A. Debt Facilities** — editable table with expandable rows
- Columns: Label (text), Type (select: term_loan/revolver/overdraft),
  Limit (number), Rate (number), Cash Plug (checkbox)
- [+ Add Facility] button appends empty row
- Each row has [Delete] icon (with VAConfirmDialog since facilities have schedules)
- Expandable chevron per row reveals:
  - Draw Schedule: mini table of (month, amount) pairs + [+ Add]
  - Repayment Schedule: mini table of (month, amount) pairs + [+ Add]

**B. Equity Raises** — simple editable table
- Columns: Label (text), Amount (number), Month (number)
- [+ Add Raise] button, [Delete] icon per row (direct delete, no confirm)

**C. Dividend Policy** — radio group + conditional input
- Options: None, Fixed Amount, Payout Ratio
- Value input hidden when "None" selected

### Validation (inline, per-field)

- `limit > 0`
- `0 ≤ interest_rate ≤ 1`
- draw amounts ≤ facility limit
- equity amount > 0
- payout_ratio in [0, 1] when selected

---

## 3. RevenueStreamEditor Component

**New file:** `apps/web/components/RevenueStreamEditor.tsx`

Converts the read-only revenue streams table into an editable form.

### Props

```typescript
interface RevenueStreamEditorProps {
  streams: RevenueStream[];
  onChange: (updated: RevenueStream[]) => void;
}
```

### Layout

Editable table — one row per revenue stream:
- Label (VAInput, text)
- Type (VASelect: recurring / one_time / usage_based / licensing)
- Business Line (VAInput, text, optional)
- Market (VAInput, text, optional)
- Launch Month (VAInput, number, optional)
- Ramp Up Months (VAInput, number — shown when launch_month is set)
- Ramp Curve (VASelect: linear / s_curve / step — shown when ramp_up_months is set)
- [Delete] icon button

[+ Add Stream] button appends row with empty defaults.

### Progressive disclosure

- `launch_month` is null → `ramp_up_months` hidden
- `ramp_up_months` is null → `ramp_curve` hidden

---

## 4. CorrelationMatrixEditor — Interactive Mode

**Modify existing:** `apps/web/components/CorrelationMatrixEditor.tsx`

Add an `editable` prop that enables interactive mode. The baseline page omits
it (or passes `false`); the draft workspace passes `true`.

### Extended props

```typescript
interface CorrelationMatrixEditorProps {
  distributions: DistributionConfig[];
  correlationMatrix: CorrelationEntry[];
  editable?: boolean;              // NEW — default false
  onChange?: (updated: CorrelationEntry[]) => void;  // NEW
}
```

### Interactive behavior (when editable=true)

- **Diagonal cells:** 1.00, greyed out, not clickable
- **Off-diagonal cells:** click → inline `<input type="number">`
  - Step: 0.05, min: -1, max: 1
  - On change: update (A,B) AND (B,A) symmetrically
  - Blur or Enter → commit value
  - Escape → cancel edit
- **Color coding:** unchanged (already implemented)
- **Non-zero pairs list:** updates reactively

### PSD validation (client-side)

On every edit:
1. Build full NxN matrix from correlation entries
2. Compute eigenvalues (power iteration or Jacobi — small N, no library needed)
3. All ≥ 0 → green check: "Matrix is valid"
4. Any < 0 → amber warning: "Matrix is not positive semi-definite. MC sampling
   may produce unexpected correlations."

Warning only — does not block save.

---

## 5. Consolidated Results Enhancements

**Modify existing:** `apps/web/components/ConsolidatedResults.tsx`

### Extended props

```typescript
interface ConsolidatedResultsProps {
  result: ConsolidatedRunResult;
  entityRunMap?: Record<string, string>;  // NEW: entity_id → run_id
}
```

### Tab-by-tab changes

**A. Statements** — no changes needed.

**B. Entity Breakdown** — 3 additions:
- New columns: revenue, net_income, total_assets per period
  (from per-entity run results if available)
- Clickable rows: `<Link>` to `/runs/{entityRunMap[entity_id]}`
- Hover state: cursor-pointer + bg highlight

**C. NCI** — 2 additions:
- Recharts `<LineChart>` for `nci_profit` over periods
  (replaces or supplements the VACard grid)
- Label which entities have NCI and their ownership %
- `nci_equity` table stays as-is

**D. IC Eliminations** — 1 addition:
- Summary footer row totaling eliminated amounts by type
  (revenue, expense, loan)

**E. FX & Integrity** — 1 addition:
- Split "Rate" column into "Avg Rate" and "Closing Rate"
- Requires backend to return `{ avg, closing }` per currency pair
  (if not available, flag as follow-up)

---

## 6. Revenue Segment Chart

**Modify existing:** `apps/web/app/runs/[id]/page.tsx`

Add a Recharts `<BarChart>` above the existing segment pivot table:

```typescript
<BarChart data={periodData}>
  <XAxis dataKey="period" />
  <YAxis />
  <Tooltip />
  <Legend />
  {segmentNames.map((seg, i) => (
    <Bar key={seg} dataKey={seg} stackId="rev" fill={COLORS[i]} />
  ))}
</BarChart>
```

The existing table stays below the chart. Data source is unchanged
(`statements.revenue_by_segment`).

---

## 7. Draft Workspace Page Changes

**Modify existing:** `apps/web/app/drafts/[id]/page.tsx`

### Layout changes

Add a VATabs section with structured editor tabs:

| Tab | Component | Data source |
|-----|-----------|-------------|
| Overview (default) | Existing AssumptionTree | `detail.workspace` |
| Funding | `<FundingEditor>` | `workspace.assumptions.funding` |
| Revenue | `<RevenueStreamEditor>` | `workspace.assumptions.revenue_streams` |
| Correlations | `<CorrelationMatrixEditor editable>` | `workspace.distributions` + `workspace.correlation_matrix` |

Active tab controlled by `?tab=` query param and local state.

### Save pattern

Each editor's `onChange` → debounced (300ms) PATCH to
`api.drafts.patch(tenantId, id, { workspace: updatedWorkspace })`.
Toast feedback on success: "Saved".

### Baseline detail page changes

`apps/web/app/baselines/[id]/page.tsx`:
- Add `[Edit Configuration]` VAButton below config header
- On click: `api.drafts.list(tenantId, { parent_baseline_id: id, status: 'active' })`
- If active draft found → navigate to it
- Otherwise → create new draft → navigate to it

---

## 8. New Dependencies

| Package | Purpose | Size |
|---------|---------|------|
| `recharts` | Stacked bar chart (segments), line chart (NCI) | ~40KB gzip |

No other new dependencies.

---

## 9. Files Changed Summary

| File | Action | Task |
|------|--------|------|
| `apps/web/components/FundingEditor.tsx` | CREATE | Task 1 |
| `apps/web/components/RevenueStreamEditor.tsx` | CREATE | Task 2 |
| `apps/web/components/CorrelationMatrixEditor.tsx` | MODIFY — add editable mode | Task 3 |
| `apps/web/components/ConsolidatedResults.tsx` | MODIFY — enrich all tabs | Task 4 |
| `apps/web/app/drafts/[id]/page.tsx` | MODIFY — add structured editor tabs | Tasks 1-3 |
| `apps/web/app/baselines/[id]/page.tsx` | MODIFY — add Edit Configuration button | Tasks 1-3 |
| `apps/web/app/runs/[id]/page.tsx` | MODIFY — add segment bar chart | Task 2 |
| `apps/web/app/org-structures/[orgId]/page.tsx` | MODIFY — pass entityRunMap | Task 4 |

---

## 10. Out of Scope

- New API endpoints (data already exists in model_config)
- Schema / migration changes
- Engine or statement generator changes
- Mobile responsiveness beyond existing breakpoint patterns
- FX avg/closing split if backend doesn't currently return it (flagged as follow-up)
