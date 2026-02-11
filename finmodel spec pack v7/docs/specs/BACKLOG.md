# Backlog — FinModel v1 (Revised)
**Date:** 2026-02-11
**Version:** 2.0 (Production-Ready)

Work items are grouped by phase. Each item has an ID, description, acceptance criteria (AC), and estimated complexity (S/M/L/XL).

**Complexity Scale:**
- **S (Small):** <1 day
- **M (Medium):** 1-3 days
- **L (Large):** 3-7 days
- **XL (Extra Large):** 7-14 days

---

## Phase 0 — Foundation & Infrastructure

### P0-01: Repository scaffolding (S)
- Initialize Git repository with monorepo structure
- Create directory structure: apps/, shared/, tests/, docs/
- Add .gitignore for Python, Node, env files
- **AC:** Repository structure matches REPO_SCAFFOLDING_LAYOUT.md; `.git` initialized

### P0-02: Python project configuration (M)
- Create `pyproject.toml` with all dependencies
- Configure Ruff, Black, MyPy, Pytest
- Set up virtual environment
- Install dependencies
- **AC:** `pip install -e ".[dev]"` succeeds; linters run successfully

### P0-03: Docker Compose for local dev (M)
- Create `docker-compose.yml` with Postgres, Redis, Supabase
- Configure volume persistence
- Add health checks
- **AC:** `docker-compose up` starts all services; services healthy

### P0-04: Environment configuration (S)
- Create `.env.example` with all required variables
- Document each variable
- Add environment validation at startup
- **AC:** `.env.example` contains all variables; startup fails gracefully if missing required vars

### P0-05: Error handling framework (L)
- Implement error classes (FinModelError, ValidationError, EngineError, etc.)
- Create error response envelope
- Map error codes to HTTP status codes
- Implement FastAPI error handlers
- **AC:** All errors use consistent envelope; HTTP status codes correct per ERROR_HANDLING_SPEC.md

### P0-06: Structured logging setup (M)
- Configure structlog with JSON/console renderers
- Implement correlation ID middleware
- Create context variables (tenant_id, user_id, correlation_id)
- **AC:** Logs output correctly (JSON in prod, pretty in dev); correlation IDs present

### P0-07: Prometheus metrics foundation (M)
- Set up Prometheus client
- Create metrics endpoint (`/metrics`)
- Implement basic metrics: api_requests_total, api_request_duration_seconds
- Add metrics middleware
- **AC:** `/metrics` returns Prometheus format; metrics update on requests

### P0-08: Health check endpoints (S)
- Implement `/api/v1/health/live` (liveness probe)
- Implement `/api/v1/health/ready` (readiness probe with DB/Redis checks)
- **AC:** Liveness returns 200 always; readiness returns 503 if dependencies down

### P0-09: Security middleware (M)
- Implement security headers (CSP, HSTS, X-Frame-Options, etc.)
- Configure rate limiting (slowapi)
- Set up CORS
- **AC:** All responses include security headers; rate limit blocks >100 req/min per IP

### P0-10: Input validation framework (S)
- Set up Pydantic for request validation
- Create base models for common patterns
- **AC:** Invalid requests return 422 with clear validation errors

### P0-11: CI/CD pipeline (L)
- Create GitHub Actions workflow
- Add jobs: lint, type-check, test, build
- Configure test matrix (Python 3.12)
- Add code coverage reporting
- Add security scanning (Safety)
- **AC:** CI runs on PR; all checks pass; coverage report generated

### P0-12: Pre-commit hooks (S)
- Create `.pre-commit-config.yaml`
- Add hooks: Ruff, Black, trailing whitespace, large files
- **AC:** `pre-commit install` works; hooks run on commit

### P0-13: FastAPI application skeleton (M)
- Create main.py with FastAPI app
- Configure middleware (logging, security, metrics)
- Add root endpoint (`/`)
- Mount metrics app
- **AC:** `uvicorn app.main:app` starts; `/` returns app info; middleware functional

### P0-14: README and setup documentation (M)
- Write README.md with setup instructions
- Document environment variables
- Add troubleshooting section
- **AC:** New developer can set up environment in <30 min following README

---

## Phase 1 — Core Model Engine

### P1-01: Database migrations + Supabase setup (M)
- Apply 0001_init.sql and 0002_functions_and_rls.sql
- Configure Supabase project: enable Auth, Storage, Realtime
- Set up .env.example with all required env vars
- **AC:** `psql` can query all tables; Supabase dashboard shows project active; RLS policies enabled

