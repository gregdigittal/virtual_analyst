# AFS Phase 3 — Review Workflow & Tax Computation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-stage review workflow with comments/sign-off and tax computation (current/deferred tax, reconciliation, AI tax note) to the AFS module.

**Architecture:** Two new sub-modules added to the existing `apps/api/app/routers/afs.py` router and `apps/web/app/(app)/afs/[id]/` page group. Migration 0054 creates 4 tables. Backend adds 9 endpoints. Frontend adds 2 pages (review + tax) and wires navigation from sections page.

**Tech Stack:** Python/FastAPI backend, Next.js 14 (App Router) frontend, PostgreSQL (tenant-scoped RLS), LLMRouter for AI tax note drafting.

---

## Context

### Existing infrastructure (from Phase 1 + 2)

- **Router:** `apps/api/app/routers/afs.py` — ~1290 lines, 24+ endpoints
- **DB migrations:** `0052_afs.sql` (frameworks, engagements, trial balances, discrepancies, projections, prior AFS), `0053_afs_sections.sql` (sections, section history)
- **Services:** `apps/api/app/services/afs/disclosure_drafter.py` (AI drafting via LLMRouter), `tb_parser.py`, `pdf_extractor.py`
- **Frontend pages:** `/afs` (dashboard), `/afs/[id]/setup` (wizard), `/afs/[id]/sections` (AI disclosure editor)
- **Frontend API:** `apps/web/lib/api.ts` — `api.afs.*` namespace with 26 methods (lines 1397-1475)
- **Interfaces:** All AFS TypeScript interfaces at lines 1886-2010

### Key patterns to follow

- **ID generators:** `_xxx_id()` returning `f"prefix_{uuid.uuid4().hex[:14]}"` — use `arv_` for reviews, `arc_` for review comments, `atc_` for tax computations, `atd_` for temp differences
- **Tenant conn:** `async with tenant_conn(x_tenant_id) as conn:` with `X-Tenant-ID` header
- **RLS:** 4 policies per table (select, insert, update, delete) using `current_setting('app.tenant_id', true)`
- **Pydantic models:** Request bodies as `class XxxBody(BaseModel)` with Field validators
- **LLM integration:** `llm: LLMRouter = Depends(get_llm_router)` parameter, task label in `DEFAULT_POLICY`
- **Frontend auth:** `getAuthContext()` → `api.setAccessToken(ctx.accessToken)` → set `tenantId` state
- **Toast:** `const { toast } = useToast()` then `toast.success(msg)` / `toast.error(msg)`
- **UI components:** Import from `@/components/ui` barrel export (VAButton, VACard, VABadge, VAInput, VASpinner, VAEmptyState, VASelect)
- **Engagement status enum:** setup → ingestion → drafting → review → approved → published
- **Section status:** draft → reviewed → locked

---

## Task 1: Database Migration (0054)

**Files:**
- Create: `apps/api/app/db/migrations/0054_afs_reviews_tax.sql`

Create 4 new tables with composite primary keys and full RLS:

```sql
-- 0054_afs_reviews_tax.sql — AFS Phase 3: reviews, review comments, tax computations, temporary differences

-- ============================================================
-- AFS_REVIEWS (review workflow stages and sign-offs)
-- ============================================================
create table if not exists afs_reviews (
  tenant_id text not null references tenants(id) on delete cascade,
  review_id text not null,
  engagement_id text not null,
  stage text not null check (stage in ('preparer_review','manager_review','partner_signoff')),
  status text not null check (status in ('pending','approved','rejected','changes_requested')) default 'pending',
  submitted_by text references users(id) on delete set null,
  submitted_at timestamptz not null default now(),
  reviewed_by text references users(id) on delete set null,
  reviewed_at timestamptz,
  comments text,
  primary key (tenant_id, review_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_reviews_engagement on afs_reviews(tenant_id, engagement_id);

-- ============================================================
-- AFS_REVIEW_COMMENTS (threaded comments per section or review)
-- ============================================================
create table if not exists afs_review_comments (
  tenant_id text not null references tenants(id) on delete cascade,
  comment_id text not null,
  review_id text not null,
  section_id text,
  parent_comment_id text,
  body text not null,
  resolved boolean not null default false,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, comment_id),
  foreign key (tenant_id, review_id) references afs_reviews(tenant_id, review_id) on delete cascade,
  foreign key (tenant_id, section_id) references afs_sections(tenant_id, section_id) on delete set null
);
create index if not exists idx_afs_review_comments_review on afs_review_comments(tenant_id, review_id);

-- ============================================================
-- AFS_TAX_COMPUTATIONS (tax computation per entity)
-- ============================================================
create table if not exists afs_tax_computations (
  tenant_id text not null references tenants(id) on delete cascade,
  computation_id text not null,
  engagement_id text not null,
  entity_id text,
  jurisdiction text not null default 'ZA',
  statutory_rate numeric(8,4) not null default 0.27,
  taxable_income numeric(18,2) not null default 0,
  current_tax numeric(18,2) not null default 0,
  deferred_tax_json jsonb not null default '{}'::jsonb,
  reconciliation_json jsonb not null default '[]'::jsonb,
  tax_note_json jsonb,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, computation_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_tax_engagement on afs_tax_computations(tenant_id, engagement_id);

-- ============================================================
-- AFS_TEMPORARY_DIFFERENCES (deferred tax line items)
-- ============================================================
create table if not exists afs_temporary_differences (
  tenant_id text not null references tenants(id) on delete cascade,
  difference_id text not null,
  computation_id text not null,
  description text not null,
  carrying_amount numeric(18,2) not null default 0,
  tax_base numeric(18,2) not null default 0,
  difference numeric(18,2) not null default 0,
  deferred_tax_effect numeric(18,2) not null default 0,
  diff_type text not null check (diff_type in ('asset','liability')) default 'liability',
  primary key (tenant_id, difference_id),
  foreign key (tenant_id, computation_id) references afs_tax_computations(tenant_id, computation_id) on delete cascade
);
create index if not exists idx_afs_temp_diff_computation on afs_temporary_differences(tenant_id, computation_id);
```

Then add 4 RLS policies per table (same pattern as `0053_afs_sections.sql`):

```sql
-- RLS for afs_reviews
alter table afs_reviews enable row level security;
drop policy if exists "afs_reviews_select" on afs_reviews;
drop policy if exists "afs_reviews_insert" on afs_reviews;
drop policy if exists "afs_reviews_update" on afs_reviews;
drop policy if exists "afs_reviews_delete" on afs_reviews;
create policy "afs_reviews_select" on afs_reviews for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_reviews_insert" on afs_reviews for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_reviews_update" on afs_reviews for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_reviews_delete" on afs_reviews for delete using (tenant_id = current_setting('app.tenant_id', true));

-- (Repeat for afs_review_comments, afs_tax_computations, afs_temporary_differences — same pattern)
```

**Verification:** `python -c "from apps.api.app.routers import afs; print('OK')"` — should still pass (migration is SQL-only).

---

## Task 2: Backend Review Endpoints (5 endpoints)

**Files:**
- Modify: `apps/api/app/routers/afs.py` — add review endpoints at the end

Add these ID generators near the top:

```python
def _review_id() -> str:
    return f"arv_{uuid.uuid4().hex[:14]}"

def _review_comment_id() -> str:
    return f"arc_{uuid.uuid4().hex[:14]}"
```

Add these Pydantic request models:

```python
class SubmitReviewBody(BaseModel):
    stage: str = Field(...)  # preparer_review, manager_review, partner_signoff
    comments: str | None = Field(default=None, max_length=5000)

class ReviewActionBody(BaseModel):
    comments: str | None = Field(default=None, max_length=5000)

class CreateReviewCommentBody(BaseModel):
    review_id: str = Field(..., min_length=1)
    section_id: str | None = None
    parent_comment_id: str | None = None
    body: str = Field(..., min_length=1, max_length=10000)
```

