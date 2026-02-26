# AFS Module Phase 1 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the foundational AFS module — database tables, backend CRUD API, frontend API client, dashboard (engagement list + create), and engagement setup wizard with dual-source data ingestion.

**Architecture:** New migration `0052_afs.sql` creates all Phase 1 tables. New FastAPI router `afs.py` provides CRUD endpoints for frameworks, engagements, trial balances, and prior AFS uploads. Frontend gets an `afs` namespace in `api.ts` and replaces the stub `/afs` page with a real engagement dashboard. An engagement setup page at `/afs/[id]/setup` provides a multi-step wizard for framework selection, data upload, and source reconciliation.

**Tech Stack:** PostgreSQL + asyncpg (backend), FastAPI + Pydantic (API), Next.js 14 App Router + TypeScript (frontend), Supabase Storage via ArtifactStore (file storage)

---

### Task 1: Database Migration

**Files:**
- Create: `apps/api/app/db/migrations/0052_afs.sql`

**What to build:**

Create migration `0052_afs.sql` with these tables (all tenant-scoped with RLS):

**afs_frameworks** — Accounting standard definitions:
```sql
create table if not exists afs_frameworks (
  tenant_id text not null references tenants(id) on delete cascade,
  framework_id text not null,
  name text not null,
  standard text not null check (standard in ('ifrs','ifrs_sme','us_gaap','sa_companies_act','custom')),
  version text not null default '1.0',
  jurisdiction text,
  disclosure_schema_json jsonb,
  statement_templates_json jsonb,
  is_builtin boolean not null default false,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, framework_id)
);
create index if not exists idx_afs_frameworks_tenant on afs_frameworks(tenant_id);
```

**afs_disclosure_items** — Disclosure checklist items per framework:
```sql
create table if not exists afs_disclosure_items (
  tenant_id text not null references tenants(id) on delete cascade,
  item_id text not null,
  framework_id text not null,
  section text not null,
  reference text,
  description text not null,
  required boolean not null default true,
  applicable_entity_types text[],
  primary key (tenant_id, item_id),
  foreign key (tenant_id, framework_id) references afs_frameworks(tenant_id, framework_id) on delete cascade
);
create index if not exists idx_afs_disclosure_items_framework on afs_disclosure_items(tenant_id, framework_id);
```

**afs_engagements** — One AFS engagement per entity per period:
```sql
create table if not exists afs_engagements (
  tenant_id text not null references tenants(id) on delete cascade,
  engagement_id text not null,
  entity_name text not null,
  framework_id text not null,
  period_start date not null,
  period_end date not null,
  prior_engagement_id text,
  status text not null check (status in ('setup','ingestion','drafting','review','approved','published')) default 'setup',
  base_source text check (base_source in ('pdf','excel','va_baseline')),
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, engagement_id),
  foreign key (tenant_id, framework_id) references afs_frameworks(tenant_id, framework_id) on delete restrict
);
create index if not exists idx_afs_engagements_tenant on afs_engagements(tenant_id);
create index if not exists idx_afs_engagements_status on afs_engagements(tenant_id, status);
```

**afs_trial_balances** — Imported trial balance data:
```sql
create table if not exists afs_trial_balances (
  tenant_id text not null references tenants(id) on delete cascade,
  trial_balance_id text not null,
  engagement_id text not null,
  entity_id text,
  source text not null check (source in ('va_baseline','upload','connector','pdf_extracted')),
  data_json jsonb not null default '[]'::jsonb,
  mapped_accounts_json jsonb,
  period_months text[],
  is_partial boolean not null default false,
  uploaded_at timestamptz not null default now(),
  primary key (tenant_id, trial_balance_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_trial_balances_engagement on afs_trial_balances(tenant_id, engagement_id);
```