### P1-02: Pydantic models for model_config_v1 (L)
- Create `shared/fm_shared/model/schemas.py`
- Full Pydantic v2 model matching ARTIFACT_MODEL_CONFIG_SCHEMA.json
- Nested models for: metadata, assumptions, driver_blueprint, distributions, scenarios, integrity
- Validation: all required fields, enum constraints, cross-field checks
- **AC:** Load example model_config JSON → Pydantic model → re-serialize → matches original; Invalid JSON rejected with clear error

### P1-03: Artifact storage service (M)
- Create `shared/fm_shared/storage/artifact_store.py`
- Interface: `save(tenant_id, artifact_type, artifact_id, data) → path`
- Interface: `load(tenant_id, artifact_type, artifact_id) → data`
- Interface: `list(tenant_id, artifact_type) → [artifact_id]`
- Backend: Supabase Storage (bucket per tenant)
- Validate against JSON Schema on save
- Add compression for large artifacts (>100KB)
- **AC:** Save model_config → load → identical; save invalid config → rejected; large artifacts compressed

### P1-04: Calculation graph builder (L)
- Create `shared/fm_shared/model/graph.py`
- Parse driver_blueprint from model_config_v1
- Build directed acyclic graph (DAG) of nodes
- Topological sort for execution order
- Detect cycles → raise error with cycle path
- **AC:** Manufacturing template blueprint → valid DAG; circular dependency → clear error with cycle path

### P1-05: Expression evaluator (M)
- Create safe expression evaluator (asteval or custom)
- Support: arithmetic (+, -, *, /), functions (min, max, clamp, if_else)
- Parse expressions into AST at graph build time
- Evaluate AST with variable substitution at runtime
- **AC:** All test expressions evaluate correctly; unsafe operations rejected

### P1-06: Time-series engine (XL)
- Create `shared/fm_shared/model/engine.py`
- Input: model_config_v1 + scenario overrides (optional)
- Output: time-series dict keyed by node_id
- Execute formulas in topological order
- Handle time-varying drivers (ramp schedules, seasonal patterns, constant)
- Support monthly and annual resolution
- Add complexity limits (max nodes, formulas, horizon)
- Add execution timeout (30s default)
- Log performance metrics (execution time by phase)
- **AC:** Manufacturing template with known inputs → revenue = capacity × utilization × yield × price per month; execution <500ms for 12 months

### P1-07: Three-statement generator (XL)
- Create `shared/fm_shared/model/statements.py`
- Input: engine output time-series + model_config assumptions
- Produce Income Statement: Revenue, COGS, Gross Profit, EBITDA, EBIT, Net Income
- Produce Balance Sheet: Cash (plug), AR, Inventory, PPE, AP, Debt, Equity
- Produce Cash Flow Statement: Operating, Investing, Financing
- Working capital calculations
- Balance sheet must balance (Assets = L + E)
- Cash flow reconciliation (CF ending cash = BS cash)
- **AC:** BS balances every month; CF beginning cash + total CF = ending cash = BS cash; known inputs → expected outputs (golden file test)

### P1-08: KPI calculator (M)
- Create `shared/fm_shared/model/kpis.py`
- From statements, compute: gross margin %, EBITDA margin %, net margin %, current ratio, debt/equity, DSCR, ROE, revenue growth %, FCF, cash conversion cycle
- **AC:** KPIs computed correctly from known statement values (golden file test)

### P1-09: FastAPI application scaffold (M)
- Extend main.py with routers
- Add database connection setup
- Add Redis connection setup
- Configure dependency injection
- **AC:** App starts with DB and Redis connections; routers mounted

### P1-10: Baseline API routes (M)
- `POST /api/v1/baselines` — create from model_config JSON body
- `GET /api/v1/baselines` — list for current tenant (paginated, 50 per page)
- `GET /api/v1/baselines/{baseline_id}` — retrieve
- `PATCH /api/v1/baselines/{baseline_id}` — update status (active/archived)
- Enforce: one active baseline per tenant (per migration constraint)
- **AC:** CRUD operations work; pagination works; second active baseline → 409 conflict

### P1-11: Run API routes (L)
- `POST /api/v1/runs` — create run (baseline_id, scenario_id optional)
- `GET /api/v1/runs` — list runs (paginated)
- `GET /api/v1/runs/{run_id}` — status + metadata
- `GET /api/v1/runs/{run_id}/statements` — IS/BS/CF
- `GET /api/v1/runs/{run_id}/kpis` — KPI outputs
- Run execution: load baseline → apply scenario overrides → engine → statements → KPIs → store artifacts
- Status flow: queued → running → succeeded | failed
- **AC:** POST run → status=queued → poll → status=succeeded → GET statements returns data

