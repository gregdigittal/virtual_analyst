# AFS Phase 4 — Multi-Entity Consolidation & Output Generation

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add multi-entity consolidation (bridging org-structures to AFS engagements) and output generation (PDF, DOCX, iXBRL) so users can produce publishable annual financial statements.

**Architecture:** Consolidation reuses the existing `shared/fm_shared/analysis/consolidation.py` engine and org-structures entity hierarchy. A new `afs_consolidation_rules` table links an AFS engagement to an org-structure, storing consolidated trial balance data and elimination entries. Output generation assembles locked sections into formatted documents via WeasyPrint (PDF), python-docx (DOCX), and custom inline XBRL (iXBRL). Generated files are stored in the artifact store and tracked via `afs_outputs`.

**Tech Stack:** Python/FastAPI, asyncpg, WeasyPrint, python-docx, Next.js 14, TypeScript, Tailwind CSS

---

## Existing Infrastructure

### Org-Structures Module (fully built)
- **Backend:** `apps/api/app/routers/org_structures.py` — full CRUD for org groups, entities, ownership links, intercompany links, hierarchy, validation, consolidated runs
- **Frontend:** `apps/web/app/(app)/org-structures/` — list page + detail page with hierarchy tree, entities table, intercompany table, consolidation settings, run trigger
- **Consolidation engine:** `shared/fm_shared/analysis/consolidation.py` — FX translation (IAS 21), full/proportional/equity methods, intercompany elimination, NCI, integrity checks
- **Entity model:** `org_entities` table has entity_id, name, entity_type, currency, country_iso, tax_jurisdiction, tax_rate, withholding_tax_rate, is_root, baseline_id

### AFS Module (Phases 1–3 complete)
- **Migrations:** 0052 (core), 0053 (sections), 0054 (reviews + tax)
- **Router:** `apps/api/app/routers/afs.py` — 37 endpoints
- **entity_id:** Already nullable in `afs_trial_balances` and `afs_tax_computations` — ready for multi-entity tagging
- **Sections:** JSON-structured content (paragraphs, tables, headings, references, warnings)
- **Engagement status:** setup → ingestion → drafting → review → approved → published

### Key Patterns
- Composite PKs: `(tenant_id, entity_id)`
- RLS: `current_setting('app.tenant_id', true)` with 4 policies per table
- ID prefixes: `acr_` (consolidation rules), `afo_` (outputs)
- AI services: `apps/api/app/services/afs/` — disclosure_drafter.py, tax_note_drafter.py
- Artifact store: `ArtifactStore` via `Depends(get_artifact_store)` — binary blob storage
- Frontend API: `apps/web/lib/api.ts` — typed methods in `api.afs` namespace

---

## Task 1: Migration 0055 — Consolidation Rules & Outputs

**Files:**
- Create: `apps/api/app/db/migrations/0055_afs_consolidation_outputs.sql`

Two new tables:

```sql
-- 0055_afs_consolidation_outputs.sql — AFS Phase 4: consolidation rules & output tracking

-- ============================================================
-- AFS_CONSOLIDATION_RULES (links engagement to org-structure)
-- ============================================================
create table if not exists afs_consolidation_rules (
  tenant_id text not null references tenants(id) on delete cascade,
  consolidation_id text not null,
  engagement_id text not null,
  org_id text not null,
  reporting_currency text not null default 'ZAR',
  fx_avg_rates jsonb not null default '{}'::jsonb,
  fx_closing_rates jsonb not null default '{}'::jsonb,
  elimination_entries_json jsonb not null default '[]'::jsonb,
  consolidated_tb_json jsonb,
  entity_tb_map jsonb not null default '{}'::jsonb,
  status text not null check (status in ('pending','consolidated','error')) default 'pending',
  error_message text,
  consolidated_at timestamptz,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, consolidation_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_consol_engagement on afs_consolidation_rules(tenant_id, engagement_id);

-- ============================================================
-- AFS_OUTPUTS (generated document files)
-- ============================================================
create table if not exists afs_outputs (
  tenant_id text not null references tenants(id) on delete cascade,
  output_id text not null,
  engagement_id text not null,
  format text not null check (format in ('pdf','docx','ixbrl','excel')),
  filename text not null,
  file_size_bytes bigint,
  artifact_key text,
  status text not null check (status in ('generating','ready','error')) default 'generating',
  error_message text,
  generated_by text references users(id) on delete set null,
  generated_at timestamptz not null default now(),
  primary key (tenant_id, output_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_outputs_engagement on afs_outputs(tenant_id, engagement_id);

-- ============================================================
-- RLS
-- ============================================================

-- afs_consolidation_rules
alter table afs_consolidation_rules enable row level security;
drop policy if exists "afs_consolidation_rules_select" on afs_consolidation_rules;
drop policy if exists "afs_consolidation_rules_insert" on afs_consolidation_rules;
drop policy if exists "afs_consolidation_rules_update" on afs_consolidation_rules;
drop policy if exists "afs_consolidation_rules_delete" on afs_consolidation_rules;
create policy "afs_consolidation_rules_select" on afs_consolidation_rules for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_consolidation_rules_insert" on afs_consolidation_rules for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_consolidation_rules_update" on afs_consolidation_rules for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_consolidation_rules_delete" on afs_consolidation_rules for delete using (tenant_id = current_setting('app.tenant_id', true));

-- afs_outputs
alter table afs_outputs enable row level security;
drop policy if exists "afs_outputs_select" on afs_outputs;
drop policy if exists "afs_outputs_insert" on afs_outputs;
drop policy if exists "afs_outputs_update" on afs_outputs;
drop policy if exists "afs_outputs_delete" on afs_outputs;
create policy "afs_outputs_select" on afs_outputs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_outputs_insert" on afs_outputs for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_outputs_update" on afs_outputs for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_outputs_delete" on afs_outputs for delete using (tenant_id = current_setting('app.tenant_id', true));
```

**Verification:** `python -c "import apps.api.app.routers.afs"` — should still import fine (no code changes, just SQL).

---

## Task 2: Consolidation Backend Endpoints

**Files:**
- Modify: `apps/api/app/routers/afs.py`

Add 4 consolidation endpoints after the existing tax endpoints:

### New ID generators
```python
def _consolidation_id() -> str:
    return f"acr_{uuid.uuid4().hex[:14]}"

def _output_id() -> str:
    return f"afo_{uuid.uuid4().hex[:14]}"
```

### New Pydantic models
```python
class LinkOrgBody(BaseModel):
    org_id: str = Field(..., min_length=1)
    reporting_currency: str = Field(default="ZAR", pattern=r"^[A-Z]{3}$")
    fx_avg_rates: dict[str, float] = Field(default_factory=dict)
    fx_closing_rates: dict[str, float] | None = None

class ConsolidateBody(BaseModel):
    fx_avg_rates: dict[str, float] | None = None
    fx_closing_rates: dict[str, float] | None = None
```

### Endpoints

1. **`POST /engagements/{engagement_id}/consolidation/link`** — Link engagement to an org-structure
   - Validate engagement exists
   - Validate org_id by querying `org_structures` table (same tenant)
   - Insert into `afs_consolidation_rules` with status='pending'
   - Return the row

2. **`GET /engagements/{engagement_id}/consolidation`** — Get consolidation config
   - Return the consolidation_rules row for this engagement (or 404 if not linked)
   - Include entity list from org_entities for the linked org_id

3. **`POST /engagements/{engagement_id}/consolidation/run`** — Run consolidation
   - Load consolidation_rules for engagement
   - Load all org_entities for the linked org_id
   - For each entity: load their trial balance from `afs_trial_balances` WHERE entity_id matches
   - Build consolidated TB by summing accounts across entities, applying elimination entries
   - For intercompany: load `org_intercompany_links` for the org, compute elimination amounts
   - Store `consolidated_tb_json` and `elimination_entries_json`
   - Update status to 'consolidated'
   - Return updated row

4. **`GET /engagements/{engagement_id}/consolidation/entities`** — List entities with their TB status
   - For each entity in the linked org: check if a trial balance exists with that entity_id
   - Return list with entity info + has_trial_balance boolean

**Key logic for consolidation/run:**
- Read each entity's `data_json` from `afs_trial_balances` (array of `{account_name, debit, credit, net}`)
- Group by account_name across entities
- Apply FX translation if currencies differ (use fx_avg_rates from consolidation_rules)
- Compute intercompany eliminations from `org_intercompany_links`
- Result: consolidated array of `{account_name, net, entity_breakdown: {entity_id: amount}}`

---

## Task 3: Output Generation Backend

**Files:**
- Modify: `apps/api/app/routers/afs.py`
- Create: `apps/api/app/services/afs/output_generator.py`

