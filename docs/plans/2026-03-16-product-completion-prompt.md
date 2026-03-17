# Multi-Agent Product Completion Sprint — Virtual Analyst
> Prompt version: 1.0 · Generated: 2026-03-16
> Usage: `/goal --supervised [paste this document]`
> Save output to: `docs/plans/2026-03-16-product-completion-plan.md`

---

## MISSION

You are the chief architect for the Virtual Analyst project. Your task is to deploy a
parallel multi-agent development process to close all remaining product gaps before beta
user testing. Billing/Stripe verification is explicitly excluded — it will be done post-beta.

All technical work (tests, CI, infrastructure) is complete as of Sprint 8 (2026-03-16).
What remains is product work: navigation, user-facing documentation, data connectivity,
developer tooling, and the Excel add-in.

---

## PROJECT CONTEXT (self-contained — no codebase reading required for planning)

**Stack:** Python 3.12 FastAPI backend · Next.js 14 App Router TypeScript frontend · Supabase PostgreSQL
**Hosting:** Vercel (web at `www.virtual-analyst.ai`) · Render (API at `virtual-analyst-api.onrender.com/api/v1`)
**Auth:** Supabase Auth + ES256 JWKS JWT · RBAC (owner/admin/analyst/investor)
**LLM:** Anthropic Claude via `LLMRouter` (single-turn) and `AgentService` (multi-step)
**Testing:** 640+ pytest tests · 274 Vitest unit tests · 71 Playwright E2E specs · 0 failing

### What is fully built and tested (do NOT rebuild)
- Core financial engine: DCF, Monte Carlo, AFS, consolidation, sensitivity (`shared/fm_shared/`)
- AFS module P1–P6: 52 endpoints, 12 DB tables, 10 frontend pages (`/afs/*`)
- PIM module Sprints 0–6: sentiment, universe, Markov (81-state), CIS scoring, portfolio, backtesting,
  PE benchmarking — 8 routers, 13 DB tables, 7 frontend route groups (`/pim/*`)
- All 38 backend routers with full test coverage
- All Tier 5 infrastructure: integration tests, CI, monitoring, load tests, OpenAPI validation

### What is MISSING (the work for this sprint)