### P1-12: Database indexing (S)
- Add indexes per PERFORMANCE_SPEC.md
- Indexes on: tenant_id, baseline_id, run_id, created_at, status
- Composite indexes for common queries
- **AC:** All indexes created; query performance <50ms for common queries

### P1-13: Connection pooling (S)
- Configure SQLAlchemy connection pool (20 connections)
- Add pool monitoring metrics
- **AC:** Pool size = 20; metrics show active connections

### P1-14: Query optimization (M)
- Identify and fix N+1 queries
- Use selectinload for relationships
- Add pagination to all list endpoints
- **AC:** No N+1 queries; all list endpoints paginated

### P1-15: Performance monitoring (M)
- Add engine execution metrics
- Add database query metrics
- Create Grafana dashboard (or similar)
- **AC:** Dashboard shows API latency, engine execution time, DB query duration

### P1-16: Audit logging (initial) (M)
- Implement audit log table (append-only)
- Log: baseline.created, baseline.accessed, baseline.archived, run.created, run.accessed
- Add audit event creation function
- **AC:** All events logged; audit log table is append-only (no updates/deletes)

### P1-17: Next.js web app scaffold (M)
- Create `apps/web/` with Next.js 14 App Router
- Supabase Auth integration (email/password login)
- Layout: sidebar nav + main content area
- Tailwind CSS + shadcn/ui components
- **AC:** Login page → authenticate → redirect to dashboard

### P1-18: Baseline list + detail UI (M)
- Dashboard page showing baseline list (with search, filter, pagination)
- Baseline detail page (view model_config)
- Error handling (toast notifications)
- Loading states
- **AC:** List renders with pagination; detail page shows model_config; errors show toast

### P1-19: Run results UI (M)
- Run results page showing IS/BS/CF tables
- Tabs: Statements, KPIs, Charts
- Tables: months as columns, line items as rows, formatted numbers
- Conditional formatting (negative values in red)
- **AC:** Tables render correctly with formatted currency values; tabs work

### P1-20: Test suite - Unit tests (L)
- test_graph_builder.py (DAG, cycle detection, topo sort)
- test_expression_evaluator.py (arithmetic, functions)
- test_time_series.py (constant, ramp, seasonal)
- test_income_statement.py, test_balance_sheet.py, test_cash_flow.py
- test_kpis.py
- **AC:** All unit tests pass; coverage >70%

### P1-21: Test suite - Integration tests (L)
- test_baseline_crud.py
- test_run_lifecycle.py
- test_rls_isolation.py
- test_artifact_storage.py
- **AC:** All integration tests pass; RLS prevents cross-tenant access

### P1-22: Test suite - Performance tests (M)
- test_engine_performance.py (12mo <500ms, 60mo <1.5s)
- test_api_latency.py (endpoints <300ms P95)
- **AC:** Performance tests pass; SLAs met

### P1-23: Golden file tests (M)
- Create golden files for manufacturing template
- test_golden_statements.py
- test_golden_kpis.py
- **AC:** Engine output matches golden files (exact match or within tolerance)

---

## Phase 2 — Draft Layer + LLM Integration

### P2-01: Background job queue setup (M)
- Install and configure Celery with Redis backend
- Create worker process
- Configure task routing
- Add job status tracking
- Implement retry with exponential backoff
- **AC:** Celery worker starts; tasks execute; retries work; status trackable

### P2-02: Dead letter queue (S)
- Implement DLQ for failed jobs
- Background processor for DLQ (retry with backoff)
- **AC:** Failed jobs go to DLQ; DLQ processor retries

### P2-03: Draft session CRUD (M)
- `POST /api/v1/drafts` — create (optionally from existing baseline)
- `GET /api/v1/drafts/{id}` — retrieve with current workspace state
- `PATCH /api/v1/drafts/{id}` — update status
- `DELETE /api/v1/drafts/{id}` — abandon
- State machine per DRAFT_COMMIT_SPEC.md
- Auto-save workspace every 30 seconds
- **AC:** Create → edit → ready_to_commit → commit flow works; invalid transitions rejected; auto-save works

### P2-04: LLM provider abstraction (L)
- Create `apps/api/app/services/llm/provider.py`
- Abstract base: `complete(messages, schema, task_label) → structured_output`
- Implementations: AnthropicProvider, OpenAIProvider
- JSON mode / structured output enforcement
- Retry with exponential backoff (3 attempts)
- Timeout (30s)
- **AC:** Both providers return valid structured JSON; provider failure → retry → fallback

