# AFS Phase 6: Custom/AI-Inferred Frameworks + Roll-Forward Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to create custom accounting frameworks (manually or via AI inference from natural language) and roll forward prior-period sections/comparatives into new engagements.

**Architecture:** Two new backend services (`framework_ai.py`, `rollforward.py`) following the existing `disclosure_drafter.py` pattern. A small migration adds `rolled_forward_from` to `afs_sections`. Frontend changes add a prior-engagement selector to the create dialog, a roll-forward trigger on the setup page, and a custom-framework creation page with AI inference. Built-in framework schemas are seeded via a JSON data file.

**Tech Stack:** Python/FastAPI (backend services + endpoints), Next.js/React (frontend pages), PostgreSQL/JSONB (schema storage), LLMRouter (AI inference)

---

## Existing Infrastructure (already built, do NOT recreate)

- `afs_frameworks` table: supports `standard = 'custom'`, has `disclosure_schema_json` and `statement_templates_json` JSONB columns (defined but currently NULL for all frameworks)
- `afs_disclosure_items` table: ready for custom checklist items with `framework_id` FK
- `afs_engagements` table: has `prior_engagement_id` column (nullable, no FK constraint)
- `CreateFrameworkBody` Pydantic model: already accepts `disclosure_schema_json` and `statement_templates_json`
- `createEngagement` API method: already accepts `prior_engagement_id` in the request body
- `AFSEngagement` TS interface: already includes `prior_engagement_id: string | null`
- `AFSFramework` TS interface: already includes `disclosure_schema_json` and `statement_templates_json`
- Framework CRUD endpoints: `GET /frameworks`, `POST /frameworks`, `GET /frameworks/{id}`, `POST /frameworks/seed`, `GET /frameworks/{id}/checklist`
- LLM task label `template_initialization` exists in router but is unused

---

### Task 1: Migration 0057 — Add `rolled_forward_from` to `afs_sections`

**Files:**
- Create: `apps/api/app/db/migrations/0057_afs_rollforward.sql`

A small migration to track which sections were carried forward from a prior engagement.

```sql
-- 0057_afs_rollforward.sql — AFS Phase 6: roll-forward tracking

ALTER TABLE afs_sections ADD COLUMN IF NOT EXISTS rolled_forward_from text;
-- rolled_forward_from stores the prior section_id this section was copied from.
-- NULL means the section was created fresh (not rolled forward).
```

**Verification:** File exists and is valid SQL.

---

### Task 2: Built-in Framework Disclosure Schemas

**Files:**
- Create: `apps/api/app/data/framework_schemas.json`
- Modify: `apps/api/app/routers/afs.py` — update `seed_builtin_frameworks` to load and apply schemas

The 4 built-in frameworks currently have NULL `disclosure_schema_json`. This task populates them with structured disclosure requirement schemas so the disclosure checklist and AI drafter know what sections are expected.

**Schema structure** (per framework):
```json
{
  "ifrs": {
    "disclosure_schema": {
      "sections": [
        {
          "type": "statement",
          "title": "Statement of Financial Position",
          "reference": "IAS 1.54",
          "required": true,
          "sub_items": ["Non-current assets", "Current assets", "Equity", "Non-current liabilities", "Current liabilities"]
        },
        {
          "type": "statement",
          "title": "Statement of Profit or Loss and Other Comprehensive Income",
          "reference": "IAS 1.81A",
          "required": true,
          "sub_items": ["Revenue", "Cost of sales", "Gross profit", "Other income", "Operating expenses", "Finance costs", "Tax expense", "Profit for the year", "OCI"]
        },
        {
          "type": "statement",
          "title": "Statement of Changes in Equity",
          "reference": "IAS 1.106",
          "required": true,
          "sub_items": []
        },
        {
          "type": "statement",
          "title": "Statement of Cash Flows",
          "reference": "IAS 7",
          "required": true,
          "sub_items": ["Operating activities", "Investing activities", "Financing activities"]
        },
        {
          "type": "accounting_policy",
          "title": "Material Accounting Policy Information",
          "reference": "IAS 1.117",
          "required": true,
          "sub_items": []
        },
        {
          "type": "note",
          "title": "Property, Plant and Equipment",
          "reference": "IAS 16.73",
          "required": true,
          "sub_items": []
        }
      ]
    },
    "statement_templates": {
      "sofp": { "title": "Statement of Financial Position", "line_items": ["non_current_assets", "current_assets", "total_assets", "equity", "non_current_liabilities", "current_liabilities", "total_equity_and_liabilities"] },
      "sopl": { "title": "Statement of Profit or Loss", "line_items": ["revenue", "cost_of_sales", "gross_profit", "other_income", "operating_expenses", "finance_costs", "tax_expense", "profit_for_year"] },
      "soce": { "title": "Statement of Changes in Equity", "line_items": ["opening_balance", "profit_for_year", "other_comprehensive_income", "dividends", "closing_balance"] },
      "socf": { "title": "Statement of Cash Flows", "line_items": ["operating_activities", "investing_activities", "financing_activities", "net_change", "opening_cash", "closing_cash"] }
    }
  }
}
```