Add these constants:

```python
VALID_REVIEW_STAGES = {"preparer_review", "manager_review", "partner_signoff"}
```

### Endpoints:

**1. `POST /engagements/{engagement_id}/reviews/submit`**
- Validate stage is in `VALID_REVIEW_STAGES`
- Verify engagement exists and all sections are status `reviewed` or `locked` (none in `draft`)
- Insert into `afs_reviews` with status `pending`
- Update engagement status to `review`
- Return the review row

**2. `GET /engagements/{engagement_id}/reviews`**
- List all reviews for engagement, ordered by `submitted_at DESC`
- Return `{ items: [...] }`

**3. `POST /engagements/{engagement_id}/reviews/{review_id}/approve`**
- Verify review exists and is `pending`
- Update review status to `approved`, set `reviewed_by` and `reviewed_at`
- If stage is `partner_signoff`, also update engagement status to `approved`
- Return the updated review row

**4. `POST /engagements/{engagement_id}/reviews/{review_id}/reject`**
- Verify review exists and is `pending`
- Accept optional `ReviewActionBody` with comments
- Update review status to `rejected`, set `reviewed_by`, `reviewed_at`, and append comments
- Return the updated review row

**5. `POST /engagements/{engagement_id}/reviews/comments`**
- Accept `CreateReviewCommentBody`
- Verify the `review_id` belongs to this engagement
- Insert into `afs_review_comments`
- Return the comment row

**6. `GET /engagements/{engagement_id}/reviews/{review_id}/comments`**
- List all comments for a review, ordered by `created_at ASC`
- Return `{ items: [...] }`

**Verification:** `python -c "from apps.api.app.routers import afs; print('OK')"` passes.

---

## Task 3: Backend Tax Computation Endpoints (4 endpoints)

**Files:**
- Modify: `apps/api/app/routers/afs.py` — add tax endpoints

Add ID generators:

```python
def _tax_computation_id() -> str:
    return f"atc_{uuid.uuid4().hex[:14]}"

def _temp_difference_id() -> str:
    return f"atd_{uuid.uuid4().hex[:14]}"
```

Add Pydantic models:

```python
class TaxComputationBody(BaseModel):
    entity_id: str | None = None
    jurisdiction: str = Field(default="ZA", max_length=10)
    statutory_rate: float = Field(default=0.27, ge=0, le=1)
    taxable_income: float = Field(default=0)
    adjustments: list[dict] | None = None  # optional list of {description, amount}

class TemporaryDifferenceBody(BaseModel):
    description: str = Field(..., min_length=1, max_length=500)
    carrying_amount: float = Field(default=0)
    tax_base: float = Field(default=0)
    diff_type: str = Field(default="liability")  # asset or liability

class GenerateTaxNoteBody(BaseModel):
    nl_instruction: str | None = Field(default=None, max_length=5000)
```

### Endpoints:

**1. `POST /engagements/{engagement_id}/tax/compute`**
- Accept `TaxComputationBody`
- Calculate `current_tax = taxable_income * statutory_rate`
- Build `reconciliation_json` from adjustments (each: `{ description, amount, effect }`)
- Insert into `afs_tax_computations`
- Return the computation row

**2. `GET /engagements/{engagement_id}/tax`**
- List all tax computations for engagement
- For each, include its temporary differences via a second query
- Return `{ items: [...] }` where each item has a `temporary_differences` array

**3. `POST /engagements/{engagement_id}/tax/{computation_id}/differences`**
- Accept `TemporaryDifferenceBody`
- Calculate `difference = carrying_amount - tax_base` and `deferred_tax_effect = difference * statutory_rate` (fetched from computation row)
- Validate `diff_type` is `asset` or `liability`
- Insert into `afs_temporary_differences`
- Update the parent computation's `deferred_tax_json` with totals
- Return the difference row