### P2-05: Circuit breaker for LLM (M)
- Implement circuit breaker pattern
- States: CLOSED, OPEN, HALF_OPEN
- Threshold: 5 consecutive failures → OPEN
- Recovery timeout: 60s
- **AC:** After 5 failures, circuit opens; blocks calls for 60s; test call after timeout

### P2-06: LLM routing policy engine (M)
- Create `apps/api/app/services/llm/router.py`
- Load llm_routing_policy_v1 artifact
- Match task_label → select provider + model
- Respect plan limits (check usage_meter before call)
- Fallback chain if primary provider fails
- **AC:** task_label="draft_assumptions" routes to configured provider; over-limit → 429 error; fallback works

### P2-07: LLM call logging + metering (M)
- After every LLM call, write llm_call_log_v1 to storage
- Aggregate into usage_meter_v1: tokens by provider, cost estimates, call counts
- Correlation: link call to draft_session_id + user_id
- **AC:** After 3 LLM calls, usage_meter shows correct totals; call_log has all 3 entries

### P2-08: Analyst chat endpoint (L)
- `POST /api/v1/drafts/{id}/chat`
- Body: `{ "message": "...", "context": { ... } }`
- System prompt includes: venture template context, current assumptions, model structure
- LLM responds with structured proposals
- Validate proposals against model_config structure
- Store proposals in draft workspace (not committed)
- Background processing for heavy calls (queue as Celery task)
- **AC:** "Set utilization to 75%" → proposal with path, value, evidence; heavy calls execute async

### P2-09: LLM quality metrics (M)
- Track proposal acceptance rate (% accepted vs rejected)
- Track user edit distance (how much users modify)
- Track confidence accuracy (high confidence → higher acceptance)
- Feedback mechanism (thumbs up/down)
- Store metrics in database
- **AC:** Metrics update on proposal accept/reject/edit; feedback recorded

### P2-10: Commit pipeline (L)
- `POST /api/v1/drafts/{id}/commit`
- Steps per DRAFT_COMMIT_SPEC.md:
  1. Validate draft workspace against model_config_v1 schema
  2. Run integrity checks (completeness, consistency, evidence coverage)
  3. Compile to frozen model_config_v1 artifact
  4. Create new baseline (or new version of existing)
  5. Update draft status to committed
- Return integrity check results in response
- Audit log: draft.committed
- **AC:** Valid draft → committed → new baseline exists; incomplete draft → integrity warnings returned

### P2-11: Changeset support (M)
- `POST /api/v1/changesets` — create against baseline
- `GET /api/v1/changesets/{id}` — retrieve with diff
- `POST /api/v1/changesets/{id}/test` — dry-run
- `POST /api/v1/changesets/{id}/merge` — create new baseline version
- **AC:** Create changeset changing price 100→120 → test shows revenue increase → merge creates new version

### P2-12: Venture template wizard API (M)
- `POST /api/v1/ventures` — create venture, select template
- `POST /api/v1/ventures/{id}/answers` — submit question_plan answers
- `POST /api/v1/ventures/{id}/generate-draft` — LLM generates initial assumptions
- **AC:** Select manufacturing_discrete → answer questions → generated draft has revenue_streams, capacity, costs populated

### P2-13: Draft workspace UI (L)
- Chat panel (left): message history, send messages, see proposals
- Assumption editor (right): tree view of model_config, edit values, see evidence
- Accept/reject individual LLM proposals
- Integrity check indicator (green/amber/red)
- Commit button with confirmation dialog
- **AC:** Full draft → chat → review → commit flow in UI

### P2-14: Changeset UI (M)
- Diff viewer (before/after comparison)
- Dry-run results preview
- Merge confirmation
- **AC:** Changeset diff shows changes; dry-run shows impact; merge works

### P2-15: Activity log (M)
- Track all changes to draft (who, what, when)
- Display in UI (timeline view)
- **AC:** Activity log shows user, field changed, old/new value, timestamp

### P2-16: Notifications service - Email (M)
- Configure SendGrid or AWS SES
- Create email templates (draft_ready, run_complete, limit_exceeded)
- Send email on key events
- **AC:** Email sent when draft ready, run complete; template renders correctly

### P2-17: Notifications service - In-app (M)
- Create notifications table
- `GET /api/v1/notifications` — list unread notifications
- `PATCH /api/v1/notifications/{id}` — mark as read
- Bell icon with count in UI
- **AC:** Notification created → appears in list → bell icon shows count → mark read works