**afs_prior_afs** — Prior-year AFS uploads (PDF and/or Excel):
```sql
create table if not exists afs_prior_afs (
  tenant_id text not null references tenants(id) on delete cascade,
  prior_afs_id text not null,
  engagement_id text not null,
  source_type text not null check (source_type in ('pdf','excel')),
  filename text not null,
  file_size integer,
  extracted_json jsonb,
  upload_path text,
  uploaded_at timestamptz not null default now(),
  primary key (tenant_id, prior_afs_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_prior_afs_engagement on afs_prior_afs(tenant_id, engagement_id);
```

**afs_source_discrepancies** — PDF vs Excel reconciliation:
```sql
create table if not exists afs_source_discrepancies (
  tenant_id text not null references tenants(id) on delete cascade,
  discrepancy_id text not null,
  engagement_id text not null,
  line_item text not null,
  pdf_value numeric,
  excel_value numeric,
  difference numeric,
  resolution text check (resolution in ('use_pdf','use_excel','noted')),
  resolution_note text,
  resolved_by text references users(id) on delete set null,
  resolved_at timestamptz,
  primary key (tenant_id, discrepancy_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_source_discrepancies_engagement on afs_source_discrepancies(tenant_id, engagement_id);
```

**afs_month_projections** — AI-projected missing months:
```sql
create table if not exists afs_month_projections (
  tenant_id text not null references tenants(id) on delete cascade,
  projection_id text not null,
  engagement_id text not null,
  month text not null,
  basis_description text not null,
  projected_data_json jsonb not null default '{}'::jsonb,
  is_estimate boolean not null default true,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, projection_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_month_projections_engagement on afs_month_projections(tenant_id, engagement_id);
```

Then add RLS policies for all 7 tables — same pattern as budgets migration (`enable row level security`, drop/create 4 policies per table: select, insert, update, delete using `tenant_id = current_setting('app.tenant_id', true)`).

**Step 1:** Create the migration file with all 7 tables + indexes + RLS policies.

**Step 2:** Commit:
```bash
git add apps/api/app/db/migrations/0052_afs.sql
git commit -m "feat(afs): add Phase 1 database migration — 7 tables with RLS"
```

---

### Task 2: Backend AFS Router — Frameworks & Engagements

**Files:**
- Create: `apps/api/app/routers/afs.py`
- Modify: `apps/api/app/main.py` (add router import + include)

**What to build:**

Create `apps/api/app/routers/afs.py` with `router = APIRouter(prefix="/afs", tags=["afs"])`.

**ID generators:**
```python
def _framework_id() -> str:
    return f"afw_{uuid.uuid4().hex[:14]}"

def _engagement_id() -> str:
    return f"aen_{uuid.uuid4().hex[:14]}"

def _tb_id() -> str:
    return f"atb_{uuid.uuid4().hex[:14]}"

def _prior_afs_id() -> str:
    return f"apa_{uuid.uuid4().hex[:14]}"

def _discrepancy_id() -> str:
    return f"asd_{uuid.uuid4().hex[:14]}"

def _projection_id() -> str:
    return f"amp_{uuid.uuid4().hex[:14]}"
```

**Pydantic models:**
```python
class CreateFrameworkBody(BaseModel):
    name: str
    standard: str  # ifrs, ifrs_sme, us_gaap, sa_companies_act, custom
    version: str = "1.0"
    jurisdiction: str | None = None
    disclosure_schema_json: dict | None = None
    statement_templates_json: dict | None = None

class CreateEngagementBody(BaseModel):
    entity_name: str
    framework_id: str
    period_start: str  # ISO date
    period_end: str
    prior_engagement_id: str | None = None
```

**Endpoints — Frameworks:**
- `GET /afs/frameworks` — List frameworks for tenant (include built-in + custom)
- `POST /afs/frameworks` — Create custom framework
- `GET /afs/frameworks/{framework_id}` — Get framework detail
- `GET /afs/frameworks/{framework_id}/checklist` — List disclosure items
- `POST /afs/frameworks/seed` — Seed 4 built-in frameworks (IFRS, IFRS for SMEs, US GAAP, SA Companies Act) with `ON CONFLICT DO NOTHING`, similar to workflow template seed pattern

