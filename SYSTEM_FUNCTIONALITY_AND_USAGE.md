# Virtual Analyst — System Functionality & Usage Guide

This document describes **all functionality** of the Virtual Analyst (VA) system and provides **instructions for setup and use**. It is the single reference for scope, capabilities, and operations.

---

## 1. Introduction & system overview

**Virtual Analyst** is a deterministic financial modeling platform with an LLM-assisted draft layer. It supports:

- **Core engine:** Model baselines, runs, three-statement outputs (P&L, balance sheet, cash flow), KPIs, Monte Carlo, sensitivity, and valuation.
- **Draft layer:** LLM-assisted assumption editing, chat, proposals, and commit-to-baseline with changesets.
- **Ventures:** Template-based venture creation with questionnaire and LLM-generated draft.
- **Scenarios:** Scenario CRUD and comparison.
- **Integrations:** Xero and QuickBooks OAuth, sync, and canonical snapshots.
- **Collaboration:** Teams, job functions, workflow templates/instances, task assignments, reviews, change summaries, learning feedback, and notifications.
- **Budgeting:** Full budget lifecycle (draft → submitted → under_review → approved → active → closed), line items, periods, department allocations, templates, actuals, variance, reforecast, and approval workflow.
- **Board packs:** Composer, generate, export (PDF/PPTX/HTML), branding, scheduling, distribution, and optional benchmarking.
- **Enterprise:** Multi-currency/FX, SSO/SAML, template and connector marketplaces, workflow analytics, AI review suggestions, peer benchmark, and natural language budget queries.

**Deployment targets:**

- **Backend:** FastAPI service (e.g. Render).
- **Frontend:** Next.js web app (e.g. Vercel).
- **Worker:** Celery + Redis for async jobs (MC runs, reminders, etc.).
- **Database:** PostgreSQL (e.g. Supabase or standalone).
- **Auth:** Supabase Auth (email/password, Google, Microsoft) plus optional SAML 2.0.

---

## 2. Architecture summary

| Layer        | Technology        | Purpose |
|-------------|-------------------|--------|
| API         | FastAPI, Python 3 | REST API at `/api/v1`, health, metrics, auth middleware |
| Web         | Next.js, React    | Login, dashboard, baselines, runs, drafts, budgets, board packs, inbox, teams, etc. |
| Worker      | Celery, Redis     | Async run execution (including Monte Carlo), deadline reminders |
| Database    | PostgreSQL        | Tenants, users, baselines, runs, workflows, budgets, audit, etc. |
| Auth        | Supabase Auth     | Email/password, OAuth (Google/Microsoft), optional SAML |
| Storage     | Supabase Storage  | Artifacts, draft workspaces, documents |
| Observability | Prometheus       | `/metrics`; in-memory latency summary at `/api/v1/metrics/summary` |

**Key middleware:**

- **Auth:** When `SUPABASE_JWT_SECRET` is set, API requires `Authorization: Bearer <token>` and sets `X-Tenant-ID` / `X-User-ID` from the JWT; the user’s **role** is loaded from the `users` table and set on `request.state.role` for RBAC. Paths under `/api/v1/health`, `/api/v1/auth/saml/`, `/api/v1/billing/webhook`, `/api/v1/billing/plans`, `/api/v1/assignments/cron/deadline-reminders`, `/metrics`, `/`, `/docs`, `/redoc` skip auth.
- **RBAC:** Every protected route uses a `require_role(...)` dependency. Allowed roles per route follow the permission matrix (owner, admin, analyst, investor). Read-only routes (e.g. baselines/runs list and get, memos read, notifications) allow all roles; write/commit routes require analyst or above; integrations, audit, compliance, teams, billing manage, and SAML config require owner or admin as specified.
- **CORS:** Configurable via `CORS_ALLOWED_ORIGINS`.
- **Security:** Security headers, rate limiting (`RATE_LIMIT`), optional `CRON_SECRET` for cron endpoints.

---

## 3. Setup and run instructions

### 3.1 Prerequisites

- Python 3.x, Node.js, Docker (for Postgres/Redis/Supabase locally).
- Git (monorepo).

### 3.2 Environment