### P2-18: Test suite - Phase 2 (L)
- test_commit_pipeline.py
- test_llm_router.py
- test_draft_chat.py (with cassettes)
- test_draft_commit_flow.py
- test_auth_roles.py
- **AC:** All Phase 2 tests pass

---

## Phase 3 — Monte Carlo + Scenarios + Valuation

### P3-01: Distribution engine (M)
- Create `shared/fm_shared/analysis/distributions.py`
- Supported families: triangular, normal, lognormal, uniform, PERT
- Interface: `sample(distribution_config, n, seed) → np.array`
- Seeded numpy RNG for reproducibility
- **AC:** triangular(min=0.5, mode=0.7, max=0.9, n=10000, seed=42) → same result every time

### P3-02: Monte Carlo runner (L)
- Create `shared/fm_shared/analysis/monte_carlo.py`
- Input: model_config + distributions + num_simulations + seed
- For each simulation: sample all stochastic drivers → run engine → collect outputs
- Output structure: percentiles (P5, P10, P25, P50, P75, P90, P95) for each metric per period
- Vectorized computation (NumPy)
- **AC:** 1000 sims, seed=42 → deterministic; P50 within 5% of base case

### P3-03: Parallel MC execution (M)
- Use ProcessPoolExecutor for parallel simulation
- Pre-allocate result arrays
- **AC:** 1000 sims complete in <30s; 10,000 sims in <5 min

### P3-04: Async MC execution (M)
- MC runs >1,000 sims execute as Celery background job
- Progress reporting (update run status)
- Timeout: 10 minutes
- **AC:** POST run with 10k sims → status=queued → background job executes → status=succeeded

### P3-05: Scenario management (M)
- `POST /api/v1/scenarios` — create named scenario with overrides
- `GET /api/v1/scenarios` — list scenarios for baseline
- `PATCH /api/v1/scenarios/{id}` — update
- `DELETE /api/v1/scenarios/{id}` — delete
- Overrides: `[{ "ref": "drv:utilization", "field": "multiplier", "value": 0.85 }]`
- Apply at runtime: merge overrides into model_config before engine execution
- **AC:** Create "Downside" scenario → run → different results from base case

### P3-06: Valuation module (L)
- DCF: sum of discounted FCFs + terminal value (perpetuity growth or exit multiple)
- Inputs: WACC, terminal_growth_rate, terminal_multiple, projection_years
- If MC enabled: compute EV at each percentile
- Multiples valuation: EV/EBITDA, EV/Revenue, P/E with user-supplied comparables
- Output: `{ "dcf": { "enterprise_value": ..., "equity_value": ..., "per_share": ... }, "multiples": { ... } }`
- **AC:** Known FCF stream + WACC + terminal growth → correct EV (hand-calculable)

### P3-07: Baseline comparison (M)
- `POST /api/v1/baselines/compare` — compare two baselines
- Show differences (assumptions, results)
- Variance analysis
- **AC:** Compare bl_001/v1 vs bl_001/v2 → diff shows changed assumptions and impact

### P3-08: Sensitivity analysis (L)
- `POST /api/v1/runs/{id}/sensitivity` — automated sensitivity analysis
- One-at-a-time driver variation (±10%, ±20%)
- Tornado chart inputs (rank drivers by impact on EV or FCF)
- **AC:** Sensitivity run identifies top 5 impact drivers; tornado inputs correct

### P3-09: Waterfall charts component (M)
- Create React component for waterfall charts
- Support: revenue bridge, EBITDA bridge, cash flow waterfall
- **AC:** Waterfall chart renders with correct bars and labels

### P3-10: Extended run API (M)
- Extend `POST /api/v1/runs` with: mc_enabled, num_simulations, seed, scenario_id, valuation_config
- `GET /api/v1/runs/{id}/mc` — MC percentile outputs
- `GET /api/v1/runs/{id}/valuation` — valuation results
- `GET /api/v1/runs/{id}/sensitivity` — sensitivity results
- **AC:** POST run with mc_enabled=true → GET mc returns percentiles

### P3-11: MC + valuation UI (L)
- Fan chart: revenue/EBITDA/FCF over time with P10/P50/P90 bands
- Tornado chart: horizontal bars showing sensitivity per driver
- Distribution histogram: FCF or EV distribution across simulations
- Scenario comparison table: base vs scenarios side-by-side
- Valuation summary card: EV range, implied multiples
- Real-time MC progress (WebSocket or polling)
- **AC:** Charts render with correct data; scenario toggle updates comparison table; progress shows during MC