### Output Generator Service

Create `apps/api/app/services/afs/output_generator.py` with:

```python
"""AFS Output Generator — assembles sections into PDF, DOCX, and iXBRL."""

async def generate_pdf(
    entity_name: str,
    period_start: str,
    period_end: str,
    framework_name: str,
    sections: list[dict],
) -> bytes:
    """Generate PDF from sections using WeasyPrint."""
    # Build HTML document with:
    # - Cover page (entity name, period, framework)
    # - Table of contents (from section titles)
    # - Each section rendered as HTML (headings, paragraphs, tables)
    # - Page numbers, headers/footers
    # Convert HTML to PDF via WeasyPrint
    ...

async def generate_docx(
    entity_name: str,
    period_start: str,
    period_end: str,
    framework_name: str,
    sections: list[dict],
) -> bytes:
    """Generate DOCX from sections using python-docx."""
    # Build Word document with:
    # - Title page
    # - TOC placeholder
    # - Each section with heading styles, body text, markdown tables
    ...

async def generate_ixbrl(
    entity_name: str,
    period_start: str,
    period_end: str,
    framework_name: str,
    standard: str,
    sections: list[dict],
) -> bytes:
    """Generate inline XBRL HTML from sections."""
    # Build HTML with XBRL namespace declarations
    # Wrap financial figures in <ix:nonFraction> tags
    # Add <ix:header> with contexts (entity, period)
    # Use IFRS taxonomy for IFRS frameworks, US GAAP taxonomy for US GAAP
    ...

def _build_html_from_sections(
    entity_name: str,
    period_start: str,
    period_end: str,
    framework_name: str,
    sections: list[dict],
    include_xbrl_tags: bool = False,
    standard: str = "ifrs",
) -> str:
    """Build HTML document from section content_json."""
    # Shared HTML builder used by both PDF and iXBRL generators
    # Renders paragraphs by type: text → <p>, heading → <h3>, table → <table>
    # For tables: parse markdown table format into HTML <table>
    ...
```

### Backend Endpoints (3 endpoints)

1. **`POST /engagements/{engagement_id}/outputs/generate`** — Generate output file
   - Body: `{ format: "pdf" | "docx" | "ixbrl" }`
   - Load engagement + framework
   - Load all locked sections (status='locked') ordered by section_number
   - If no locked sections, return 400
   - Call appropriate generator
   - Store bytes in artifact store
   - Insert into `afs_outputs` with status='ready'
   - Return output row

2. **`GET /engagements/{engagement_id}/outputs`** — List generated outputs
   - Return all outputs ordered by generated_at DESC

3. **`GET /engagements/{engagement_id}/outputs/{output_id}/download`** — Download output file
   - Load output row
   - Load bytes from artifact store
   - Return as StreamingResponse with correct content-type and Content-Disposition

### New Pydantic model
```python
class GenerateOutputBody(BaseModel):
    format: str = Field(...)  # pdf, docx, ixbrl
```

**Verification:** `python -c "from apps.api.app.services.afs.output_generator import generate_pdf, generate_docx, generate_ixbrl"` — imports OK.

---

## Task 4: Frontend API Additions

**Files:**
- Modify: `apps/web/lib/api.ts`

### New TypeScript interfaces

```typescript
export interface AFSConsolidation {
  consolidation_id: string;
  engagement_id: string;
  org_id: string;
  reporting_currency: string;
  fx_avg_rates: Record<string, number>;
  fx_closing_rates: Record<string, number>;
  elimination_entries_json: unknown[];
  consolidated_tb_json: unknown[] | null;
  entity_tb_map: Record<string, string>;
  status: string;
  error_message: string | null;
  consolidated_at: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AFSConsolidationEntity {
  entity_id: string;
  name: string;
  entity_type: string;
  currency: string;
  has_trial_balance: boolean;
}

export interface AFSOutput {
  output_id: string;
  engagement_id: string;
  format: string;
  filename: string;
  file_size_bytes: number | null;
  status: string;
  error_message: string | null;
  generated_by: string | null;
  generated_at: string;
}
```

### New API methods in `api.afs`