Provide schemas for all 4 standards: `ifrs`, `ifrs_sme`, `us_gaap`, `sa_companies_act`. Each should have 10-20 disclosure sections and 4 statement templates. Use realistic IFRS/GAAP references.

**Modify `seed_builtin_frameworks`:** After inserting a framework row, load its schema from the JSON file and UPDATE the `disclosure_schema_json` and `statement_templates_json` columns. Also seed corresponding `afs_disclosure_items` rows for each section in the schema.

**Verification:** `python -c "import json; d=json.load(open('apps/api/app/data/framework_schemas.json')); print(list(d.keys()))"` → `['ifrs', 'ifrs_sme', 'us_gaap', 'sa_companies_act']`

---

### Task 3: AI Framework Inference Service

**Files:**
- Create: `apps/api/app/services/afs/framework_ai.py`
- Modify: `apps/api/app/services/llm/router.py` — add task labels

New service following the `disclosure_drafter.py` pattern. Takes a natural-language description of jurisdiction/requirements and generates a custom framework schema.

**Function signature:**
```python
async def infer_framework(
    llm_router: LLMRouter,
    tenant_id: str,
    *,
    description: str,           # NL description from user
    jurisdiction: str | None,   # optional jurisdiction hint
    entity_type: str | None,    # e.g. "private company", "listed entity"
) -> dict:
    """Returns { name, disclosure_schema_json, statement_templates_json, suggested_items }"""
```

**FRAMEWORK_SCHEMA** (structured output):
```python
{
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "disclosure_schema": {
            "type": "object",
            "properties": {
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["note", "statement", "directors_report", "accounting_policy"]},
                            "title": {"type": "string"},
                            "reference": {"type": "string"},
                            "required": {"type": "boolean"},
                            "sub_items": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["type", "title", "reference", "required", "sub_items"],
                        "additionalProperties": false
                    }
                }
            },
            "required": ["sections"],
            "additionalProperties": false
        },
        "statement_templates": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "line_items": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["title", "line_items"],
                "additionalProperties": false
            }
        },
        "suggested_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "section": {"type": "string"},
                    "reference": {"type": "string"},
                    "description": {"type": "string"},
                    "required": {"type": "boolean"}
                },
                "required": ["section", "reference", "description", "required"],
                "additionalProperties": false
            }
        }
    },
    "required": ["name", "disclosure_schema", "statement_templates", "suggested_items"],
    "additionalProperties": false
}
```

**System prompt:**
```
You are an expert accounting standards advisor. Given a natural-language description of an entity's
reporting requirements, generate a complete disclosure framework including:
1. All required financial statement sections (SOFP, SOPL, SOCE, SOCF)
2. All required disclosure notes with standard references
3. Statement templates with line items
4. A suggested disclosure checklist

Base your recommendations on IFRS, US GAAP, and local jurisdictional requirements as described.
Always include standard references (e.g. "IAS 1.54", "ASC 220-10-45").
```

**Task labels to add to LLM router:** `afs_framework_inference` (Anthropic primary, OpenAI fallback)