### P3-12: Test suite - Phase 3 (L)
- test_distributions.py
- test_monte_carlo.py
- test_valuation.py
- test_scenarios.py
- test_mc_run.py (integration)
- **AC:** All Phase 3 tests pass

---

## Phase 4 — ERP Integrations + Billing + Compliance

### P4-01: Integration connection framework (L)
- Connection model: provider, OAuth2 credentials (encrypted), status, last_sync
- OAuth2 flow: redirect → callback → store tokens → refresh
- Provider adapter interface: `connect()`, `discover()`, `sync()`, `disconnect()`
- Token encryption/decryption
- **AC:** OAuth2 flow completes for Xero sandbox; tokens stored encrypted

### P4-02: Xero adapter (L)
- Implement XeroAdapter
- Discovery: chart of accounts, tracked categories, bank accounts, periods available
- Sync: trial balance, P&L, balance sheet for specified periods
- Map Xero account types → canonical account types
- Store as canonical_sync_snapshot_v1
- **AC:** Sync Xero demo company → canonical snapshot with revenue, expenses, assets, liabilities

### P4-03: ERP discovery endpoint (M)
- `POST /api/v1/integrations/discover` — probe connected ERP
- Store as erp_discovery_session_v1
- **AC:** Discovery returns chart of accounts, periods available

### P4-04: Sync scheduling (M)
- Configurable sync interval (daily, weekly, manual)
- Background job (Celery) for scheduled syncs
- **AC:** Scheduled sync runs at configured interval; manual sync works

### P4-05: Billing plan + subscription management (M)
- Seed plans: Starter, Professional, Enterprise (per PRICING_AND_GTM.md)
- Subscription CRUD: create, update tier, cancel
- Plan limits stored in billing_plan_v1
- **AC:** Create subscription on Starter plan; upgrade to Pro; limits updated

### P4-06: Usage metering service (M)
- Aggregate from: llm_call_log (tokens), integration_sync_run (sync events), runs (MC sims)
- Period: calendar month
- Check limits before: LLM calls, sync triggers, MC runs
- Produce usage_meter_v1 per period
- **AC:** After 10 LLM calls + 2 syncs + 1 MC run → usage_meter reflects all; limit check works

### P4-07: Stripe integration (M)
- Create Stripe customer on tenant creation
- Create subscription aligned to plan
- Webhook handler: invoice.paid, subscription.updated, subscription.deleted
- Usage-based billing: report metered usage to Stripe
- Invoice generation
- **AC:** Create subscription → Stripe shows active; report usage → Stripe invoice reflects it; webhook updates subscription status

### P4-08: Audit logging - Complete implementation (L)
- All event types per AUDIT_COMPLIANCE_SPEC.md
- Immutable audit log table (enforce with RLS + trigger)
- S3 backup for compliance (daily job)
- Checksum for integrity
- **AC:** All event types logged; audit log is append-only; S3 backup works

### P4-09: Audit log viewer UI (M)
- Admin-only page
- Search and filter (user, event type, date range, resource)
- Export (CSV, JSON)
- **AC:** Audit log searchable; export works; non-admin cannot access

### P4-10: Compliance reporting (M)
- `GET /api/v1/compliance/report` — generate quarterly report
- Report includes: user activity, data activity, security events, GDPR requests
- **AC:** Report generates correctly with all sections

### P4-11: GDPR endpoints (M)
- `GET /api/v1/gdpr/data-export` — export all user data
- `DELETE /api/v1/gdpr/delete-user` — delete user data, anonymize audit logs
- Consent management (track consent for LLM processing, analytics)
- **AC:** Data export returns all user data; deletion works and anonymizes audit logs; consent tracked

### P4-12: Notification preferences (S)
- User preferences for notification types (email, in-app)
- `GET/PATCH /api/v1/notifications/preferences`
- **AC:** User can enable/disable notification types; preferences persist

### P4-13: CSV import (M)
- `POST /api/v1/import/csv` — upload CSV with assumptions
- Mapping wizard (map CSV columns to model fields)
- Validation and preview
- Create draft from CSV
- **AC:** Upload CSV → map columns → preview → create draft

### P4-14: Covenant monitoring (M)
- Define covenant thresholds (debt/equity < 2.5, DSCR > 1.2, etc.)
- Automatic monitoring on each run
- Alert when covenant breached (notification + flag on run)
- Covenant dashboard
- **AC:** Covenant breach detected → alert sent → dashboard shows breaches

### P4-15: Integration + billing UI (M)
- Connection wizard: select provider → OAuth → configure sync schedule
- Sync status page: last sync, next sync, error log
- Billing page: current plan, usage this period, upgrade/downgrade buttons
- Invoice history
- **AC:** Full flow: connect → sync → view results → see usage → view invoices