1. Copy the example env file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set at least:
   - **Database:** `DATABASE_URL` (e.g. `postgresql://postgres:postgres@localhost:5432/finmodel_dev`).
   - **Supabase:** `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`; optionally `SUPABASE_JWT_SECRET` for API JWT verification.
   - **Redis:** `REDIS_URL` (e.g. `redis://localhost:6379`) for Celery and caching.
   - **Security:** `JWT_SECRET`, `ENCRYPTION_KEY`; for OAuth token encryption set `OAUTH_ENCRYPTION_KEY` (Fernet key).
   - **API/Web:** `CORS_ALLOWED_ORIGINS`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
   - **Integrations (optional):** `XERO_CLIENT_ID`, `XERO_CLIENT_SECRET`; `QUICKBOOKS_CLIENT_ID`, `QUICKBOOKS_CLIENT_SECRET`; `INTEGRATION_CALLBACK_BASE_URL`, `INTEGRATION_OAUTH_REDIRECT_URI`.
   - **Billing (optional):** `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, Stripe price IDs.
   - **LLM (optional):** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (if unset, mock used in dev).

### 3.3 Database migrations

Migrations live under `apps/api/app/db/migrations/`.

**Order:**

1. **Baseline (required first):**
   - `0001_init.sql` — core tables (tenants, users, draft_sessions, model_baselines, model_changesets, ventures, venture_artifacts, runs, run_artifacts, etc.).
   - `0002_functions_and_rls.sql` — `current_tenant_id()`, `generate_id()`, RLS on baseline tables.

2. **All pending (0008–0040):**
   - **Preferred:** Run **`APPLY_ALL_MIGRATIONS.sql`** once (applies 0008 through 0040 in order).
   - **Alternative:** Run `RUN_ALL_PENDING_MIGRATIONS.sql` (through 0028), then 0029–0040 in numeric order.

**Example:**

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/finmodel_dev"

psql "$DATABASE_URL" -f apps/api/app/db/migrations/0001_init.sql
psql "$DATABASE_URL" -f apps/api/app/db/migrations/0002_functions_and_rls.sql
psql "$DATABASE_URL" -f apps/api/app/db/migrations/APPLY_ALL_MIGRATIONS.sql
```

See `apps/api/app/db/migrations/README.md` for Supabase and other notes.

### 3.4 Local services

```bash
docker-compose up -d
```

This starts Postgres, Redis, and (if configured) Supabase. Ensure health checks pass.

### 3.5 API server

```bash
python -m venv .venv
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
pip install -e ".[dev]"
uvicorn apps.api.app.main:app --host 0.0.0.0 --port 8000
```

API base: `http://localhost:8000`. Docs: `http://localhost:8000/docs`, ReDoc: `http://localhost:8000/redoc`.

### 3.6 Web app

From repo root, with API running:

```bash
cd apps/web && npm install && npm run dev
```

Web app: `http://localhost:3000`. Set `NEXT_PUBLIC_API_URL=http://localhost:8000` (and Supabase vars) in `.env`.

### 3.7 Celery worker

For async jobs (e.g. Monte Carlo runs, scheduled tasks):

```bash
celery -A apps.worker.celery_app worker -l info
```

Requires Redis (`REDIS_URL`).

### 3.8 Cron (deadline reminders)

Call the deadline-reminders endpoint on a schedule (e.g. every 15 minutes). If `CRON_SECRET` is set, send it in the request:

```bash
curl -X POST "http://localhost:8000/api/v1/assignments/cron/deadline-reminders" \
  -H "X-Cron-Secret: YOUR_CRON_SECRET"
```

---

## 4. Authentication and request context

### 4.1 Supabase Auth (email/password, Google, Microsoft)

- Users sign up and sign in via the web app (Supabase Auth).
- The web app sends the Supabase access token as `Authorization: Bearer <token>` to the API.
- When `SUPABASE_JWT_SECRET` is set, the API verifies the JWT and sets tenant/user from the token; you do **not** need to send `X-Tenant-ID` / `X-User-ID` (they are overwritten from the token).

### 4.2 Headers when JWT is not used

If the API is called without Supabase JWT (e.g. server-to-server or tests), and `SUPABASE_JWT_SECRET` is not set, the API may rely on:

- **X-Tenant-ID:** Tenant identifier.
- **X-User-ID:** User identifier (optional for some routes).

These are standard request headers; see middleware and RLS for tenant isolation.

### 4.3 SAML SSO (enterprise)

- **Login:** `GET /api/v1/auth/saml/login` — redirects to IdP.
- **ACS:** `POST /api/v1/auth/saml/acs` — IdP posts SAML response; API creates/links user and session.
- **Config:** `GET /api/v1/auth/saml/config`, `PUT /api/v1/auth/saml/config` — tenant SAML configuration (metadata URL/XML, entity ID, ACS URL, attribute mapping).

When SAML is configured for a tenant, users can sign in via SAML; non-SAML tenants continue with Supabase Auth.

### 4.4 Creating an Admin user

User records and roles live in the `users` table (`id`, `tenant_id`, `email`, `role`). Allowed roles: `owner`, `admin`, `analyst`, `investor`. The API does not sync Supabase Auth signups into `users` automatically; you create or update the row yourself.

