# Phase 5 Prompt — Excel Live Links + Memo Packs

## Pre-requisites
- Phase 4 gate passed
- Read: `EXCEL_LIVE_LINKS.md` (overview)
- Schemas: `excel_connection_v1`, `excel_sync_event_v1`, `memo_pack_v1`
- Examples: `excel_connection_v1.example.json`, `memo_pack_v1.example.json`
- Apply migration: `0005_excel_and_memos.sql`

## Tasks

### 1. Migration 0005
Create tables:
- `excel_connections` (tenant_id, excel_connection_id, mode, target_json, workbook_json, bindings_json, sync_json, permissions_json, created_at, created_by)
- `excel_sync_events` (tenant_id, event_id, excel_connection_id, timestamp, direction, status, diff_json)
- `memo_packs` (tenant_id, memo_id, memo_type, source_json, sections_json, outputs_json, created_at, created_by)

RLS policies on all tables.

### 2. Excel Connection API
```
File: apps/api/app/routers/excel.py

POST /api/v1/excel/connections — create connection (bindings, mode, target, permissions)
GET /api/v1/excel/connections — list
GET /api/v1/excel/connections/{id} — detail with bindings
PATCH /api/v1/excel/connections/{id} — update bindings or sync config
DELETE /api/v1/excel/connections/{id}

POST /api/v1/excel/connections/{id}/pull — gather current values for all bindings
  For each binding:
    kind=assumption → read from baseline model_config at binding.path
    kind=result/kpi → read from latest run artifacts at binding.path
    kind=statement_line → read from latest run statements
  Return: [{ binding_id, value, data_type, units }]

POST /api/v1/excel/connections/{id}/push — receive changed values from Excel
  Body: { changes: [{ binding_id, old_value, new_value }] }
  Validation:
    Check data_type matches
    Check min/max/allowed_values per binding.validation
    Check user role in permissions.can_push_roles
  Behavior per sync.push_behavior:
    "draft_override" → update draft session workspace directly
    "changeset" → create new changeset with overrides
    "blocked" → reject with 403
  Log as excel_sync_event_v1 (direction=push)

WebSocket: /api/v1/excel/ws/{connection_id}
  Notify connected clients when:
    - A run completes (new results available for pull)
    - A push creates a changeset (notify web UI)
```

### 3. Office.js Add-in
```
Directory: apps/excel-addin/

Structure:
  manifest.xml — Office Add-in manifest for sideloading
  src/
    taskpane/
      taskpane.html — main UI
      taskpane.ts — logic
    commands/
      commands.ts — ribbon button handlers

Auth:
  On taskpane open: prompt for API URL + auth token (or Supabase login)
  Store token in Office.context.roamingSettings

Connection Management:
  Dropdown to select existing connection (fetched from API)
  Binding status indicator (green = synced, amber = pending, red = error)

Pull Flow:
  1. User clicks "Pull" button (or auto-refresh per refresh_interval_seconds)
  2. POST /api/v1/excel/connections/{id}/pull
  3. For each binding in response:
     Use Excel.run() to write value to binding.excel_ref.range
     Set number format based on data_type (currency, percent, number)
  4. Log as excel_sync_event_v1 (direction=pull)

Push Flow:
  1. User clicks "Push" button
  2. For each binding with kind=assumption:
     Read current value from excel_ref.range via Excel.run()
     Compare to last known value (stored locally)
     If changed: add to changes array
  3. Validate changes client-side:
     Check data_type, min/max per binding.validation
     Show validation errors inline
  4. POST /api/v1/excel/connections/{id}/push
  5. Show result: changeset created (link to web UI) or errors

Role Gating:
  On connection load: check user role against permissions.can_push_roles
  If not allowed: hide Push button, show "Read Only" badge

Named Ranges:
  On connection setup: create named ranges matching binding.excel_ref.name
  This allows formulas in other cells to reference model data by name
```

### 4. Memo Pack Generator
```
File: apps/api/app/services/memo_service.py

Templates per memo_type:

investment_committee:
  Sections: Executive Summary, Business Overview, Financial Highlights, Key Assumptions,
  Risk Analysis, Valuation Summary, Recommendation
  
credit_memo:
  Sections: Borrower Overview, Purpose of Facility, Financial Analysis, Ratio Analysis,
  Covenant Headroom, Security/Collateral, Risk Assessment, Recommendation

valuation_note:
  Sections: Executive Summary, Methodology, Assumptions, DCF Analysis,
  Comparable Analysis, Valuation Range, Sensitivity

For each section, assemble content blocks:
  markdown: narrative text (use LLM task_label="memo_generation" for drafting)
  table_ref: reference run artifact table (IS summary, ratio table, etc.)
  chart_ref: reference chart (generated as SVG/PNG, embedded)
  assumption_refs: list key assumptions with evidence + confidence
  risk_summary: top risks from sentiment analysis

Output renderers:
  HTML: Jinja2 templates → styled HTML
  PDF: weasyprint (HTML → PDF)
  DOCX: python-docx (programmatic document construction)

Store all outputs in Supabase Storage. Record as memo_pack_v1 artifact.
```

### 5. Memo API Routes
```
File: apps/api/app/routers/memos.py

POST /api/v1/memos — { run_id, memo_type, options?: { include_mc, include_valuation } }
  Generate memo → store → return memo_id
GET /api/v1/memos — list for tenant
GET /api/v1/memos/{id} — metadata + section list
GET /api/v1/memos/{id}/download?format=html|pdf|docx — download rendered output
DELETE /api/v1/memos/{id}
```

### 6. Excel + Memo UI
```
apps/web/app/excel/page.tsx — Excel connection list
apps/web/app/excel/[id]/page.tsx — connection detail, binding list, sync history
apps/web/app/excel/new/page.tsx — create connection wizard (select baseline/run, define bindings)

apps/web/app/memos/page.tsx — memo list (filterable by type)
apps/web/app/memos/new/page.tsx — memo wizard:
  Step 1: Select run
  Step 2: Choose memo type
  Step 3: Preview sections (editable section titles)
  Step 4: Generate → progress indicator → redirect to viewer
apps/web/app/memos/[id]/page.tsx — memo viewer:
  Render HTML memo in styled iframe
  Download buttons: PDF, DOCX
  Share link option
```

### 7. Tests
Per TESTING_STRATEGY.md Phase 5 section.

## Verification
Verify Phase 5 gate criteria from BUILD_PLAN.md.