### P4-16: Webhook support (M)
- `POST /api/v1/webhooks` — create webhook (URL + events)
- Webhook delivery (POST to URL on event)
- Retry failed deliveries
- Webhook logs
- **AC:** Webhook created → event triggers → POST sent to URL → delivery logged

### P4-17: Migration 0004 (M)
- Write and apply 0004_integrations_billing_llm.sql
- Tables: integration_connections, integration_sync_runs, canonical_sync_snapshots, erp_discovery_sessions, billing_plans, billing_subscriptions, usage_meters, llm_call_logs, llm_routing_policies
- RLS policies on all tables
- **AC:** All tables created; RLS policies enforced

### P4-18: Test suite - Phase 4 (L)
- test_integration_connection.py
- test_sync_run.py
- test_billing.py
- test_rls_isolation.py
- test_audit_log.py
- test_gdpr.py
- **AC:** All Phase 4 tests pass

---

## Phase 5 — Export, Memos & Collaboration

### P5-01: Excel export (static) (M)
- `GET /api/v1/runs/{id}/export/excel` — export run to Excel
- Sheets: IS, BS, CF
- Formatted with headers, currency formatting
- Export multiple scenarios to single workbook (multiple sheets)
- **AC:** Export works; Excel file contains IS/BS/CF with correct formatting

### P5-02: Excel connection API (M)
- `POST/GET /api/v1/excel/connections` — create/manage bindings
- Binding: map named range to model path (assumption or output)
- **AC:** Connection created with bindings; CRUD works

### P5-03: Excel pull endpoint (M)
- `POST /api/v1/excel/connections/{id}/pull` — server → Excel
- Gather current values for all bindings
- Return JSON with values
- **AC:** Pull returns correct values for bindings

### P5-04: Excel push endpoint (M)
- `POST /api/v1/excel/connections/{id}/push` — Excel → server
- Receive changed values, validate
- Create changeset or draft_override (per connection config)
- Role-based push permissions (can_push_roles)
- Version check (conflict detection)
- **AC:** Push creates changeset; investor role rejected; version conflict detected

### P5-05: WebSocket for real-time notifications (M)
- WebSocket endpoint for Excel refresh notifications
- Notify connected clients when data changes
- **AC:** WebSocket connection works; notification sent on data change

### P5-06: Office.js add-in (XL)
- Manifest.xml for sideloading
- Taskpane: auth, connection picker, binding status
- Pull: on button click, fetch from API, write to named ranges
- Push: on button click, read named ranges, diff, POST changes
- Push validation: check data_type, min/max, allowed_values
- Role check: if user role not in can_push_roles, disable push UI
- Conflict handling: if version mismatch, show error
- **AC:** Open Excel → sign in → pull populates cells → edit cell → push → changeset appears in web UI

### P5-07: Memo pack generator (L)
- Template engine with section definitions per memo_type
- Templates: investment_committee, credit_memo, valuation_note
- Content block renderers: markdown→HTML, table_ref→HTML table, chart_ref→SVG embed
- Data binding: pull values from run artifacts, assumptions, MC results
- HTML output (primary)
- PDF output via weasyprint
- **AC:** Generate IC memo from run → HTML has executive summary, financial tables, risk section; PDF renders correctly

### P5-08: Memo API routes (M)
- `POST /api/v1/memos` — generate memo (run_id, memo_type)
- `GET /api/v1/memos` — list memos for tenant
- `GET /api/v1/memos/{id}` — metadata
- `GET /api/v1/memos/{id}/download?format=html|pdf`
- **AC:** Generate → list shows it → download in both formats

### P5-09: PDF upload + OCR (L)
- `POST /api/v1/upload/pdf` — upload financial statements
- OCR extraction (Tesseract or AWS Textract)
- Map extracted data to model fields (AI-assisted mapping)
- Create draft from PDF data
- **AC:** Upload PDF → OCR extracts data → mapping wizard → draft created

### P5-10: Document management (M)
- `POST /api/v1/documents` — attach document to assumption
- Store in Supabase Storage
- `GET /api/v1/documents` — list documents
- `DELETE /api/v1/documents/{id}` — delete document
- File viewer in UI
- **AC:** Upload document → attach to assumption → view in UI → delete works