**4. `POST /engagements/{engagement_id}/tax/{computation_id}/generate-note`**
- Accept optional `GenerateTaxNoteBody`
- Load computation + differences + engagement framework
- Call LLM to generate a structured tax note (IAS 12 for IFRS, ASC 740 for US GAAP)
- Store result in `tax_note_json` on the computation row
- Return the updated computation

**LLM task label:** Add `"afs_tax_note"` to `DEFAULT_POLICY` in `apps/api/app/services/llm/router.py` with same providers as existing AFS tasks.

**Verification:** `python -c "from apps.api.app.routers import afs; print('OK')"` passes.

---

## Task 4: Tax Note AI Service

**Files:**
- Create: `apps/api/app/services/afs/tax_note_drafter.py`
- Modify: `apps/api/app/services/llm/router.py` — add `afs_tax_note` task label

### `tax_note_drafter.py`

One function:

```python
async def draft_tax_note(
    llm_router: LLMRouter,
    tenant_id: str,
    framework_name: str,
    standard: str,
    computation: dict,
    differences: list[dict],
    nl_instruction: str | None = None,
) -> LLMResult:
```

- Build a prompt that includes:
  - The applicable tax standard (IAS 12 for IFRS, ASC 740 for US GAAP)
  - Tax computation data (taxable income, statutory rate, current tax)
  - All temporary differences with their deferred tax effects
  - Reconciliation items
  - Optional NL instruction from user
- Request structured JSON output: `{ title, paragraphs: [{type, content}], references: [], current_tax_table: {...}, deferred_tax_table: {...}, reconciliation_table: {...} }`
- Use task label `afs_tax_note`

### LLM Router update

In `DEFAULT_POLICY` dict (in `apps/api/app/services/llm/router.py`), add:

```python
"afs_tax_note": [
    {"priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5"},
    {"priority": 2, "provider": "openai", "model": "gpt-4o"},
],
```

**Verification:** `python -c "from apps.api.app.services.afs.tax_note_drafter import draft_tax_note; print('OK')"` passes.

---

## Task 5: Frontend TypeScript Interfaces & API Methods

**Files:**
- Modify: `apps/web/lib/api.ts`

### New interfaces (add after `AFSValidationResult` at line ~2010):

```typescript
export interface AFSReview {
  review_id: string;
  engagement_id: string;
  stage: string;
  status: string;
  submitted_by: string | null;
  submitted_at: string;
  reviewed_by: string | null;
  reviewed_at: string | null;
  comments: string | null;
}

export interface AFSReviewComment {
  comment_id: string;
  review_id: string;
  section_id: string | null;
  parent_comment_id: string | null;
  body: string;
  resolved: boolean;
  created_by: string | null;
  created_at: string;
}

export interface AFSTaxComputation {
  computation_id: string;
  engagement_id: string;
  entity_id: string | null;
  jurisdiction: string;
  statutory_rate: number;
  taxable_income: number;
  current_tax: number;
  deferred_tax_json: Record<string, unknown>;
  reconciliation_json: Record<string, unknown>[];
  tax_note_json: Record<string, unknown> | null;
  temporary_differences?: AFSTemporaryDifference[];
  created_by: string | null;
  created_at: string;
  updated_at: string;
  llm_cost_usd?: number;
  llm_tokens?: number;
}

export interface AFSTemporaryDifference {
  difference_id: string;
  computation_id: string;
  description: string;
  carrying_amount: number;
  tax_base: number;
  difference: number;
  deferred_tax_effect: number;
  diff_type: string;
}
```

### New API methods (add inside `afs: { ... }` before the closing `},`):