**Endpoints — Engagements:**
- `POST /afs/engagements` — Create engagement (validates framework_id exists)
- `GET /afs/engagements` — List engagements with pagination (`limit`, `offset`, optional `status` filter)
- `GET /afs/engagements/{engagement_id}` — Get engagement detail
- `PATCH /afs/engagements/{engagement_id}` — Update engagement (status, base_source, entity_name)
- `DELETE /afs/engagements/{engagement_id}` — Delete engagement

All endpoints use the standard pattern:
```python
@router.post("/engagements", status_code=201)
async def create_engagement(
    body: CreateEngagementBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    _: None = require_role(*ROLES_CAN_WRITE),
) -> dict[str, Any]:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        # validate framework exists
        # insert engagement
        # return created engagement
```

**Register router in main.py:**
```python
# In imports line:
from apps.api.app.routers import ... afs
# After board_packs include:
app.include_router(afs.router, prefix="/api/v1")
```

**Step 1:** Create `afs.py` with all framework + engagement endpoints.
**Step 2:** Add import and `include_router` to `main.py`.
**Step 3:** Commit:
```bash
git add apps/api/app/routers/afs.py apps/api/app/main.py
git commit -m "feat(afs): add backend router for frameworks and engagements"
```

---

### Task 3: Backend AFS Router — Data Ingestion Endpoints

**Files:**
- Modify: `apps/api/app/routers/afs.py`

**What to build:**

Add data ingestion endpoints to the existing `afs.py` router:

**Trial Balance:**
- `POST /afs/engagements/{eid}/trial-balance` — Upload trial balance (UploadFile for Excel/CSV, or JSON body for VA baseline link). Stores file in ArtifactStore, parses basic structure into `data_json`. Detects `period_months` and `is_partial`.
- `GET /afs/engagements/{eid}/trial-balance` — List trial balances for engagement
- `POST /afs/engagements/{eid}/trial-balance/map` — Placeholder for AI-assisted account mapping (returns echo for now)

**Prior AFS:**
- `POST /afs/engagements/{eid}/prior-afs` — Upload prior AFS (PDF or Excel). Accepts `UploadFile`. Stores in ArtifactStore. Records metadata in `afs_prior_afs`. Multiple uploads allowed (one PDF + one Excel).
- `GET /afs/engagements/{eid}/prior-afs` — List uploaded prior AFS for engagement
- `POST /afs/engagements/{eid}/prior-afs/reconcile` — Compare PDF vs Excel extracted data, generate discrepancy rows in `afs_source_discrepancies`. For Phase 1, this stubs the reconciliation logic (returns mock discrepancies based on the uploaded data). Full AI reconciliation in Phase 2.
- `POST /afs/engagements/{eid}/base-source` — Set `base_source` on engagement (`pdf`, `excel`, or `va_baseline`)

**Discrepancies:**
- `GET /afs/engagements/{eid}/discrepancies` — List discrepancies for engagement
- `PATCH /afs/engagements/{eid}/discrepancies/{did}` — Resolve a discrepancy (body: `{ resolution: "use_pdf"|"use_excel"|"noted", resolution_note: str }`)

**Projections:**
- `POST /afs/engagements/{eid}/projections` — Create month projection (body: `{ month: "YYYY-MM", basis_description: str }`). Phase 1 stores the description; AI generation in Phase 2.
- `GET /afs/engagements/{eid}/projections` — List projections for engagement

File upload pattern follows documents.py: `file: UploadFile`, read with 10MB size check, store via `ArtifactStore.save()`, record metadata in DB.

**Step 1:** Add all data ingestion endpoints to `afs.py`.
**Step 2:** Commit:
```bash
git add apps/api/app/routers/afs.py
git commit -m "feat(afs): add data ingestion endpoints — trial balance, prior AFS, discrepancies, projections"
```