### P5-11: Comments system (M)
- `POST /api/v1/comments` — add comment to assumption
- `GET /api/v1/comments` — list comments for draft/assumption
- `DELETE /api/v1/comments/{id}` — delete comment
- @mentions (notify mentioned user)
- Threaded comments
- **AC:** Add comment → appears in UI → @mention notifies user → threaded replies work

### P5-12: Activity feed (M)
- Dashboard widget showing recent activity
- Filter by user, resource type, timeframe
- Real-time updates (via polling or WebSocket)
- **AC:** Activity feed shows recent changes; updates in real-time

### P5-13: Real-time presence (optional) (M)
- Show who's currently viewing a draft
- Avatar indicators
- **AC:** Multiple users viewing draft → avatars show

### P5-14: Excel + memo UI (L)
- Excel connections page: list, create, manage bindings
- Memo generation wizard: select run → choose memo type → preview → generate
- Memo viewer: HTML render in iframe
- Download buttons for PDF
- PDF upload wizard
- Document library page
- Comments UI (threaded, @mentions)
- Activity feed widget
- **AC:** Full memo generation flow in UI; Excel connections work; PDF upload works; comments work

### P5-15: Migration 0005 (M)
- Write and apply 0005_excel_and_memos.sql
- Tables: excel_connections, excel_sync_events, memo_packs, documents, comments
- RLS policies
- **AC:** All tables created; RLS enforced

### P5-16: Test suite - Phase 5 (L)
- test_excel_connection.py
- test_excel_push_pull.py
- test_memo_generation.py
- test_pdf_upload.py
- test_comments.py
- **AC:** All Phase 5 tests pass

---

## Cross-Cutting / Post-Phase Work

### Security Hardening (ongoing)

#### SEC-01: Security testing suite (L)
- test_sql_injection.py
- test_xss_prevention.py
- test_rls_bypass_attempts.py
- test_rate_limiting.py
- test_auth_token_expiry.py
- **AC:** All security tests pass

#### SEC-02: Dependency scanning automation (M)
- Configure Dependabot
- Add Safety to CI pipeline
- Container image scanning (Trivy)
- **AC:** Dependencies scanned on PR; alerts on vulnerabilities

#### SEC-03: Penetration testing (external) (XL)
- Contract penetration testing firm
- Scope: web app, API, auth, data access
- Remediate findings
- **AC:** Pen test report received; all high/critical findings remediated

### Load & Performance Testing

#### PERF-01: Load testing suite (L)
- Locust tests for API endpoints
- Simulate 100+ concurrent users
- Test: concurrent runs, MC simulations, LLM calls
- **AC:** Load tests pass; system handles 100 users; P95 latency meets SLAs

#### PERF-02: Performance regression testing (M)
- Add performance tests to CI
- Compare against baseline
- Fail if regression >20%
- **AC:** CI fails on performance regression

### Documentation

#### DOC-01: API documentation (M)
- Generate OpenAPI spec from FastAPI
- Swagger UI at `/docs`
- Include request/response examples
- **AC:** API docs complete and accurate

#### DOC-02: User guide (L)
- End-user documentation (how to create models, interpret results)
- Screenshots and tutorials
- **AC:** User guide published

#### DOC-03: Developer guide (M)
- How to extend templates, add formula functions
- Architecture overview
- **AC:** Developer guide published

#### DOC-04: Operational runbooks (M)
- Common issues and resolution steps
- Escalation procedures
- **AC:** Runbooks for top 10 issues

### Deployment

#### DEPLOY-01: Staging environment setup (M)
- Provision staging infrastructure
- Configure CI/CD for staging deployment
- **AC:** Staging environment operational; auto-deploys from `main`

#### DEPLOY-02: Production environment setup (L)
- Provision production infrastructure
- Configure monitoring, alerting
- Set up backups
- **AC:** Production environment ready; backups tested

#### DEPLOY-03: DR testing (M)
- Test database restore from backup
- Test failover procedures
- **AC:** DR drill completed; documented recovery time

---

## Summary Statistics

**Total Work Items:** 118 items (P0-P5 + cross-cutting)

**By Phase:**
- Phase 0: 14 items
- Phase 1: 23 items
- Phase 2: 18 items
- Phase 3: 12 items
- Phase 4: 18 items
- Phase 5: 16 items
- Cross-cutting: 17 items

**By Complexity:**
- Small (S): 15 items (~15 days)
- Medium (M): 58 items (~116 days)
- Large (L): 37 items (~185 days)
- Extra Large (XL): 8 items (~80 days)

**Total Effort Estimate:** ~396 developer-days (with 3-4 developers = ~20-26 weeks)

**With 20% buffer:** ~475 days → **~24-30 weeks (~6-7 months)**