**1. Get your identifiers**

- **User ID:** Supabase Dashboard → Authentication → Users → your user → copy the **User UID** (same as JWT `sub`). Or after logging in, decode your JWT at [jwt.io](https://jwt.io) and use the `sub` value.
- **Tenant ID:** The app uses `user_metadata.tenant_id` or `app_metadata.tenant_id` from the JWT if set; otherwise it falls back to the user id. For a single-tenant setup you can use your user id as the tenant id.

**2. Ensure the tenant exists**

```bash
psql "$DATABASE_URL" -c "INSERT INTO tenants (id, name) VALUES ('YOUR_TENANT_ID', 'My Organisation') ON CONFLICT (id) DO NOTHING;"
```

**3. Insert or update your user with role `admin`**

Row-level security on `users` requires `tenant_id = current_tenant_id()`. Run as a database superuser (e.g. the same role used for migrations) so you can set the session or bypass RLS.

**Option A — You already have a row in `users` (e.g. from SAML or a previous insert):**

```sql
UPDATE users SET role = 'admin' WHERE id = 'YOUR_SUPABASE_USER_UID' AND tenant_id = 'YOUR_TENANT_ID';
```

**Option B — No row yet (e.g. email/password signup only):**

```sql
-- As DB superuser: set tenant context then insert (RLS allows insert when tenant_id matches)
SET app.tenant_id = 'YOUR_TENANT_ID';
INSERT INTO users (id, tenant_id, email, role)
VALUES ('YOUR_SUPABASE_USER_UID', 'YOUR_TENANT_ID', 'your@email.com', 'admin')
ON CONFLICT (id) DO UPDATE SET role = 'admin', email = EXCLUDED.email, tenant_id = EXCLUDED.tenant_id;
```

If your DB user cannot set `app.tenant_id`, use a single connection with RLS bypass:

```sql
-- Run once as superuser; restore RLS after
ALTER TABLE users DISABLE ROW LEVEL SECURITY;
INSERT INTO users (id, tenant_id, email, role)
VALUES ('YOUR_SUPABASE_USER_UID', 'YOUR_TENANT_ID', 'your@email.com', 'admin')
ON CONFLICT (id) DO UPDATE SET role = 'admin', email = EXCLUDED.email, tenant_id = EXCLUDED.tenant_id;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
```

Replace `YOUR_SUPABASE_USER_UID`, `YOUR_TENANT_ID`, and `your@email.com` with your values. After this, your user is an admin in the database. The API enforces role-based permissions on every protected route (see §4 and §6).

---

## 5. Functionality by area

### 5.1 Core deterministic engine

- **Model baselines:** Create, list, get, patch. One active baseline per tenant; versioned model config stored and validated (graph, expressions).
- **Runs:** Create run from baseline (sync or async). Sync runs return statements/KPIs; async (e.g. Monte Carlo) use Celery; poll run status and get results when complete.
- **Outputs:** Three statements (income statement, balance sheet, cash flow), KPI calculator (margins, ratios, working capital). Stored as run artifacts.
- **Monte Carlo:** Run with `mc_enabled`, `num_simulations`, `seed`; progress via run status; results: percentiles (e.g. P5–P95) for revenue, EBITDA, net income, FCF.
- **Sensitivity:** One-at-a-time sensitivity (e.g. ±% on drivers), terminal FCF impact; used for tornado/fan charts.
- **Valuation:** DCF and multiples; optional `valuation_config` on run; results at `GET /runs/{id}/valuation`.
- **Excel export:** `GET /api/v1/runs/{run_id}/export/excel` — IS/BS/CF and KPIs.

**API:** `baselines`, `runs`, `metrics_summary` (latency). **Web:** `/baselines`, `/baselines/[id]`, `/runs`, `/runs/[id]`, `/runs/[id]/mc`, `/runs/[id]/valuation`, `/dashboard`.

---

### 5.2 Draft layer and LLM

- **Draft sessions:** CRUD; state machine (active, ready_to_commit, committed, abandoned). Workspace (assumptions) stored in artifact store; autosave via PATCH.
- **Draft chat:** `POST /api/v1/drafts/{id}/chat` — send message; LLM returns structured proposals (paths under assumptions). Proposals can be accepted or rejected via `/proposals/{id}/accept` and `/rejects`.
- **Commit:** `POST /api/v1/drafts/{id}/commit` — compile workspace to frozen model_config, integrity checks (e.g. acyclic graph), create baseline; draft status → committed.
- **Changesets:** Create changeset from diffs; dry-run test (engine); merge into new baseline version. Used for collaborative model evolution.
- **LLM:** Provider abstraction (Anthropic, OpenAI), router with circuit breaker and metering; task labels (e.g. draft_assumptions, template_initialization, review_summary, budget_initialization, board_pack_narrative). Confidence and evidence in proposals; content safety checks.

**API:** `drafts`, `changesets`. **Web:** `/drafts`, `/drafts/[id]` (workspace, chat, proposals, commit, abandon).

---

### 5.3 Ventures and templates

- **Ventures:** Create venture from template (`POST /api/v1/ventures`); submit questionnaire answers (`POST /api/v1/ventures/{id}/answers`); generate draft with LLM (`POST /api/v1/ventures/{id}/generate-draft`). Template catalog (e.g. manufacturing, wholesale, services, SaaS, fintech) in default catalog.
- **Template marketplace:** List and get marketplace templates; “use template” creates baseline or budget from template. Audit log records template use.
- **API:** `ventures`, `marketplace` (templates). **Web:** Venture flow can start from template selection and questionnaire.

---

### 5.4 Scenarios

- **Scenario CRUD:** Create, list, get, delete scenarios (with overrides).
- **Compare:** `POST /api/v1/scenarios/compare` — side-by-side KPIs/variance.
- **API:** `scenarios`. **Web:** `/scenarios` (list and compare).

---

### 5.5 Integrations and connectors

- **Connections:** OAuth2 connect (Xero, QuickBooks); list connections; trigger sync; list snapshots; delete connection. Callback URL and redirect URI must match provider config.
- **Connector marketplace:** List available connectors; get connector by id (config schema, capabilities). QuickBooks adapter: OAuth, sync chart of accounts and actuals into budget/runs.
- **Sync:** Sync produces canonical snapshot; actuals can feed budget variance or run inputs.
- **API:** `integrations` (connections, callback, sync, snapshots), `connectors`. **Web:** Integration/connection management UI can call these endpoints.

---

### 5.6 Audit, compliance, covenants

- **Audit:** Append-only audit log. List events (filter by type, date, actor); event catalog; export (e.g. CSV).
- **Compliance:** GDPR-style export (`GET /api/v1/compliance/export`); user anonymization (`POST /api/v1/compliance/anonymize-user`).
- **Covenants:** Metric refs for covenant definitions; CRUD covenants; covenant monitoring and breach alerts (e.g. from import or run data).
- **API:** `audit`, `compliance`, `covenants`.

---

### 5.7 CSV import

- **Import:** `POST /api/v1/import/csv` — upload CSV; import wizard can create draft or link to covenant monitoring; breaches trigger alerts.
- **API:** `import_csv`.

---

### 5.8 Excel connections and memos

- **Excel connections:** CRUD connections; pull (API → Excel) and push (Excel → API) for live-linked workbooks. Used by Office Add-in.
- **Excel export:** `GET /api/v1/runs/{run_id}/export/excel` (IS/BS/CF, KPIs).
- **Memos:** Create memo from run/config; list, get, delete; download as HTML or PDF (`GET /memos/{id}/download?format=html|pdf`).
- **Documents:** Upload, list, get, delete document attachments.
- **Comments:** Create, list, delete comments; @mentions can trigger notifications.
- **Activity:** Merged feed of audit events and comments (`GET /api/v1/activity`).
- **API:** `excel`, `memos`, `documents`, `comments`, `activity`. **Web:** Document and comment UIs; activity feed.

---

### 5.9 Teams and job functions

- **Teams:** CRUD; hierarchy (reports_to) validated within team; RLS enforced.
- **Members:** Add, remove, update members; list by team.
- **Job functions:** List (with defaults seeded for tenants); used for workflow assignee rules.
- **API:** `teams` (teams, members, job-functions/list). **Web:** `/settings/teams`, `/settings/teams/[teamId]` (members, hierarchy tree).

---

### 5.10 Workflow engine

- **Templates:** List, get workflow templates. Stages with assignee rules (explicit, reports_to, reports_to_chain, team_pool). Default templates (e.g. Self-Service, Standard Review, Full Approval). Cross-team stages supported (multi-team approval chains).
- **Instances:** Create instance from template; list (filter by entity_type, status); get, patch. State machine: pending → in_progress → submitted → approved/returned → completed.
- **Assignments:** Create assignment (top-down); list (inbox); pool list; claim pool assignment; submit for review; patch. Deadline tracking; 24h/4h/overdue reminders via cron.
- **Reviews:** Submit review (approve, request_changes, reject); inline corrections as structured diff (path, old_value, new_value, reason); change summary auto-generated; learning points (LLM) on request_changes/rejected — AI-assisted review suggestions.
- **Feedback:** List change summaries; acknowledge (author marks read). Unacknowledged highlighted in UI.
- **Notifications:** Task assigned, submitted, review decision, deadline approaching/overdue, workflow completed. In-app and (when configured) email.
- **Analytics:** `GET /api/v1/workflows/analytics` — cycle time, time per stage, review rate, bottlenecks (tenant, optional template_id, date range).
- **API:** `workflows` (templates, instances, analytics), `assignments` (create, list, pool, claim, submit, review, cron/deadline-reminders), `feedback`, `notifications`. **Web:** `/inbox`, `/inbox/[id]`, `/inbox/[id]/review`, `/inbox/feedback`, `/assignments/new`, `/notifications`.

---

### 5.11 Budgets

- **CRUD:** Create, list, get, patch budgets. Lifecycle: draft → submitted → under_review → approved → active → closed. Versioning: immutable budget versions (revision history).
- **Periods and line items:** Periods CRUD; line items with monthly amounts, account ref, notes; confidence scores when LLM-assisted.
- **Departments:** Allocate budget by department/cost centre; sum validated against version totals.
- **Templates:** List budget templates; create budget from template (wizard with questionnaire); LLM seeds initial amounts (budget_initialization).
- **Actuals and variance:** Import actuals (JSON or from ERP sync); variance (budget vs actual, absolute, %, YTD); favourable/unfavourable; materiality threshold; drill-down by period/department. `GET /api/v1/budgets/{id}/variance`.
- **Reforecast:** `POST /api/v1/budgets/{id}/reforecast` — new version with actuals locked and remaining periods re-projected; LLM task budget_reforecast for revised forecast and variance explanations.
- **Approval workflow:** Budget submission creates workflow instance; stages (e.g. department_head_review → finance_review → cfo_approval → board_presentation); CFO approval transitions budget to active.
- **Dashboard:** Burn rate, runway, utilisation %, variance trend, department ranking; optional alerts (e.g. >90% utilised, unfavourable variance >10%).
- **NL query:** `POST /api/v1/budgets/nl-query` — natural language question over budget/dashboard data; LLM with tool use or structured query; factual answer with optional citations.
- **API:** `budgets` (full CRUD, templates, from-template, dashboard, nl-query, submit, periods, line-items, departments, clone, actuals/import, variance, reforecast). **Web:** `/budgets`, `/budgets/new`, `/budgets/[id]`, `/budgets/[id]/variance`, `/budgets/[id]/reforecast`.

---

### 5.12 Board packs

- **Composer:** Create board pack; configure sections (executive summary, P&L, BS, CF, budget variance, KPI dashboard, scenario comparison, strategic commentary); section order and inclusion; auto-populated from run results, budget variance, KPI, scenario compare. LLM task board_pack_narrative for narrative (facts-only). Branding: tenant logo, colour palette, T&C footer.
- **Generate:** `POST /api/v1/board-packs/{pack_id}/generate` — assemble and generate pack.
- **Export:** `GET /api/v1/board-packs/{pack_id}/export?format=pdf|pptx|html` — PDF (layout, ToC, charts, tables), PPTX (one section per slide), HTML (preview/email). Charts: IS/BS/CF waterfall, variance bar, KPI trend, scenario tornado, MC fan. Optional benchmark section (industry median from peer or external dataset).
- **Scheduling:** Create schedule (e.g. monthly on 5th business day); list schedules; run-now; pack history with download links and metadata; distribute (email to recipients with optional cover note).
- **API:** `board_packs` (CRUD, generate, export), `board_pack_schedules` (CRUD, history, run-now, distribute). **Web:** `/board-packs`, `/board-packs/new`, `/board-packs/[id]`.

---

### 5.13 Multi-currency and FX

- **Tenant settings:** Base currency, reporting currency, FX source (manual or feed).
- **Rates:** List, create, delete FX rates (from_currency, to_currency, effective_date). Rates auditable.
- **Convert:** `GET /api/v1/currency/convert` — convert amount at configured rates. Run output and board pack support currency toggle.
- **API:** `currency` (settings, rates, convert).

---

### 5.14 Billing and usage

- **Plans:** List plans (e.g. Starter, Professional).
- **Subscription:** Get, create, delete subscription (Stripe).
- **Usage:** Get usage (metering); limits enforced (e.g. LLM tokens, seats).
- **Webhook:** Stripe webhook for subscription lifecycle.
- **API:** `billing` (plans, subscription, usage, webhook).

---

### 5.15 Benchmark (peer comparison)

- **Opt-in:** Tenant opts in to anonymous benchmarking (no PII). GET/PUT/DELETE opt-in.
- **Summary:** “Your run vs peer median” style summary (opt-in tenants only).
- **Aggregates:** Aggregated metrics by segment (industry, size) without tenant identity.
- **API:** `benchmark` (opt-in, summary, aggregates).

---

### 5.16 Jobs (async tasks)

- **Enqueue:** `POST /api/v1/jobs/enqueue` — body e.g. `{"task": "add", "args": [1, 2]}`; returns `task_id`.
- **Status:** `GET /api/v1/jobs/{task_id}` — poll for status. Failed jobs after retries go to Redis DLQ (`celery:dlq`).
- **API:** `jobs`. Used internally for Monte Carlo and other async work.

---

## 6. API reference (by router)

All routes are under prefix `/api/v1` unless noted. Auth: send `Authorization: Bearer <token>` when `SUPABASE_JWT_SECRET` is set.

| Router | Key endpoints |
|--------|----------------|
| **health** | `GET /health/live`, `GET /health/ready` |
| **auth_saml** | `GET /auth/saml/login`, `POST /auth/saml/acs`, `GET /auth/saml/config`, `PUT /auth/saml/config` |
| **baselines** | `POST /baselines`, `GET /baselines`, `GET /baselines/{id}`, `PATCH /baselines/{id}` |
| **runs** | `POST /runs`, `GET /runs`, `GET /runs/{id}`, `GET /runs/{id}/statements`, `GET /runs/{id}/kpis`, `GET /runs/{id}/mc`, `GET /runs/{id}/sensitivity`, `GET /runs/{id}/valuation`, `GET /runs/{id}/export/excel` |
| **drafts** | `POST /drafts`, `GET /drafts`, `GET /drafts/{id}`, `PATCH /drafts/{id}`, `DELETE /drafts/{id}`, `POST /drafts/{id}/chat`, `POST /drafts/{id}/proposals/{pid}/accept`, `POST /drafts/{id}/proposals/{pid}/reject`, `POST /drafts/{id}/commit` |
| **changesets** | `POST /changesets`, `GET /changesets/{id}`, `POST /changesets/{id}/test`, `POST /changesets/{id}/merge` |
| **ventures** | `POST /ventures`, `POST /ventures/{id}/answers`, `POST /ventures/{id}/generate-draft` |
| **scenarios** | `POST /scenarios`, `GET /scenarios`, `GET /scenarios/{id}`, `DELETE /scenarios/{id}`, `POST /scenarios/compare` |
| **integrations** | `POST /integrations/connections`, `GET /integrations/connections/callback`, `GET /integrations/connections`, `GET /integrations/connections/{id}`, `POST /integrations/connections/{id}/sync`, `GET /integrations/connections/{id}/snapshots`, `DELETE /integrations/connections/{id}` |
| **connectors** | `GET /connectors`, `GET /connectors/{id}` |
| **jobs** | `POST /jobs/enqueue`, `GET /jobs/{task_id}` |
| **notifications** | `GET /notifications`, `PATCH /notifications/{id}` |
| **audit** | `GET /audit/events/catalog`, `GET /audit/events`, `GET /audit/events/export` |
| **compliance** | `GET /compliance/export`, `POST /compliance/anonymize-user` |
| **import_csv** | `POST /import/csv` |
| **covenants** | `GET /covenants/metric-refs`, `GET /covenants`, `POST /covenants`, `DELETE /covenants/{id}` |
| **excel** | `POST /excel/connections`, `GET /excel/connections`, `GET/PATCH/DELETE /excel/connections/{id}`, `POST /excel/connections/{id}/pull`, `POST /excel/connections/{id}/push` |
| **memos** | `POST /memos`, `GET /memos`, `GET /memos/{id}`, `GET /memos/{id}/download`, `DELETE /memos/{id}` |
| **documents** | `POST /documents`, `GET /documents`, `GET /documents/{id}`, `DELETE /documents/{id}` |
| **comments** | `POST /comments`, `GET /comments`, `DELETE /comments/{id}` |
| **activity** | `GET /activity` |
| **teams** | `GET /teams`, `POST /teams`, `GET /teams/job-functions/list`, `GET /teams/{id}`, `PATCH /teams/{id}`, `DELETE /teams/{id}`, `GET /teams/{id}/members`, `POST /teams/{id}/members`, `PATCH /teams/{id}/members/{uid}`, `DELETE /teams/{id}/members/{uid}` |
| **workflows** | `GET /workflows/templates`, `GET /workflows/templates/{id}`, `POST /workflows/instances`, `GET /workflows/instances`, `GET /workflows/instances/{id}`, `PATCH /workflows/instances/{id}`, `GET /workflows/analytics` |
| **assignments** | `POST /assignments`, `GET /assignments`, `GET /assignments/pool`, `GET /assignments/{id}`, `POST /assignments/{id}/claim`, `POST /assignments/{id}/submit`, `PATCH /assignments/{id}`, `POST /assignments/{id}/review`, `GET /assignments/{id}/reviews`, `POST /assignments/cron/deadline-reminders` |
| **feedback** | `GET /feedback`, `POST /feedback/{summary_id}/acknowledge` |
| **budgets** | `POST /budgets`, `GET /budgets`, `GET /budgets/templates`, `POST /budgets/from-template`, `GET /budgets/dashboard`, `POST /budgets/nl-query`, `GET /budgets/{id}`, `POST /budgets/{id}/submit`, `PATCH /budgets/{id}`, `GET/POST /budgets/{id}/periods`, `GET /budgets/{id}/line-items`, `POST /budgets/{id}/line-items`, `PATCH /budgets/{id}/line-items/{lid}`, `DELETE /budgets/{id}/line-items/{lid}`, `GET /budgets/{id}/departments`, `POST /budgets/{id}/departments`, `POST /budgets/{id}/clone`, `POST /budgets/{id}/actuals/import`, `GET /budgets/{id}/variance`, `POST /budgets/{id}/reforecast` |
| **board_packs** | `POST /board-packs`, `GET /board-packs`, `GET /board-packs/{id}`, `POST /board-packs/{id}/generate`, `PATCH /board-packs/{id}`, `GET /board-packs/{id}/export`, `DELETE /board-packs/{id}` |
| **board_pack_schedules** | `POST /board-pack-schedules`, `GET /board-pack-schedules`, `GET /board-pack-schedules/history`, `POST /board-pack-schedules/{id}/run-now`, `POST /board-pack-schedules/history/{hid}/distribute`, `PATCH /board-pack-schedules/{id}`, `DELETE /board-pack-schedules/{id}` |
| **currency** | `GET /currency/settings`, `PUT /currency/settings`, `GET /currency/rates`, `POST /currency/rates`, `DELETE /currency/rates/{from}/{to}/{date}`, `GET /currency/convert` |
| **marketplace** | `GET /marketplace/templates`, `GET /marketplace/templates/{id}`, `POST /marketplace/templates/{id}/use` |
| **benchmark** | `GET /benchmark/opt-in`, `PUT /benchmark/opt-in`, `DELETE /benchmark/opt-in`, `GET /benchmark/summary`, `GET /benchmark/aggregates` |
| **billing** | `GET /billing/plans`, `GET /billing/subscription`, `POST /billing/subscription`, `DELETE /billing/subscription`, `GET /billing/usage`, `POST /billing/webhook` |
| **metrics_summary** | `GET /metrics/summary` (in-memory latency) |

**Metrics:** Prometheus at `GET /metrics` (mounted on app).

---

## 7. Web UI routes

| Path | Purpose |
|------|--------|
| `/` | Landing |
| `/login`, `/signup` | Auth (email/password, Google, Microsoft) |
| `/dashboard` | Dashboard (metrics, links) |
| `/baselines` | List baselines |
| `/baselines/[id]` | Baseline detail |
| `/runs` | List runs |
| `/runs/[id]` | Run results (statements, KPIs) |
| `/runs/[id]/mc` | Monte Carlo results |
| `/runs/[id]/valuation` | Valuation (DCF, multiples) |
| `/drafts` | List drafts |
| `/drafts/[id]` | Draft workspace (chat, assumptions, commit) |
| `/scenarios` | Scenarios list and compare |
| `/notifications` | Notifications list |
| `/inbox` | Task inbox (My Tasks, Team Pool, All) |
| `/inbox/[id]` | Assignment detail |
| `/inbox/[id]/review` | Review workspace (methodology, review form, corrections) |
| `/inbox/feedback` | Change summaries and learning feedback |
| `/assignments/new` | Create assignment wizard |
| `/settings/teams` | Teams list and create |
| `/settings/teams/[teamId]` | Team detail, members, hierarchy |
| `/budgets` | Budgets list |
| `/budgets/new` | Create budget wizard |
| `/budgets/[id]` | Budget workspace (line items, departments) |
| `/budgets/[id]/variance` | Variance dashboard |
| `/budgets/[id]/reforecast` | Reforecast view |
| `/board-packs` | Board packs list |
| `/board-packs/new` | Pack composer |
| `/board-packs/[id]` | Pack preview and download |

---

## 8. Key usage flows

### 8.1 Run a model and view results

1. Ensure a baseline exists (`POST /api/v1/baselines` or create from draft/venture).
2. `POST /api/v1/runs` with `baseline_id`; for Monte Carlo add `mc_enabled`, `num_simulations`, `seed`.
3. For sync run: use response or `GET /api/v1/runs/{id}` for status and artifact IDs; then `GET /api/v1/runs/{id}/statements`, `/kpis`, `/valuation`, `/sensitivity` as needed.
4. For async MC: poll `GET /api/v1/runs/{id}` until status complete; then `GET /api/v1/runs/{id}/mc` for percentiles.
5. In the web app: open `/runs/[id]` for statements/KPIs, `/runs/[id]/mc` for MC, `/runs/[id]/valuation` for valuation.

### 8.2 Draft → commit → baseline

1. Create draft: `POST /api/v1/drafts` (or from venture `POST /api/v1/ventures/{id}/generate-draft`).
2. Optionally chat: `POST /api/v1/drafts/{id}/chat`; accept/reject proposals.
3. When ready: `POST /api/v1/drafts/{id}/commit` (with `acknowledge_warnings` if needed). New baseline is created; draft status → committed.
4. Use the new baseline for runs. In the UI: use Draft workspace then “Commit” (and resolve integrity dialog if any).

### 8.3 Create and approve a budget

1. Create budget: `POST /api/v1/budgets` or `POST /api/v1/budgets/from-template`. Add periods and line items; optionally allocate departments.
2. Import actuals: `POST /api/v1/budgets/{id}/actuals/import`. View variance: `GET /api/v1/budgets/{id}/variance`.
3. Submit: `POST /api/v1/budgets/{id}/submit` — creates workflow instance. Reviewers use assignments inbox and review endpoint; CFO approval transitions budget to active.
4. Optional reforecast: `POST /api/v1/budgets/{id}/reforecast`. Optional NL query: `POST /api/v1/budgets/nl-query`.

### 8.4 Generate and export a board pack

1. Create pack: `POST /api/v1/board-packs` with section config and branding.
2. Generate: `POST /api/v1/board-packs/{pack_id}/generate`.
3. Export: `GET /api/v1/board-packs/{pack_id}/export?format=pdf` (or pptx, html).
4. Optional: create schedule (`POST /api/v1/board-pack-schedules`), run-now or use history and distribute.

### 8.5 Workflow: assign → submit → review

1. Create assignment: `POST /api/v1/assignments` (entity_type, assignee, workflow_template_id, deadline, etc.). Assignee may be resolved from team/reports_to for the template’s stages.
2. Assignee works; claims pool task if needed (`POST /api/v1/assignments/{id}/claim`). Submits: `POST /api/v1/assignments/{id}/submit`.
3. Reviewer opens `/inbox/[id]/review` or uses `POST /api/v1/assignments/{id}/review` (approve / request_changes / reject, corrections, notes). Learning points (AI) stored on change summary.
4. Author sees feedback in `/inbox/feedback` and acknowledges. Notifications sent at each step; deadline reminders via cron.

### 8.6 Connect Xero or QuickBooks

1. User initiates connect (e.g. from settings); frontend redirects to `GET /api/v1/integrations/connections` or provider OAuth URL (use connector config from `GET /api/v1/connectors`).
2. Provider redirects to `GET /api/v1/integrations/connections/callback` with code; API exchanges for tokens and stores connection.
3. Sync: `POST /api/v1/integrations/connections/{id}/sync`. Snapshots: `GET /api/v1/integrations/connections/{id}/snapshots`. Use snapshots for actuals import or run inputs.

### 8.7 Use a marketplace template

1. List: `GET /api/v1/marketplace/templates`. Get one: `GET /api/v1/marketplace/templates/{id}`.
2. Use: `POST /api/v1/marketplace/templates/{id}/use` — creates baseline or budget from template; audit log records use.

### 8.8 Natural language budget query

1. `POST /api/v1/budgets/nl-query` with body e.g. `{ "question": "Which department is over budget?", "budget_id": "..." }`.
2. API assembles facts (dashboard, variance, rankings), calls LLM with schema; returns factual answer and optional source refs.

---

## 9. Summary

Virtual Analyst provides end-to-end financial modeling, drafting, budgeting, board packs, workflows, and integrations. Use this guide for:

- **Setup:** env, migrations, API, web, worker, cron.
- **Auth:** Supabase JWT, optional SAML, headers.
- **Capabilities:** All phases (0–8) and feature areas.
- **API:** Router-level endpoint reference.
- **Web:** Main UI routes.
- **Flows:** Run model, draft→commit, budget lifecycle, board pack, workflow, integrations, marketplace, NL budget query.

For detailed task-level scope and acceptance criteria, see `finmodel spec pack v7/docs/specs/VIRTUAL_ANALYST_BACKLOG.md`. For remaining/done status, see `finmodel spec pack v7/docs/specs/VIRTUAL_ANALYST_BACKLOG_REMAINING.md`.