---

### Task 4: Frontend API Client — AFS Namespace

**Files:**
- Modify: `apps/web/lib/api.ts`

**What to build:**

Add TypeScript interfaces and `afs` namespace to `api.ts`.

**Interfaces (add near the other type exports):**
```typescript
export interface AFSFramework {
  framework_id: string;
  name: string;
  standard: string;
  version: string;
  jurisdiction: string | null;
  is_builtin: boolean;
  created_at: string;
}

export interface AFSEngagement {
  engagement_id: string;
  entity_name: string;
  framework_id: string;
  period_start: string;
  period_end: string;
  status: string;
  base_source: string | null;
  created_at: string;
  updated_at: string;
}

export interface AFSTrialBalance {
  trial_balance_id: string;
  engagement_id: string;
  source: string;
  period_months: string[] | null;
  is_partial: boolean;
  uploaded_at: string;
}

export interface AFSPriorAFS {
  prior_afs_id: string;
  engagement_id: string;
  source_type: string;
  filename: string;
  file_size: number | null;
  uploaded_at: string;
}

export interface AFSDiscrepancy {
  discrepancy_id: string;
  engagement_id: string;
  line_item: string;
  pdf_value: number | null;
  excel_value: number | null;
  difference: number | null;
  resolution: string | null;
  resolution_note: string | null;
}

export interface AFSProjection {
  projection_id: string;
  month: string;
  basis_description: string;
  is_estimate: boolean;
}
```

**Namespace (add after the last namespace):**
```typescript
afs: {
  // Frameworks
  listFrameworks: (tenantId: string) =>
    request<{ items: AFSFramework[] }>("/api/v1/afs/frameworks", { tenantId }),
  seedFrameworks: (tenantId: string) =>
    request<{ seeded: number }>("/api/v1/afs/frameworks/seed", { tenantId, method: "POST" }),
  getFramework: (tenantId: string, frameworkId: string) =>
    request<AFSFramework>(`/api/v1/afs/frameworks/${euc(frameworkId)}`, { tenantId }),

  // Engagements
  listEngagements: (tenantId: string, opts?: { limit?: number; offset?: number; status?: string }) => {
    const p = new URLSearchParams();
    if (opts?.limit != null) p.set("limit", String(opts.limit));
    if (opts?.offset != null) p.set("offset", String(opts.offset));
    if (opts?.status) p.set("status", opts.status);
    const qs = p.toString();
    return request<{ items: AFSEngagement[] }>(`/api/v1/afs/engagements${qs ? `?${qs}` : ""}`, { tenantId });
  },
  createEngagement: (tenantId: string, body: { entity_name: string; framework_id: string; period_start: string; period_end: string }) =>
    request<AFSEngagement>("/api/v1/afs/engagements", { tenantId, method: "POST", body }),
  getEngagement: (tenantId: string, engagementId: string) =>
    request<AFSEngagement>(`/api/v1/afs/engagements/${euc(engagementId)}`, { tenantId }),
  updateEngagement: (tenantId: string, engagementId: string, body: Record<string, unknown>) =>
    request<AFSEngagement>(`/api/v1/afs/engagements/${euc(engagementId)}`, { tenantId, method: "PATCH", body }),
  deleteEngagement: (tenantId: string, engagementId: string) =>
    request<void>(`/api/v1/afs/engagements/${euc(engagementId)}`, { tenantId, method: "DELETE" }),

  // Trial Balance
  uploadTrialBalance: (tenantId: string, engagementId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return requestForm<AFSTrialBalance>(`/api/v1/afs/engagements/${euc(engagementId)}/trial-balance`, { tenantId, body: form });
  },
  listTrialBalances: (tenantId: string, engagementId: string) =>
    request<{ items: AFSTrialBalance[] }>(`/api/v1/afs/engagements/${euc(engagementId)}/trial-balance`, { tenantId }),

  // Prior AFS
  uploadPriorAFS: (tenantId: string, engagementId: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return requestForm<AFSPriorAFS>(`/api/v1/afs/engagements/${euc(engagementId)}/prior-afs`, { tenantId, body: form });
  },
  listPriorAFS: (tenantId: string, engagementId: string) =>
    request<{ items: AFSPriorAFS[] }>(`/api/v1/afs/engagements/${euc(engagementId)}/prior-afs`, { tenantId }),
  reconcile: (tenantId: string, engagementId: string) =>
    request<{ discrepancies: AFSDiscrepancy[] }>(`/api/v1/afs/engagements/${euc(engagementId)}/prior-afs/reconcile`, { tenantId, method: "POST" }),
  setBaseSource: (tenantId: string, engagementId: string, baseSource: string) =>
    request<AFSEngagement>(`/api/v1/afs/engagements/${euc(engagementId)}/base-source`, { tenantId, method: "POST", body: { base_source: baseSource } }),

  // Discrepancies
  listDiscrepancies: (tenantId: string, engagementId: string) =>
    request<{ items: AFSDiscrepancy[] }>(`/api/v1/afs/engagements/${euc(engagementId)}/discrepancies`, { tenantId }),
  resolveDiscrepancy: (tenantId: string, engagementId: string, discrepancyId: string, body: { resolution: string; resolution_note: string }) =>
    request<AFSDiscrepancy>(`/api/v1/afs/engagements/${euc(engagementId)}/discrepancies/${euc(discrepancyId)}`, { tenantId, method: "PATCH", body }),

  // Projections
  createProjection: (tenantId: string, engagementId: string, body: { month: string; basis_description: string }) =>
    request<AFSProjection>(`/api/v1/afs/engagements/${euc(engagementId)}/projections`, { tenantId, method: "POST", body }),
  listProjections: (tenantId: string, engagementId: string) =>
    request<{ items: AFSProjection[] }>(`/api/v1/afs/engagements/${euc(engagementId)}/projections`, { tenantId }),
},
```