```typescript
    // Reviews
    submitReview: (tenantId: string, engagementId: string, body: { stage: string; comments?: string }) =>
      request<AFSReview>(`/api/v1/afs/engagements/${eU(engagementId)}/reviews/submit`, { tenantId, method: "POST", body }),
    listReviews: (tenantId: string, engagementId: string) =>
      request<{ items: AFSReview[] }>(`/api/v1/afs/engagements/${eU(engagementId)}/reviews`, { tenantId }),
    approveReview: (tenantId: string, engagementId: string, reviewId: string, body?: { comments?: string }) =>
      request<AFSReview>(`/api/v1/afs/engagements/${eU(engagementId)}/reviews/${eU(reviewId)}/approve`, { tenantId, method: "POST", body }),
    rejectReview: (tenantId: string, engagementId: string, reviewId: string, body?: { comments?: string }) =>
      request<AFSReview>(`/api/v1/afs/engagements/${eU(engagementId)}/reviews/${eU(reviewId)}/reject`, { tenantId, method: "POST", body }),
    listReviewComments: (tenantId: string, engagementId: string, reviewId: string) =>
      request<{ items: AFSReviewComment[] }>(`/api/v1/afs/engagements/${eU(engagementId)}/reviews/${eU(reviewId)}/comments`, { tenantId }),
    createReviewComment: (tenantId: string, engagementId: string, body: { review_id: string; section_id?: string; parent_comment_id?: string; body: string }) =>
      request<AFSReviewComment>(`/api/v1/afs/engagements/${eU(engagementId)}/reviews/comments`, { tenantId, method: "POST", body }),

    // Tax
    computeTax: (tenantId: string, engagementId: string, body: { jurisdiction?: string; statutory_rate?: number; taxable_income: number; adjustments?: { description: string; amount: number }[] }) =>
      request<AFSTaxComputation>(`/api/v1/afs/engagements/${eU(engagementId)}/tax/compute`, { tenantId, method: "POST", body }),
    listTaxComputations: (tenantId: string, engagementId: string) =>
      request<{ items: AFSTaxComputation[] }>(`/api/v1/afs/engagements/${eU(engagementId)}/tax`, { tenantId }),
    addTemporaryDifference: (tenantId: string, engagementId: string, computationId: string, body: { description: string; carrying_amount: number; tax_base: number; diff_type?: string }) =>
      request<AFSTemporaryDifference>(`/api/v1/afs/engagements/${eU(engagementId)}/tax/${eU(computationId)}/differences`, { tenantId, method: "POST", body }),
    generateTaxNote: (tenantId: string, engagementId: string, computationId: string, body?: { nl_instruction?: string }) =>
      request<AFSTaxComputation>(`/api/v1/afs/engagements/${eU(engagementId)}/tax/${eU(computationId)}/generate-note`, { tenantId, method: "POST", body }),
```

Note: check if `encodeURIComponent` is aliased as `eU` or used inline in existing code. Match existing pattern.

**Verification:** `cd apps/web && npx tsc --noEmit` passes (or `npx next build`).

---

## Task 6: Review Workflow Page

**Files:**
- Create: `apps/web/app/(app)/afs/[id]/review/page.tsx`

### Page layout:

Split into three areas:

1. **Header:** Back arrow → `/afs/{id}/sections`, engagement name + "Review Workflow" title, status badge
2. **Review timeline:** Vertical list of review stages (Preparer Review → Manager Review → Partner Sign-off), each with status badge
3. **Active review panel:** Comments thread + action buttons (Approve / Request Changes)

### Behaviour:

- Load engagement + reviews + sections on mount (via `getAuthContext()` pattern)
- Show 3 review stages as cards (preparer_review, manager_review, partner_signoff)
  - Completed stages: green checkmark, reviewer name, timestamp
  - Current/pending stage: highlighted, with action buttons
  - Future stages: greyed out
- **Submit for Review** button: Only enabled when all sections are `reviewed` or `locked`
  - Calls `api.afs.submitReview(tenantId, engagementId, { stage: "preparer_review" })`
  - Toast success