**Verification:** `python -c "from apps.api.app.services.afs.framework_ai import infer_framework; print('OK')"` → `OK`

---

### Task 4: AI Framework Inference + Custom Framework Endpoints

**Files:**
- Modify: `apps/api/app/routers/afs.py` — add 2 new endpoints

**Endpoint 1: `POST /afs/frameworks/infer`**
```python
class InferFrameworkBody(BaseModel):
    description: str = Field(..., min_length=10, max_length=2000)
    jurisdiction: str | None = None
    entity_type: str | None = None

@router.post("/frameworks/infer")
async def infer_framework_endpoint(
    body: InferFrameworkBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm_router: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
```

- Calls `infer_framework()` service
- Creates the framework row with `standard='custom'` and the generated schemas
- Inserts `afs_disclosure_items` from `suggested_items`
- Returns the created framework + items count

**Endpoint 2: `POST /afs/frameworks/{framework_id}/items`**
```python
class CreateDisclosureItemBody(BaseModel):
    section: str = Field(..., min_length=1)
    reference: str | None = None
    description: str = Field(..., min_length=1)
    required: bool = True
    applicable_entity_types: list[str] | None = None

@router.post("/frameworks/{framework_id}/items", status_code=201)
async def add_disclosure_item(
    framework_id: str,
    body: CreateDisclosureItemBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
```

- Validates framework exists and belongs to tenant
- Inserts into `afs_disclosure_items`
- Returns created item

**Verification:** `python -c "from apps.api.app.routers.afs import router; print('Router OK')"` → `Router OK`

---

### Task 5: Roll-Forward Service

**Files:**
- Create: `apps/api/app/services/afs/rollforward.py`

Service that copies sections and comparative data from a prior engagement into a new one.

**Function signatures:**
```python
async def rollforward_sections(
    conn,
    tenant_id: str,
    source_engagement_id: str,
    target_engagement_id: str,
    *,
    created_by: str | None = None,
) -> dict:
    """
    Copy all sections from source engagement into target engagement.
    - Sets status='draft' on all copied sections
    - Sets rolled_forward_from to the source section_id
    - Preserves section_type, title, content_json, section_number
    - Generates new section_ids
    Returns { sections_copied: int, sections: [...] }
    """

async def rollforward_comparatives(
    conn,
    tenant_id: str,
    source_engagement_id: str,
    target_engagement_id: str,
) -> dict:
    """
    Copy trial balance data from source engagement as comparative reference.
    Inserts a new TB row with source='va_baseline' and a marker in mapped_accounts_json
    indicating these are prior-period comparatives.
    Returns { comparatives_copied: bool, trial_balance_id: str | None }
    """
```

**Implementation notes:**
- `rollforward_sections`: SELECT from `afs_sections WHERE engagement_id = source`, INSERT into `afs_sections` with new IDs and `rolled_forward_from` set. Use `ON CONFLICT DO NOTHING` to be idempotent.
- `rollforward_comparatives`: SELECT from `afs_trial_balances WHERE engagement_id = source`, INSERT one summary TB row for the target with `source='va_baseline'` and `mapped_accounts_json` containing `{"_comparative_source": source_engagement_id}`.

**Verification:** `python -c "from apps.api.app.services.afs.rollforward import rollforward_sections, rollforward_comparatives; print('OK')"` → `OK`

---

### Task 6: Roll-Forward Endpoint

**Files:**
- Modify: `apps/api/app/routers/afs.py` — add 1 new endpoint

```python
@router.post("/engagements/{engagement_id}/rollforward")
async def rollforward_engagement(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
```

- Validates engagement exists and has `prior_engagement_id` set
- Validates prior engagement exists
- Calls `rollforward_sections()` and `rollforward_comparatives()`
- Returns `{ sections_copied: int, comparatives_copied: bool }`

**Verification:** `python -c "from apps.api.app.routers.afs import router; print('Router OK')"` → `Router OK`

---

### Task 7: Frontend API Methods

**Files:**
- Modify: `apps/web/lib/api.ts` — add 3 new methods to the `afs` namespace