Note: `euc` is `encodeURIComponent` — check if the codebase already has a shorthand; if not, add `const euc = encodeURIComponent;` at the top of the api object or use the full function name.

**Step 1:** Add interfaces and namespace to `api.ts`.
**Step 2:** Commit:
```bash
git add apps/web/lib/api.ts
git commit -m "feat(afs): add frontend API client namespace for AFS module"
```

---

### Task 5: Frontend — AFS Dashboard Page (Replace Stub)

**Files:**
- Modify: `apps/web/app/(app)/afs/page.tsx` (replace stub entirely)

**What to build:**

Replace the "Coming Soon" stub with a real engagement dashboard that:

1. Lists existing AFS engagements with search + pagination
2. Shows a "Create Engagement" form dialog
3. Auto-seeds frameworks on first visit (like workflows auto-seed pattern)
4. Uses VAEmptyState when no engagements exist

**Page structure:**
- Auth init + framework seed (same pattern as workflows page)
- Engagement list with VAListToolbar (search on `entity_name`)
- VAPagination for pagination
- VAFormDialog for "New Engagement" creation (fields: entity_name, framework_id dropdown, period_start, period_end)
- Each engagement row: entity name, framework, period, status badge, link to `/afs/{engagement_id}/setup`
- VAEmptyState when no engagements: icon="file-text", title="No AFS engagements yet", description="Create an engagement to start generating financial statements.", actionLabel="New engagement"

**Step 1:** Rewrite `afs/page.tsx` with the full dashboard.
**Step 2:** Commit:
```bash
git add apps/web/app/(app)/afs/page.tsx
git commit -m "feat(afs): replace stub with real engagement dashboard"
```

---

### Task 6: Frontend — Engagement Setup Page

**Files:**
- Create: `apps/web/app/(app)/afs/[id]/setup/page.tsx`
- Create: `apps/web/app/(app)/afs/[id]/layout.tsx` (optional — thin wrapper if needed)

**What to build:**