- **Approve** button on pending review: Calls `api.afs.approveReview()`
- **Reject** button on pending review: Opens text area for comments, calls `api.afs.rejectReview()`
- Comments section per review: Thread of `AFSReviewComment`, add comment form at bottom
- When partner_signoff is approved, show "Engagement Approved" celebration state, update engagement status

### UI components used:

- `VACard`, `VAButton`, `VABadge` (success/warning/danger/violet), `VASpinner`, `VAEmptyState`, `useToast`
- Textarea for review comments

**Verification:** `npx next build` passes.

---

## Task 7: Tax Computation Page

**Files:**
- Create: `apps/web/app/(app)/afs/[id]/tax/page.tsx`

### Page layout:

Split into:

1. **Header:** Back arrow → `/afs/{id}/sections`, engagement name + "Tax Computation" title
2. **Computation form:** Inputs for jurisdiction, statutory rate, taxable income, adjustments
3. **Temporary differences table:** Rows with description, carrying amount, tax base, difference, deferred tax effect, type (asset/liability)
4. **Tax note preview:** Generated tax note content (JSON → rendered paragraphs, same pattern as section content in sections page)

### Behaviour:

- Load engagement + existing tax computations on mount
- If no computation exists, show form to create one:
  - Jurisdiction dropdown (ZA, US, GB, etc.)
  - Statutory rate (decimal input, e.g. 0.27)
  - Taxable income (number input)
  - Optional adjustments list (add/remove rows: description + amount)
  - "Compute" button → calls `api.afs.computeTax()`
- If computation exists, show:
  - Summary card: taxable income, statutory rate, current tax, effective rate
  - Reconciliation table from `reconciliation_json`
  - Temporary differences table with "Add Difference" form
  - "Generate Tax Note" button → calls `api.afs.generateTaxNote()`
  - Tax note preview (if `tax_note_json` exists)

### UI components:

- `VACard`, `VAButton`, `VABadge`, `VAInput`, `VASpinner`, `useToast`
- Table built with standard HTML `<table>` styled with Tailwind

**Verification:** `npx next build` passes.

---

## Task 8: Navigation Wiring

**Files:**
- Modify: `apps/web/app/(app)/afs/[id]/sections/page.tsx` — add Review and Tax nav links in header

### Changes:

In the sections page header (line ~185), add navigation buttons to Review and Tax pages:

```tsx
<VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/review`)}>
  Review
</VAButton>
<VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/tax`)}>
  Tax
</VAButton>
```

Also update the dashboard page (`/afs/page.tsx`) to show appropriate links based on engagement status — engagements in `review` or `approved` status should link to the review page.

**Verification:** `npx next build` passes.

---

## Task 9: Build & Import Verification

**Files:** None (verification only)

### Steps:

1. Run: `python -c "from apps.api.app.routers import afs; print('OK')"`
   - Expected: `OK`

2. Run: `python -c "from apps.api.app.services.afs.tax_note_drafter import draft_tax_note; print('OK')"`
   - Expected: `OK`

3. Run: `cd apps/web && npx next build`
   - Expected: Build succeeds with no errors

4. Run: `cd apps/web && npx vitest run`
   - Expected: All existing tests pass (140/140 or more)

If any fail, fix and re-verify.

---

## Execution Order

```
Task 1 (Migration 0054)           ─── first (DB schema)
Task 2 (Review endpoints)         ─── after Task 1
Task 3 (Tax endpoints)            ─── after Task 1 (parallel with Task 2)
Task 4 (Tax note AI service)      ─── after Task 3
Task 5 (Frontend API methods)     ─── after Tasks 2+3+4
Task 6 (Review page)              ─── after Task 5
Task 7 (Tax page)                 ─── after Task 5 (parallel with Task 6)
Task 8 (Navigation wiring)        ─── after Tasks 6+7
Task 9 (Build verification)       ─── last
```

Tasks 2 and 3 can be parallelized. Tasks 6 and 7 can be parallelized. All others are sequential.