| # | Item | Impact | Effort |
|---|------|--------|--------|
| 1 | PIM module not in sidebar navigation | Zero UX access to entire PIM suite | S |
| 2 | AFS sidebar entry is wrong ("AFS Import" under SETUP, no sub-pages) | Users can't navigate AFS workflow | S |
| 3 | CONTEXT.md is 7 days stale (describes PIM as "pre-development") | Agents in new sessions get wrong context | S |
| 4 | Polygon.io + FRED keys not in `.env.example` or `CLAUDE.md` | Ops can't configure real data feeds | S |
| 5 | PIM routes have no InstructionsDrawer help content | Users get no contextual help in PIM | M |
| 6 | DTF (Developer Testing Framework) not built | No Markov model integrity monitoring | L |
| 7 | Excel add-in is a skeleton (Push sends empty changes array; Pull doesn't write cells) | Excel live-links feature non-functional | M |

---

## KEY FILE LOCATIONS AND PATTERNS

### High-conflict files — assign to ONE stream only
- `apps/web/components/VASidebar.tsx` — nav groups, assigned to **Stream A**
- `apps/web/lib/instructions-config.ts` — route→help mapping, assigned to **Stream A** (after sidebar)
- `CONTEXT.md` — project context doc, assigned to **Stream B**
- `.env.example` — env var reference, assigned to **Stream B**
- `CLAUDE.md` — project config for Claude, assigned to **Stream B**

### VASidebar.tsx — current structure (lines 27–74)
The sidebar uses a `NAV_GROUPS: NavGroup[]` array with 4 groups (SETUP, CONFIGURE, ANALYZE, REPORT).
Each group has `{ key, label, items: [{ href, label, icon }] }`.
There is also a `UTILITY_ITEMS` array for non-grouped links.
The available icon names come from `NavIcon` in `components/ui/NavIcon` — use existing icon names
seen in the file: `grid`, `store`, `upload`, `file-text`, `users`, `layers`, `edit`, `git-branch`,
`play`, `dollar`, `shield`, `briefcase`, `folder`, `workflow`, `diff`, `inbox`, `bell`, `settings`.
Additional valid Lucide names: `bar-chart-2`, `brain`, `trending-up`, `activity`, `zap`,
`target`, `pie-chart`, `database`, `cpu`.

### Current NAV_GROUPS summary
```
SETUP:     /dashboard, /marketplace, /excel-import, /afs (wrong — just "AFS Import"), /org-structures
CONFIGURE: /baselines, /drafts, /scenarios
ANALYZE:   /runs, /budgets, /covenants
REPORT:    /board-packs, /memos, /documents
```

### PIM frontend pages that exist (need sidebar entries)
- `/pim` — PIM overview/hub (page.tsx)
- `/pim/sentiment` — sentiment dashboard
- `/pim/universe` — investment universe
- `/pim/markov` — Markov state viewer
- `/pim/backtest` — backtest studio
- `/pim/pe` — PE assessment list
- `/pim/economic` — economic indicators

### AFS frontend pages that exist (need sidebar entries)
- `/afs` — AFS dashboard (engagement list)
- `/afs/frameworks` — compliance framework browser
- `/afs/[id]/setup` — engagement setup (account mapping)
- `/afs/[id]/sections` — section editor (AI disclosure drafter)
- `/afs/[id]/review` — review workflow
- `/afs/[id]/tax` — tax computation
- `/afs/[id]/consolidation` — multi-entity consolidation
- `/afs/[id]/output` — iXBRL/DOCX output
- `/afs/[id]/analytics` — AFS analytics

### instructions-config.ts — current structure
File is 1141 lines. It exports `getInstructionsForPath(pathname)` and a `INSTRUCTIONS_MAP`
record keyed by route string. Each entry is an `InstructionSection`:
```typescript
{
  title: string;
  chapter: string;   // e.g. "27" — next PIM chapter starts at "28"
  overview: string;  // 1-2 sentences
  steps: string[];   // 4-6 action steps
  prerequisites: [{ label, href }];
  relatedPages: [{ label, href }];
  tips?: string[];   // 2-3 power-user tips
}
```
AFS entries exist at lines 152–342 (chapters 20–26 approx). PIM needs chapters 28–35.
The last chapter in the file is chapter "26" at `/settings/compliance`.

### settings.py — PIM API keys (already declared as optional)
```python
# apps/api/app/core/settings.py lines ~100-105
polygon_api_key: str | None = Field(default=None, alias="POLYGON_API_KEY")
fred_api_key: str | None = Field(default=None, alias="FRED_API_KEY")
```
These are **already optional** — the services degrade gracefully when missing.
They are NOT in `.env.example` and NOT documented in `CLAUDE.md`.

### .env.example — add entries in the "PIM / External Data" section
Follow existing pattern: `VARIABLE_NAME=          # description`

### CLAUDE.md — Optional env vars table (line ~65 area)
Has a table with columns `Variable | Purpose | Default`.
PIM API keys need rows added to this table.

### DTF specification (from PIM build plan)
**DTF-A — Manual Calibration CLI** (`tools/dtf/calibrate.py`)
- Purpose: developer tool to inspect and manually override Markov transition matrix parameters
- Operations: `inspect` (print current matrix + steady-state), `override` (set specific transition probabilities),
  `validate` (check rows sum to 1.0), `reset` (restore from DB baseline)
- Reads/writes to the `pim_markov_states` table or equivalent Markov state storage
- CLI only — never on any API endpoint
- Uses `argparse` or `click`, produces human-readable output

**DTF-B — Automated Weekly Validation** (`tools/dtf/weekly_validator.py`)
- Purpose: weekly automated check that Markov model predictions match actuals
- Operations: fetch last N weeks of CIS predictions vs. actual outcomes, compute accuracy metrics
  (mean absolute error, rank correlation), flag if accuracy drops below threshold (0.6 IC)
- Output: writes a `dtf_validation_results` JSON report to `tools/dtf/reports/`
- Can be triggered as a Celery beat task or standalone `python tools/dtf/weekly_validator.py`
- Reads from `pim_cis_scores`, `pim_backtest_results` tables
- Does NOT modify any production data — read-only validation

**DTF tests:** `tests/unit/test_dtf_calibrate.py`, `tests/unit/test_dtf_validator.py`

### Excel add-in — current state (`apps/excel-addin/taskpane.js`)
The add-in has `onPull()` and `onPush()` handlers.
- **Pull is functional**: calls `POST /excel/connections/{id}/pull` and logs the binding values,
  but does NOT write values into Excel cells (uses `Excel.run` + named ranges needed)
- **Push is broken**: calls `POST /excel/connections/{id}/push` with `changes: []` (hardcoded empty)
- **What needs building**:
  1. Pull: after fetching binding values, use `Excel.run` to write each value into its named range cell
  2. Push: before calling push endpoint, use `Excel.run` to read current cell values for all bindings
     and populate the `changes` array with `{ binding_id, new_value }` objects
  3. Connection management UI: add a "List Connections" button that calls `GET /excel/connections`
     and populates a `<select>` dropdown so users don't need to type the connection ID manually

The add-in uses plain vanilla JS (no bundler). Office.js is loaded from CDN.
The `manifest.xml` already points to the correct task pane URL.
API contract for push: `POST /api/v1/excel/connections/{id}/push` body: `{ changes: [{ binding_id: str, new_value: any }] }`
API contract for pull: `POST /api/v1/excel/connections/{id}/pull` returns `{ values: [{ binding_id, current_value, cell_ref }] }`
API contract for list: `GET /api/v1/excel/connections` returns `{ items: [{ id, label, run_id }] }`

---

## PARALLELISATION RULES

1. Maximum 4 agent streams simultaneously
2. High-conflict files (VASidebar.tsx, instructions-config.ts) → Stream A only
3. Documentation files (CONTEXT.md, .env.example, CLAUDE.md) → Stream B only
4. DTF files are new (`tools/dtf/`) → Stream C only, no conflicts
5. Excel add-in files (`apps/excel-addin/`) → Stream D only, no conflicts
6. Every stream ends with: ruff/tsc check on touched files + fast gate subset
7. The final SP9-Z commit task runs after ALL streams complete

---

## DELIVERABLE: PARALLEL SPRINT PLAN

Produce a sprint plan and then IMMEDIATELY execute it using the agent streams below.
Do not just plan — plan and execute.

---

## STREAM DEFINITIONS

### Stream A — Navigation & Help Content (frontend-builder)
**Files owned exclusively:** `VASidebar.tsx`, `instructions-config.ts`
**Sequential within stream (A1 must complete before A2):**

**A1 — VASidebar restructure**
Remove `/afs` from the SETUP group.
Add a new group `"AFS"` (label: `"AFS"`, key: `"afs"`) immediately after SETUP containing:
```
{ href: "/afs",             label: "Engagements",  icon: "file-text" }
{ href: "/afs/frameworks",  label: "Frameworks",   icon: "database" }
```
Note: AFS sub-pages (/afs/[id]/*) are accessed from the engagement detail page, not the sidebar.

Add a new group `"INTELLIGENCE"` (label: `"INTELLIGENCE"`, key: `"intelligence"`) after ANALYZE containing:
```
{ href: "/pim",             label: "Overview",     icon: "brain" }
{ href: "/pim/sentiment",   label: "Sentiment",    icon: "activity" }
{ href: "/pim/universe",    label: "Universe",     icon: "target" }
{ href: "/pim/economic",    label: "Economic",     icon: "trending-up" }
{ href: "/pim/markov",      label: "Markov",       icon: "cpu" }
{ href: "/pim/backtest",    label: "Backtest",     icon: "bar-chart-2" }
{ href: "/pim/pe",          label: "PE",           icon: "pie-chart" }
```

After editing, run: `cd apps/web && npm run type-check` — fix any TypeScript errors.
Add/update the Vitest smoke test for VASidebar if one exists in `apps/web/tests/`.

**A2 — PIM InstructionsDrawer chapters**
Add 8 new entries to `INSTRUCTIONS_MAP` in `instructions-config.ts` for PIM routes.
Chapters start at "28" (chapter "27" is reserved for the PIM overview).
Use the AFS entries (lines 152–342) as the style template — same depth, same tone.

Entries needed:
```
"/pim"           ch:27  title:"Portfolio Intelligence"     overview: PIM hub — access all intelligence modules
"/pim/sentiment" ch:28  title:"Sentiment Analysis"         overview: real-time news sentiment scoring via Polygon.io
"/pim/universe"  ch:29  title:"Investment Universe"        overview: manage the tracked investment universe
"/pim/economic"  ch:30  title:"Economic Indicators"        overview: FRED macroeconomic data and regime classification
"/pim/markov"    ch:31  title:"Markov State Model"         overview: 81-state Markov chain — view transition matrix and steady-state
"/pim/backtest"  ch:32  title:"Backtest Studio"            overview: walk-forward backtesting with IC/ICIR/SPC metrics
"/pim/pe"        ch:33  title:"PE Benchmarking"            overview: PE fund assessment — DPI/TVPI/IRR vs. benchmark cohort
"/pim/pe/*"      ch:34  title:"PE Assessment Detail"       overview: individual fund analysis with J-curve and peer comparison
```

For each entry write:
- `overview`: 2 sentences explaining what the page does and who uses it
- `steps`: 4–5 concrete actions the user takes on this page
- `prerequisites`: link to the pages that must be set up first
- `relatedPages`: 2–3 natural next pages
- `tips`: 2 power-user tips (mark as optional if no tips come to mind)

After editing: `cd apps/web && npm run type-check` — instructions-config.ts is TypeScript.

**A stream acceptance:**
- `npm run type-check` passes with 0 errors on VASidebar.tsx and instructions-config.ts
- All 9 new INSTRUCTIONS_MAP entries are present and have all required fields
- The sidebar has the AFS group and INTELLIGENCE group in the correct positions

---

### Stream B — Documentation & Environment (general-purpose)
**Files owned exclusively:** `CONTEXT.md`, `.env.example`, `CLAUDE.md`

**B1 — Update CONTEXT.md**
The current CONTEXT.md is dated 2026-03-09 and describes PIM as "pre-development."
Rewrite the following sections to reflect the actual state as of 2026-03-16:

1. Update the header (`> Last updated`, `> Commit`, `> Total commits`)
2. Replace the "PIM Module Status" section — all 7 sprints are COMPLETE:
   - Sprint 0 (Remediation): ✅ Complete
   - Sprint 1 (Sentiment): ✅ Complete — `routers/pim_sentiment.py` (338 lines), `services/pim/sentiment_ingestor.py`
   - Sprint 2 (Economic/FRED): ✅ Complete — `services/pim/fred.py`, `routers/pim_universe.py`
   - Sprint 3 (CIS + Markov): ✅ Complete — `routers/pim_cis.py` (319 lines), `routers/pim_markov.py` (257 lines)
   - Sprint 4 (Portfolio): ✅ Complete — `routers/pim_portfolio.py` (364 lines), `services/pim/portfolio.py`
   - Sprint 5 (Backtesting): ✅ Complete — `routers/pim_backtest.py` (560 lines), materialized view migrations
   - Sprint 6 (PE + DTF shell): ✅ Complete — `routers/pim_pe.py`, `routers/pim_peer.py`
3. Update the "AFS Module Status" section — P6 is done (2026-03-15)
4. Update the "Current State" metrics table to match BACKLOG.md Sprint 8 values:
   - Backend tests: 640+ tests, 0 failed
   - E2E specs: 71 spec files, 0 failing
5. Add a "Sprint 8 — Platform Hardening" entry to "Recent Changes"
6. Update the "Backlog Summary" table — all tiers now complete except DTF and Excel add-in

**B2 — Add PIM API keys to .env.example and CLAUDE.md**
In `.env.example`, add a new section `# PIM / External Data (optional — PIM degrades gracefully when absent)`:
```
POLYGON_API_KEY=       # Polygon.io market data API key ($29/mo) — powers sentiment news feed
FRED_API_KEY=          # FRED (Federal Reserve Economic Data) API key (free) — powers economic indicators
```

In `CLAUDE.md`, add two rows to the Optional env vars table:
```
| `POLYGON_API_KEY` | Polygon.io news feed for PIM sentiment ingestion | (PIM sentiment module disabled) |
| `FRED_API_KEY` | FRED macroeconomic data for PIM economic indicators | (FRED data unavailable; mock data used) |
```

**B stream acceptance:**
- CONTEXT.md date is 2026-03-16, PIM sprint table shows all ✅
- `.env.example` has POLYGON_API_KEY and FRED_API_KEY with descriptions
- `CLAUDE.md` optional vars table has both new rows

---

### Stream C — DTF Build (pim-builder)
**Files owned exclusively:** `tools/dtf/` (new directory), `tests/unit/test_dtf_*.py`

Create `tools/dtf/` directory. All files here are developer CLI tools — NEVER exposed on any API endpoint.

**C1 — DTF-A: Markov Calibration CLI (`tools/dtf/calibrate.py`)**

```python
"""DTF-A: Markov model manual calibration CLI.

Developer tool — never call from API routes.
Usage:
  python tools/dtf/calibrate.py inspect
  python tools/dtf/calibrate.py validate
  python tools/dtf/calibrate.py override --from-state 0 --to-state 1 --probability 0.15
  python tools/dtf/calibrate.py reset

Operations:
  inspect   — print current transition matrix dimensions + top-5 steady-state states
  validate  — assert all rows sum to 1.0 ± 1e-9; print PASS/FAIL per row
  override  — set transition probability P(from→to); re-normalises the row
  reset     — restore matrix to the version computed from observed data
"""
```

Requirements:
- Use `argparse` for the CLI (no third-party CLI framework)
- Uses `asyncpg` and `asyncio.run()` to query the DB — reads `DATABASE_URL` from env
- Query target: the table storing Markov transition data (read `apps/api/app/routers/pim_markov.py`
  and `apps/api/app/services/pim/markov.py` to find the actual table name and schema)
- `inspect`: fetches matrix dimensions from DB, fetches steady-state vector from the
  `/pim/markov/steady-state` service logic (reuse `services/pim/markov.py` functions directly),
  prints a formatted table
- `validate`: fetches all rows of the transition matrix, checks each sums to 1.0 ± 1e-9,
  prints `ROW {i}: PASS/FAIL ({sum:.10f})`, exits with code 1 if any fail
- `override`: updates a single cell in the matrix, then re-normalises the affected row so it sums to 1.0
- `reset`: deletes manually-overridden rows and restores from a `_baseline` snapshot table
  (create the snapshot on first run if it doesn't exist)
- Adds `tools/dtf/__init__.py` (empty) and `tools/dtf/README.md` with usage instructions

**C2 — DTF-B: Weekly Validation (`tools/dtf/weekly_validator.py`)**

```python
"""DTF-B: Automated weekly Markov model validation.

Developer tool — run weekly via cron or manually:
  python tools/dtf/weekly_validator.py [--weeks N] [--output path/to/report.json]

Validates that CIS scores from N weeks ago predicted actual outcomes correctly.
Writes a JSON report to tools/dtf/reports/YYYY-MM-DD.json.
Exits with code 0 if IC >= 0.4, code 1 if IC < 0.4 (below acceptable threshold).
"""
```

Requirements:
- Fetches CIS scores from `pim_cis_scores` (or equivalent table — inspect the migration files
  at `apps/api/app/db/migrations/` to find the actual CIS score table)
- Computes Information Coefficient (IC) = Spearman rank correlation between predicted CIS rank
  and actual return rank over the validation period
- Writes JSON report: `{ date, weeks_evaluated, ic_score, ic_threshold: 0.4, pass: bool, n_observations, details: [...] }`
- Creates `tools/dtf/reports/` directory if it doesn't exist
- Handles no-data gracefully: if fewer than 10 observations, writes report with `{ pass: null, reason: "insufficient_data" }`

**C3 — DTF tests**
Write `tests/unit/test_dtf_calibrate.py`:
- Test `validate()` logic with a mock matrix where one row sums to 1.01 (should FAIL)
- Test `validate()` with a perfect matrix (should PASS)
- Test `override()` re-normalisation: after setting P(0→1)=0.5, assert row 0 sums to 1.0

Write `tests/unit/test_dtf_validator.py`:
- Test IC computation with known inputs (mock correlation pairs)
- Test insufficient-data path (n < 10 returns `pass: null`)
- Test report JSON structure matches expected schema

After implementing, run:
```bash
cd /home/gregmorris/projects/virtual_analyst
ruff check tools/dtf/
mypy tools/dtf/
pytest tests/unit/test_dtf_calibrate.py tests/unit/test_dtf_validator.py -v --tb=short
```

**C stream acceptance:**
- `ruff check tools/dtf/` passes
- `mypy tools/dtf/` passes (or errors are pre-existing in imported services only)
- 6+ tests pass in test_dtf_calibrate.py + test_dtf_validator.py
- `tools/dtf/README.md` documents all commands with examples
- Neither file imports from any router — DTF only imports from `services/pim/` and `db/`

---

### Stream D — Excel Add-in Enhancement (general-purpose)
**Files owned exclusively:** `apps/excel-addin/taskpane.js`, `apps/excel-addin/taskpane.html`

Read the current `taskpane.js` and `taskpane.html` fully before making changes.

**D1 — Fix Pull: write values into Excel cells**
After a successful pull response, iterate over `data.values` and write each value to its cell.
Use the `cell_ref` field from the pull response (e.g. `"B5"`, `"Revenue!C3"`):

```javascript
await Excel.run(async (context) => {
  for (const binding of data.values) {
    if (binding.cell_ref && binding.current_value !== undefined) {
      const range = context.workbook.worksheets
        .getActiveWorksheet()
        .getRange(binding.cell_ref);
      range.values = [[binding.current_value]];
    }
  }
  await context.sync();
});
```

Handle the case where `cell_ref` is null (some bindings may not have a cell reference) — skip those gracefully.

**D2 — Fix Push: read cell values before sending**
Before calling the push endpoint, use `Excel.run` to read current cell values for all bindings.
Fetch the binding list first (`GET /excel/connections/{id}/pull` to get `data.values` which includes `cell_ref`),
then read each cell's current value:

```javascript
// Step 1: get binding list (reuse pull response if recently fetched, else re-fetch)
// Step 2: read current cell values using Excel.run
const changes = [];
await Excel.run(async (context) => {
  for (const binding of bindings) {
    if (binding.cell_ref) {
      const range = context.workbook.worksheets
        .getActiveWorksheet()
        .getRange(binding.cell_ref);
      range.load("values");
      await context.sync();
      changes.push({ binding_id: binding.binding_id, new_value: range.values[0][0] });
    }
  }
});
// Step 3: POST to push endpoint with the populated changes array
```

**D3 — Add connection list dropdown**
In `taskpane.html`, replace the manual `connectionId` text input with:
```html
<label>Connection<br/>
  <select id="connectionSelect"><option value="">-- select --</option></select>
  <button id="btnRefreshConnections">↻</button>
</label>
```

In `taskpane.js`, add `onRefreshConnections()`:
- Calls `GET {apiUrl}/excel/connections` with tenant headers
- Populates the `<select>` with `{ value: item.id, label: item.label || item.id }` options
- Updates `connectionIdEl` value when selection changes

Wire the refresh button and auto-call on page load when `apiUrl` and `tenantId` are set.

**D stream acceptance:**
- Pull: after clicking Pull, if cell references are returned, cell values are written to the workbook
- Push: clicking Push reads current cell values and sends non-empty `changes` array when cells have been modified
- Connection dropdown: clicking ↻ populates the list from the API
- The vanilla JS changes do not break existing Pull/Push functionality
- No TypeScript compile step needed (vanilla JS file)

---

## FINAL TASK: SP9-Z — Commit, Push, Update BACKLOG

After ALL 4 streams complete:

1. Run the full fast gate from project root:
```bash
cd /home/gregmorris/projects/virtual_analyst
ruff check tools/dtf/ && \
mypy tools/dtf/ apps/api/app/routers/pim_cis.py apps/api/app/routers/pim_markov.py && \
pytest tests/unit/test_dtf_calibrate.py tests/unit/test_dtf_validator.py -v --tb=short && \
cd apps/web && npm run type-check && npm run test && cd ../..
```

2. Update `BACKLOG.md`:
   - In the Current Status table: add Sprint 9 row showing all 7 product items complete
   - Add `| Sprint 9 — Product Completion | (2026-03-16) | [description] |` to Completed Rounds

3. Commit with message:
```
feat(sprint9): product completion — PIM/AFS navigation, DTF, Excel add-in, docs

Stream A: VASidebar — AFS group (Engagements, Frameworks) + INTELLIGENCE group
  (7 PIM pages); 8 new InstructionsDrawer chapters for PIM (ch27–34)
Stream B: CONTEXT.md updated to Sprint 8 state; POLYGON_API_KEY + FRED_API_KEY
  added to .env.example and CLAUDE.md optional vars table
Stream C: DTF-A calibrate.py (inspect/validate/override/reset CLI) + DTF-B
  weekly_validator.py (IC-based Markov accuracy monitoring); 6 new tests
Stream D: Excel add-in — Pull writes cell values via Excel.run; Push reads
  cell values before sending changes[]; connection dropdown with refresh
```

---

## CONSTRAINTS

1. Do NOT add Stripe/billing work — explicitly deferred to post-beta
2. Do NOT modify any router or service files except to import DTF helpers
3. `tools/dtf/` is CLI only — zero imports in any `apps/api/app/routers/` file
4. VASidebar.tsx and instructions-config.ts are touched by Stream A ONLY
5. CONTEXT.md, .env.example, CLAUDE.md are touched by Stream B ONLY
6. All 4 streams must complete before SP9-Z
7. The fast gate must pass before committing
8. Do not rebuild or re-test anything that already passes — focus on new work only
9. Excel add-in is vanilla JS — no bundler, no TypeScript, no npm install
10. DTF files go in `tools/dtf/` — not in `apps/`, not in `tests/` (tests go in `tests/unit/`)

---

## SUCCESS CRITERIA

Sprint 9 is done when:
- [ ] Sidebar has AFS group (2 items) and INTELLIGENCE group (7 items) — verified by `npm run type-check`
- [ ] 8 PIM routes have InstructionsDrawer entries (ch27–34) — verified by TypeScript compile
- [ ] CONTEXT.md header says 2026-03-16, PIM shows all ✅
- [ ] `.env.example` has POLYGON_API_KEY and FRED_API_KEY
- [ ] `tools/dtf/calibrate.py` inspect/validate/override/reset all work
- [ ] `tools/dtf/weekly_validator.py` runs and produces a JSON report in `tools/dtf/reports/`
- [ ] 6+ DTF unit tests passing
- [ ] Excel add-in Pull writes values; Push sends non-empty changes; dropdown works
- [ ] Fast gate passes: ruff + mypy + pytest dtf tests + vitest + tsc
- [ ] BACKLOG.md Sprint 9 row added and committed