Multi-step setup wizard at `/afs/{id}/setup` with 4 steps:

**Step 1 — Framework & Entity** (already set at creation, display for confirmation)
- Show selected framework, entity name, period
- "Edit" button to change framework
- "Next" to proceed

**Step 2 — Upload Financial Data**
- Two upload zones side by side:
  - Left: "Excel / CSV Trial Balance" — drag-and-drop or file picker for `.xlsx`, `.csv`
  - Right: "PDF Annual Financial Statements" — drag-and-drop or file picker for `.pdf`
- Below: list of uploaded files with source type badge
- Guidance text: "Upload your Excel trial balance, PDF AFS, or both. When both are provided, we'll identify discrepancies for your review."
- "Next" to proceed (at least one file required)

**Step 3 — Source Reconciliation** (only shown when both PDF and Excel uploaded)
- If only one source: skip this step, auto-set `base_source`
- If both sources: show discrepancy table with columns: Line Item, PDF Value, Excel Value, Difference, Resolution, Note
- Each row has a VASelect for resolution (Use PDF / Use Excel / Noted) and a text input for note
- "Set Base Source" selector at top: radio buttons for "Use Excel as base" / "Use PDF as base"
- "Resolve All" and "Next" buttons

**Step 4 — YTD Projection** (only shown when `is_partial` detected)
- If full year data: skip this step
- Show detected months vs expected months
- For each missing month: text area for basis description
- "Generate Projections" button (Phase 1: saves descriptions; Phase 2: AI fills values)
- "Complete Setup" button → updates engagement status to `ingestion`

**Implementation notes:**
- Use `useParams()` to get engagement ID
- Load engagement detail on mount
- Each step uses local state; "Next" saves via API then advances
- Use a simple step counter (not the ModelStepper — this is a different flow)
- Mobile-friendly: stack upload zones vertically on small screens

**Step 1:** Create the setup page with all 4 steps.
**Step 2:** Commit:
```bash
git add apps/web/app/(app)/afs/[id]/setup/page.tsx
git commit -m "feat(afs): add engagement setup wizard with dual-source upload and reconciliation"
```

---

### Task 7: Build Verification & Commit

**Files:** None (verification only)

**Step 1:** Run Next.js build:
```bash
cd apps/web && npx next build
```
Expected: Build succeeds with no type errors.

**Step 2:** Run frontend tests:
```bash
cd apps/web && npx vitest run
```
Expected: All tests pass (no new test files in Phase 1; existing tests should not break).

**Step 3:** If any errors, fix them and re-run.

**Step 4:** Final commit with all fixes:
```bash
git add -A
git commit -m "fix(afs): resolve build errors from Phase 1 implementation"
```

---

## Execution Order

```
Task 1 (Migration)         ─── sequential (foundation)
Task 2 (Backend: frameworks + engagements)  ─── depends on Task 1
Task 3 (Backend: data ingestion)            ─── depends on Task 2
Task 4 (Frontend: API client)               ─── depends on Tasks 2+3 (needs endpoint knowledge)
Task 5 (Frontend: dashboard)                ─── depends on Task 4
Task 6 (Frontend: setup wizard)             ─── depends on Task 4
Task 7 (Build verification)                 ─── depends on all
```

Tasks 5 and 6 can run in parallel after Task 4.

---

## Verification Checklist

1. Migration SQL is valid and idempotent (`CREATE TABLE IF NOT EXISTS`, `DROP POLICY IF EXISTS`)
2. All 7 tables have RLS enabled with 4 policies each
3. Backend endpoints return proper HTTP status codes (201 for create, 200 for list/get/update, 204 for delete)
4. File uploads enforce 10MB size limit
5. Frontend API client types match backend response shapes
6. AFS dashboard lists engagements, creates new ones, seeds frameworks
7. Setup wizard handles: single source (Excel only, PDF only), dual source (both), partial year data
8. `next build` passes with no type errors
9. All existing tests still pass