```typescript
inferFramework: (tenantId: string, body: { description: string; jurisdiction?: string; entity_type?: string }) =>
  request<AFSFramework & { items_count: number }>("/api/v1/afs/frameworks/infer", { tenantId, method: "POST", body }),

addDisclosureItem: (tenantId: string, frameworkId: string, body: { section: string; reference?: string; description: string; required?: boolean }) =>
  request<AFSDisclosureItem>(`/api/v1/afs/frameworks/${encodeURIComponent(frameworkId)}/items`, { tenantId, method: "POST", body }),

rollforward: (tenantId: string, engagementId: string) =>
  request<{ sections_copied: number; comparatives_copied: boolean }>(`/api/v1/afs/engagements/${encodeURIComponent(engagementId)}/rollforward`, { tenantId, method: "POST" }),
```

**Verification:** `cd apps/web && npx tsc --noEmit --pretty 2>&1 | head -5` → no errors

---

### Task 8: Prior Engagement Selector in Create Dialog

**Files:**
- Modify: `apps/web/app/(app)/afs/page.tsx`

Update the "New AFS Engagement" create dialog to include:

1. **Prior Engagement dropdown** — after the Period End date field, add:
   ```tsx
   <div>
     <label className="mb-1 block text-sm font-medium text-va-text">
       Prior Engagement (optional)
     </label>
     <VASelect
       value={priorEngagementId}
       onChange={(e) => setPriorEngagementId(e.target.value)}
     >
       <option value="">None (fresh engagement)</option>
       {engagements
         .filter((e) => e.status === "approved" || e.status === "published")
         .map((e) => (
           <option key={e.engagement_id} value={e.engagement_id}>
             {e.entity_name} ({e.period_start} – {e.period_end})
           </option>
         ))}
     </VASelect>
     <p className="mt-1 text-xs text-va-muted">
       Link to a prior period to enable roll-forward of sections and comparatives.
     </p>
   </div>
   ```

2. **State:** Add `const [priorEngagementId, setPriorEngagementId] = useState("")`

3. **Pass to API:** Update `handleCreate` to include `prior_engagement_id: priorEngagementId || undefined` in the body.

4. **Engagement cards:** Show a small "Linked" badge on engagement cards that have `prior_engagement_id` set.

**Verification:** `cd apps/web && npx next build` → clean build

---

### Task 9: Roll-Forward UI on Setup Page

**Files:**
- Modify: `apps/web/app/(app)/afs/[id]/setup/page.tsx`

Add roll-forward functionality to Step 1 (Framework & Entity) of the setup page:

1. **Detect prior engagement:** If `engagement.prior_engagement_id` is set, show a roll-forward panel in Step 1.

2. **Roll-forward panel:**
   ```tsx
   {engagement.prior_engagement_id && (
     <div className="mt-4 rounded-va-md border border-va-blue/30 bg-va-blue/5 p-4">
       <h3 className="text-sm font-semibold text-va-text">Roll Forward Available</h3>
       <p className="mt-1 text-xs text-va-text2">
         This engagement is linked to a prior period. You can carry forward sections and
         comparative data to use as a starting point.
       </p>
       <div className="mt-3 flex items-center gap-3">
         <VAButton
           variant="primary"
           disabled={rollingForward}
           onClick={async () => {
             setRollingForward(true);
             try {
               const result = await api.afs.rollforward(tenantId!, engagementId);
               toast.success(`Rolled forward ${result.sections_copied} sections`);
               setRolledForward(true);
             } catch (e) {
               toast.error(e instanceof Error ? e.message : "Roll-forward failed");
             } finally {
               setRollingForward(false);
             }
           }}
         >
           {rollingForward ? "Rolling forward..." : rolledForward ? "Rolled Forward ✓" : "Roll Forward Sections"}
         </VAButton>
         {rolledForward && (
           <span className="text-xs text-va-success">Sections and comparatives copied</span>
         )}
       </div>
     </div>
   )}
   ```

3. **State:** Add `rollingForward` and `rolledForward` boolean states.

**Verification:** `cd apps/web && npx next build` → clean build

---

### Task 10: Sections Page — Rolled-Forward Badges