```typescript
// Consolidation
linkOrg(tenantId, engagementId, body: { org_id: string; reporting_currency?: string; fx_avg_rates?: Record<string, number>; fx_closing_rates?: Record<string, number> })
getConsolidation(tenantId, engagementId)
runConsolidation(tenantId, engagementId, body?: { fx_avg_rates?: Record<string, number>; fx_closing_rates?: Record<string, number> })
listConsolidationEntities(tenantId, engagementId)

// Outputs
generateOutput(tenantId, engagementId, body: { format: string })
listOutputs(tenantId, engagementId)
downloadOutput(tenantId, engagementId, outputId) → returns blob URL
```

---

## Task 5: Consolidation Page

**Files:**
- Create: `apps/web/app/(app)/afs/[id]/consolidation/page.tsx`

### Layout
Split into sections:

1. **Header:** Back arrow + "{entity_name} — Consolidation" + nav buttons (Sections, Tax, Review, Output)

2. **Link Org-Structure panel** (if no consolidation linked yet):
   - Dropdown to select from user's org-structures (call `api.orgStructures.list()`)
   - Reporting currency input
   - "Link" button → calls `linkOrg`

3. **Entity TB Status** (once linked):
   - Table showing each entity from the org: name, currency, type, has_trial_balance (green check / red X)
   - For entities without TB: "Upload via Setup page" hint
   - Entity TB upload: when uploading TB on setup page, include entity_id tag

4. **FX Rates** (if multi-currency):
   - Input fields for avg and closing rates per currency pair
   - Pre-filled from consolidation_rules

5. **Run Consolidation** button:
   - Disabled unless all entities have TBs
   - Shows status badge (pending/consolidated/error)
   - On success: shows consolidated TB summary (top 20 accounts by absolute value)

6. **Elimination Entries** (after consolidation):
   - Table showing intercompany eliminations applied
   - Account name, from_entity, to_entity, amount

---

## Task 6: Output Page

**Files:**
- Create: `apps/web/app/(app)/afs/[id]/output/page.tsx`

### Layout

1. **Header:** Back arrow + "{entity_name} — Output" + nav buttons

2. **Generate section:**
   - 3 cards (PDF, DOCX, iXBRL) each with:
     - Icon and format name
     - Description (e.g. "Print-ready PDF with cover page and TOC")
     - "Generate" button
   - Disabled if no locked sections exist (show warning)
   - On click: calls `generateOutput`, shows spinner, then adds to list below

3. **Generated outputs list:**
   - Table: format badge, filename, file size, generated date, status badge
   - Download button per row → calls `downloadOutput`, triggers browser download
   - Error state shows error_message

---

## Task 7: Navigation Wiring

**Files:**
- Modify: `apps/web/app/(app)/afs/[id]/sections/page.tsx` — add Consolidation and Output nav buttons
- Modify: `apps/web/app/(app)/afs/[id]/review/page.tsx` — add Consolidation and Output nav buttons
- Modify: `apps/web/app/(app)/afs/[id]/tax/page.tsx` — add Consolidation and Output nav buttons
- Modify: `apps/web/app/(app)/afs/page.tsx` — add "published" status to link to output page

### Nav button additions (in each page's header button group):
```tsx
<VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/consolidation`)}>
  Consolidation
</VAButton>
<VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/output`)}>
  Output
</VAButton>
```

### Dashboard link update:
For engagements with status "published" → link to `/afs/${eng.engagement_id}/output`.

---

## Task 8: Build Verification

1. `python -c "from apps.api.app.routers.afs import router; print('OK')"` — router imports
2. `python -c "from apps.api.app.services.afs.output_generator import generate_pdf; print('OK')"` — output service imports
3. `cd apps/web && npx next build` — no type errors
4. `cd apps/web && npx vitest run` — all tests pass (140+)

---

## Execution Order

```
Task 1 (Migration 0055)                    ─── first (schema required by all)
Task 2 (Consolidation endpoints)           ─┐
Task 3 (Output generation backend)         ─┤── parallel after Task 1
Task 4 (Frontend API additions)            ─┘
Task 5 (Consolidation page)               ─┐── parallel after Tasks 2+4
Task 6 (Output page)                      ─┘── parallel after Tasks 3+4
Task 7 (Navigation wiring)               ─── after Tasks 5+6
Task 8 (Build verification)              ─── last
```

---

## Dependencies

**Python packages needed:**
- `weasyprint` — HTML → PDF rendering
- `python-docx` — DOCX generation

Check if already in requirements: `apps/api/requirements.txt`. If not, add them.

**No new npm packages needed** — frontend is standard React/Next.js.