**Files:**
- Modify: `apps/web/app/(app)/afs/[id]/sections/page.tsx`

Update the sections list to show a visual indicator for rolled-forward sections:

1. **Add to `AFSSection` type check:** If `(section as any).rolled_forward_from` is truthy, show a badge.

2. **Badge placement:** Next to the section title in the list, add:
   ```tsx
   {(section as any).rolled_forward_from && (
     <VABadge variant="violet">Carried Forward</VABadge>
   )}
   ```

3. **Update `AFSSection` TS interface** in `api.ts` to include `rolled_forward_from: string | null`.

**Verification:** `cd apps/web && npx next build` → clean build

---

### Task 11: Custom Framework Creation Page

**Files:**
- Create: `apps/web/app/(app)/afs/frameworks/page.tsx`
- Modify: `apps/web/components/VASidebar.tsx` — add nav entry under AFS group (if applicable) or rely on in-page navigation

A dedicated page for creating custom frameworks with two paths:

**Path A — AI Inference:**
- Textarea for NL description (e.g. "South African private company using IFRS for SMEs with mining-specific disclosures")
- Optional jurisdiction and entity type inputs
- "Generate Framework" button → calls `api.afs.inferFramework()`
- Shows generated framework preview: name, section list, disclosure items
- "Save Framework" confirmation

**Path B — Manual Creation:**
- Form fields: name, jurisdiction, version
- Add sections manually (type, title, reference, required)
- Add disclosure items manually

**Page structure (~150 lines):**
```tsx
export default function CustomFrameworkPage() {
  const [mode, setMode] = useState<"ai" | "manual">("ai");
  // ... AI form state, manual form state, preview state

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <h1>Create Custom Framework</h1>

      {/* Mode toggle */}
      <div className="flex gap-2">
        <VAButton variant={mode === "ai" ? "primary" : "secondary"} onClick={() => setMode("ai")}>
          AI-Assisted
        </VAButton>
        <VAButton variant={mode === "manual" ? "primary" : "secondary"} onClick={() => setMode("manual")}>
          Manual
        </VAButton>
      </div>

      {mode === "ai" && <AIInferenceForm />}
      {mode === "manual" && <ManualFrameworkForm />}

      {/* Preview of generated/entered framework */}
      {preview && <FrameworkPreview />}
    </main>
  );
}
```

**Navigation:** Add a "Custom Framework" button on the main AFS page (`/afs`) next to "New Engagement", linking to `/afs/frameworks`.

**Verification:** `cd apps/web && npx next build` → clean build

---

## Execution Order

```
Task 1 (Migration 0057)                    ─┐
Task 2 (Built-in framework schemas)         ─┤── parallel (all independent)
Task 3 (AI framework inference service)     ─┤
Task 5 (Roll-forward service)               ─┘
                                             │
Task 4 (AI framework + items endpoints)     ─── depends on Task 3
Task 6 (Roll-forward endpoint)              ─── depends on Task 5
                                             │
Task 7 (Frontend API methods)               ─── depends on Tasks 4 + 6
                                             │
Task 8 (Prior engagement selector)          ─┐
Task 9 (Roll-forward UI on setup)           ─┤── depend on Task 7, parallel with each other
Task 10 (Sections rolled-forward badges)    ─┤
Task 11 (Custom framework creation page)    ─┘
```

---

## Verification Checklist

1. `python -c "from apps.api.app.services.afs.framework_ai import infer_framework; print('OK')"` → OK
2. `python -c "from apps.api.app.services.afs.rollforward import rollforward_sections; print('OK')"` → OK
3. `python -c "from apps.api.app.routers.afs import router; print('Router OK')"` → Router OK
4. `cd apps/web && npx next build` → clean build, no type errors
5. `cd apps/web && npx vitest run` → all tests pass
6. Visit `/afs` → "New Engagement" dialog shows prior engagement selector
7. Create engagement with prior link → setup page shows roll-forward panel
8. Click "Roll Forward" → sections copied with "Carried Forward" badges
9. Visit `/afs/frameworks` → can create framework via AI inference or manually
10. AI-inferred framework → generates sections, disclosure items, statement templates
