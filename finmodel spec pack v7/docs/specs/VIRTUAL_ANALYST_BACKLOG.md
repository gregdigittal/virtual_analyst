# Backlog — Virtual Analyst v1
Date: 2026-02-11
Version: 1.0

This backlog is the execution overlay for Virtual Analyst v1, derived from the FinModel v7 spec pack. For detailed schemas and acceptance criteria, reference `docs/specs/BACKLOG.md` and the phase prompts in `docs/specs/PROMPTS/`.

## Status (2026-02-11)
- **Phase 1 core shipped:** Model layer, baseline/run APIs, artifact store, audit, web UI. Unit tests (24), integration tests (4, gated by INTEGRATION_TESTS=1 + DB), performance tests (engine 12mo P95 &lt;500ms, full pipeline &lt;1s), golden file tests (manufacturing statements/KPIs). Integration suite: baseline/run lifecycle, tenant isolation (RLS). Golden: manufacturing_base_statements.json, manufacturing_base_kpis.json.
- **Next:** Phase 2 (VA-P2-01 etc.) or CI: set INTEGRATION_TESTS=1 and DATABASE_URL to run integration tests.
- **Context save:** `docs/specs/CONTEXT_SAVE_2026-02-11.md`

## Complexity Scale
- S: <1 day
- M: 1-3 days
- L: 3-7 days
- XL: 7-14 days

---

## Phase 0 — Foundation & Infrastructure (Sprint 0-1)

### VA-P0-01: Repository scaffolding (S)
- Create monorepo structure and initialize Git
- AC: Structure matches `REPO_SCAFFOLDING_LAYOUT.md`

### VA-P0-02: Python project configuration (M)
- Create `pyproject.toml` and dev tooling
- AC: `pip install -e ".[dev]"` succeeds; lint/type/test run

### VA-P0-03: Docker Compose for local dev (M)
- Postgres, Redis, Supabase with health checks
- AC: `docker-compose up` starts all services healthy

### VA-P0-04: Environment configuration (S)
- `.env.example` and startup validation
- AC: Missing required env vars fail with clear errors

### VA-P0-05: Error handling framework (L)
- Error classes, envelope, FastAPI handlers
- AC: Consistent error envelope and status codes per spec

### VA-P0-06: Structured logging setup (M)
- Structlog config, correlation IDs
- AC: JSON logs in prod, readable logs in dev

### VA-P0-07: Prometheus metrics foundation (M)
- `/metrics` with request and latency metrics
- AC: Metrics endpoint returns valid Prometheus format

### VA-P0-08: Health check endpoints (S)
- `/api/v1/health/live` and `/ready`
- AC: Readiness fails when DB/Redis unavailable

### VA-P0-09: Security middleware (M)
- Security headers, rate limiting, CORS
- AC: Rate limit enforced; headers present

### VA-P0-10: Input validation framework (S)
- Base Pydantic models and validation
- AC: Invalid requests return 422 with details

### VA-P0-11: CI/CD pipeline (L)
- GitHub Actions for lint/type/test/build
- AC: CI runs on PR and passes

### VA-P0-12: Pre-commit hooks (S)
- Ruff, Black, whitespace checks
- AC: `pre-commit install` works and hooks run

### VA-P0-13: FastAPI app skeleton (M)
- App init, middleware, health, metrics
- AC: `uvicorn` starts; endpoints respond

### VA-P0-14: README and setup docs (M)
- Setup, env vars, troubleshooting
- AC: New developer setup <30 minutes

---

## Phase 1 — Core Deterministic Engine (Sprint 2-4)

### VA-P1-01: DB migrations + Supabase setup (M)
- Apply 0001/0002 migrations and enable Auth/Storage/RLS
- AC: Tables present; RLS policies enabled; env configured

### VA-P1-02: Pydantic models for model_config_v1 (L) — DONE
- Full schema validation with cross-field checks
- AC: Example JSON round-trips; invalid JSON rejected

### VA-P1-03: Artifact storage service (M) — DONE
- Supabase Storage with schema validation and compression
- AC: Save/load artifacts round-trip; invalid rejected

### VA-P1-04: Calculation graph builder (L) — DONE
- DAG build, topo sort, cycle detection
- AC: Manufacturing blueprint builds; cycles error with path

### VA-P1-05: Expression evaluator (M) — DONE
- Safe AST evaluation with limited functions
- AC: Test expressions evaluate correctly; unsafe ops rejected

### VA-P1-06: Time-series engine (XL) — DONE
- Execute formulas over horizon with limits and metrics
- AC: 12-month run <500ms; deterministic outputs

### VA-P1-07: Three-statement generator (XL) — DONE
- IS/BS/CF with reconciliation and balancing
- AC: BS balances monthly; CF reconciles to cash

### VA-P1-08: KPI calculator (M) — DONE
- Margins, ratios, working capital metrics
- AC: KPIs match expected values in tests

### VA-P1-09: FastAPI application scaffold (M) — DONE
- Routers, DB/Redis connections, DI
- AC: App boots and routes mounted correctly

### VA-P1-10: Baseline API routes (M) — DONE
- CRUD with pagination and versioning rules
- AC: CRUD works; one active baseline enforced

### VA-P1-11: Run API routes (L) — DONE
- Run lifecycle with status transitions and artifacts
- AC: Runs complete and results retrievable

### VA-P1-12: Database indexing (S) — DONE
- Indexes per performance spec
- AC: Query performance meets <50ms P95 target
- Note: 0007_indexes_performance.sql — idx_model_baselines_tenant_created, idx_runs_tenant_created.

### VA-P1-13: Connection pooling (S) — DONE
- Pool sizing and metrics
- AC: Pool configured to 20 connections
- Note: asyncpg pool in apps/api/app/db/connection.py (init_pool/close_pool, lifespan); DB_POOL_MIN_SIZE, DB_POOL_MAX_SIZE=20.

### VA-P1-14: Query optimization (M) — DONE
- Eliminate N+1s, add pagination
- AC: No N+1 in common queries
- Note: List baselines/runs cap limit at 100 (Query le=100); single-query list (no N+1).

### VA-P1-15: Performance monitoring (M) — DONE
- Engine and DB metrics dashboard
- AC: Dashboard shows latency and execution time
- Note: In-memory latency ring (get_latency_summary), GET /api/v1/metrics/summary, web /dashboard (request count, P50/P95, by endpoint).

### VA-P1-16: Audit logging (initial) (M) — DONE
- Baseline/run event logging
- AC: Events persisted in append-only audit table

### VA-P1-17: Next.js web app scaffold (M) — DONE
- Auth, layout, Tailwind, shadcn/ui
- AC: Login and redirect to dashboard works

### VA-P1-18: Baseline list + detail UI (M) — DONE
- Pagination, search, error states
- AC: List and detail pages render correctly

### VA-P1-19: Run results UI (M) — DONE
- IS/BS/CF tables, KPIs, charts
- AC: Tables render with correct formatting

### VA-P1-20: Unit tests (L) — DONE
- Engine, graph, evaluator, statements, KPIs
- AC: Unit tests pass; coverage >70 percent
- Note: 24 unit tests (graph, evaluator, engine, statements, KPIs); model layer coverage improved.

### VA-P1-21: Integration tests (L) — DONE
- Baseline/run lifecycle and RLS isolation
- AC: Integration suite passes; RLS enforced
- Note: tests/integration (baseline create/list/get, run lifecycle, tenant isolation). Run with INTEGRATION_TESTS=1 and DATABASE_URL set.

### VA-P1-22: Performance tests (M) — DONE
- Engine and API latency thresholds
- AC: Performance tests meet SLAs
- Note: tests/load/test_engine_performance.py — engine 12mo &lt;500ms P95, full pipeline &lt;1s.

### VA-P1-23: Golden file tests (M) — DONE
- Manufacturing template outputs
- AC: Outputs match golden files within tolerance
- Note: tests/golden/ — manufacturing_config.json, manufacturing_base_statements.json, manufacturing_base_kpis.json.

---

## Phase 2 — Draft Layer + LLM Integration

### VA-P2-01: Background job queue (M) — DONE
- Celery + Redis, retries, DLQ
- AC: Jobs execute with retry and status tracking
- Note: `apps/worker/celery_app.py` (Redis broker/backend), `apps/worker/tasks.py` (add, fail_then_dlq; DLQ on final failure). `POST /api/v1/jobs/enqueue`, `GET /api/v1/jobs/{task_id}`. Run worker: `celery -A apps.worker.celery_app worker -l info`.

### VA-P2-02: Draft session CRUD (M) — DONE
- State machine and autosave
- AC: Draft lifecycle transitions enforced
- Note: POST/GET/PATCH/DELETE /api/v1/drafts; state machine active↔ready_to_commit, any→abandoned; workspace in ArtifactStore (draft_workspace); audit draft.created/accessed/abandoned; PATCH supports status and/or workspace (autosave).

### VA-P2-03: LLM provider abstraction (L) — DONE
- Anthropic + OpenAI with structured outputs
- AC: Both providers return valid JSON outputs
- Note: `apps/api/app/services/llm/provider.py` — LLMProvider ABC, complete(messages, response_schema, task_label) → LLMResponse; AnthropicProvider (output_config json_schema), OpenAIProvider (response_format json_schema); retry 3× exponential backoff; TokenUsage, LLMResponse; settings ANTHROPIC_API_KEY, OPENAI_API_KEY.

### VA-P2-04: LLM governance (M) — DONE
- Circuit breaker, routing, metering
- AC: Routing, fallback, and limits enforced
- Note: `apps/api/app/services/llm/router.py` (LLMRouter, default policy, complete_with_routing); `circuit_breaker.py` (per-provider open/half_open/closed); `metering.py` (in-memory usage + check_limit). Settings: LLM_TOKENS_MONTHLY_LIMIT, CIRCUIT_BREAKER_FAILURE_THRESHOLD, CIRCUIT_BREAKER_RECOVERY_SECONDS. ERR_LLM_QUOTA_EXCEEDED (429), ERR_LLM_ALL_PROVIDERS_FAILED (503). Unit tests: tests/unit/test_llm_router.py.

### VA-P2-05: Draft chat endpoint (L) — DONE
- Structured proposals stored as draft deltas
- AC: Proposal validation and persistence works
- Note: POST /api/v1/drafts/{id}/chat (body: message, context); builds system prompt from workspace, calls LLMRouter.complete_with_routing("draft_assumptions"), validates paths under assumptions, appends to pending_proposals and chat_history. POST .../proposals/{id}/accept and .../reject to apply or remove proposals. PROPOSAL_RESPONSE_SCHEMA, _build_draft_assumptions_prompt, _path_under_assumptions, _set_by_path. get_llm_router in deps.

### VA-P2-06: Commit pipeline + changesets (L) — DONE
- Compile to frozen model_config; diff and merge
- AC: Commit creates baseline; changeset merge works
- Note: POST /api/v1/drafts/{id}/commit (body: acknowledge_warnings); integrity checks (IC_GRAPH_ACYCLIC), compile workspace to model_config, create baseline, set draft status=committed. POST/GET /api/v1/changesets, POST .../test (dry-run engine), POST .../merge (new baseline version). model_changesets table and changeset_overrides artifact type. tests/unit/test_drafts_api.py, test_changesets_api.py.

### VA-P2-07: Venture template wizard (M) — DONE
- Template selection and LLM-generated draft
- AC: Draft generated from questionnaire
- Note: POST /api/v1/ventures (create venture from template), POST .../answers (submit questionnaire), POST .../generate-draft (LLM generates assumptions → draft session). Template catalog: apps/api/app/data/default_catalog.json (manufacturing, wholesale, services, SaaS, fintech). LLM task_label: template_initialization. Unit tests: tests/unit/test_ventures_api.py.

### VA-P2-08: Draft workspace UI (L) — DONE
- Chat, assumption editor, integrity status
- AC: End-to-end draft -> commit flow in UI
- Note: /drafts list and /drafts/[id] workspace (assumption tree, chat, pending proposals, Mark ready, Commit, Abandon). API client: drafts list/get/create/patch/chat/acceptProposal/rejectProposal/commit/delete. Integrity dialog on 409; terminal banners for committed/abandoned.

### VA-P2-08b: LLM guardrails & confidence visibility (M) — DONE
- Facts-only constraints in all LLM prompts, confidence display in UI
- AC: LLM prompts include hallucination prevention; confidence badges shown on proposals and assumptions; content safety validation on LLM output
- Note: System prompts updated with CRITICAL RULES (no fabrication, evidence-backed, confidence guide). TEMPLATE_INITIALIZATION_SCHEMA updated with confidence/evidence description. Proposal UI shows confidence badges (green/amber/red). AssumptionTree displays _confidence and _evidence sibling fields inline. Post-LLM content safety validation (_validate_proposal_content) drops unsafe proposals.

### VA-P2-09: Notifications (M) — DONE
- Email and in-app notifications
- AC: Key events generate notifications
- Note: Migration 0008_notifications; notifications table; list/mark-read API; created on run complete and draft commit; web bell icon and /notifications page.

---

## Phase 3 — Monte Carlo + Scenarios + Valuation

### VA-P3-01: Distribution engine + MC runner (L) — DONE
- Supported distributions and seeded RNG
- AC: MC results deterministic with seed
- Note: shared/fm_shared/analysis/distributions.py (sample: triangular, normal, lognormal, uniform, pert); monte_carlo.py (run_monte_carlo → MCResult with percentiles P5–P95 for revenue, ebitda, net_income, fcf). Unit tests: test_distributions.py, test_monte_carlo.py.

r### VA-P3-02: Async MC execution (M) — DONE
- Background jobs with progress reporting
- AC: 1k sim run completes and reports progress
- Note: POST /runs with mc_enabled, num_simulations, seed enqueues Celery run_mc_execute; progress in Redis; GET /runs/{id} returns mc_progress when queued/running; GET /runs/{id}/mc returns percentiles. Migration 0009_runs_async_mc.

### VA-P3-03: Scenario management (M) — DONE
- CRUD with overrides and comparison
- AC: Scenario comparison produces expected variance
- Note: scenarios table (0010_scenarios); POST/GET/DELETE /api/v1/scenarios; POST .../compare returns side-by-side KPIs. Web /scenarios list + compare form.

### VA-P3-04: Valuation module (M) — DONE
- DCF and multiples outputs
- AC: Valuation outputs appear in run results
- Note: shared/fm_shared/analysis/valuation.py (dcf_valuation, multiples_valuation). Sync run accepts valuation_config; GET /runs/{id}/valuation. Web /runs/[id]/valuation page.

### VA-P3-05: Sensitivity + charts (M) — DONE
- Tornado, fan, waterfall charts
- AC: Charts render with correct inputs
- Note: GET /runs/{id}/sensitivity (one-at-a-time ±pct, terminal FCF impact). MC page: percentile table + revenue fan (P10/P50/P90). Valuation page: DCF + multiples cards.

---

## Phase 4 — Integrations + Billing + Compliance

### VA-P4-01: Integration framework + Xero adapter (L)
- OAuth2 connection and sync runner
- AC: Sync produces canonical snapshot

### VA-P4-02: Billing and usage metering (L)
- Stripe subscription lifecycle and limits
- AC: Limits enforced and usage visible

### VA-P4-03: Audit logging (complete) (M)
- Full event catalog and export
- AC: Export works; audit log immutable

### VA-P4-04: Compliance endpoints (M)
- GDPR export and deletion
- AC: Export returns all data; deletion anonymizes

### VA-P4-05: CSV import + covenant monitoring (M)
- Import wizard and covenant alerts
- AC: Import creates draft; breaches trigger alerts

---

## Phase 5 — Excel + Memos + Collaboration

### VA-P5-01: Excel export + live links API (L)
- Export and connection management
- AC: Excel export includes IS/BS/CF sheets

### VA-P5-02: Office.js add-in (L)
- Auth, bindings, pull/push workflows
- AC: Excel Online and Desktop add-in works

### VA-P5-03: Memo pack generator (M)
- HTML/PDF outputs from runs
- AC: Memo outputs contain correct data

### VA-P5-04: Document management + collaboration (M) — DONE
- Attachments, comments, activity feed
- AC: Documents viewable; comments notify users
- Implemented: migration 0018 (document_attachments, comments + RLS); POST/GET/DELETE /api/v1/documents (upload/list/download/delete); POST/GET/DELETE /api/v1/comments (@mentions → notifications); GET /api/v1/activity (audit + comments merged feed)

---

## Phase 6 — Team Collaboration & Workflow Engine

### VA-P6-01: Team & hierarchy data model (M)
- Migration 0011: teams, team_members, job_functions tables with RLS
- Seed default job functions on tenant creation
- AC: Teams CRUD works; hierarchy (reports_to) validates within team; RLS enforced

### VA-P6-02: Team management API (M)
- CRUD for teams, members, job functions
- AC: POST/GET/PATCH/DELETE teams; add/remove/update members; list job functions

### VA-P6-03: Workflow template engine (L)
- Migration 0011: workflow_templates, workflow_instances tables
- Stage definitions with assignee rules (explicit, reports_to, reports_to_chain, team_pool)
- Seed default templates (Self-Service, Standard Review, Full Approval)
- Workflow state machine: pending → in_progress → submitted → approved/returned → completed
- AC: Create workflow from template; stages advance correctly; routing resolves correct reviewer via hierarchy

### VA-P6-04: Task assignment system (L)
- Migration 0011: task_assignments table
- Create assignment (top-down: senior assigns to junior/pool)
- Submit for review (bottom-up: junior submits, system routes to reviewer)
- Claim pool assignments
- Deadline tracking with approaching/overdue detection
- AC: Assignments created and visible in inbox; pool claim works; deadlines tracked; status transitions enforced

### VA-P6-05: Review & correction pipeline (L)
- Migration 0011: reviews, change_summaries tables
- Review decisions: approve, request_changes, reject
- Inline corrections tracked as structured diff {path, old_value, new_value, reason}
- Change summary auto-generated on review with corrections
- AC: Reviewer can approve/return/reject; corrections recorded as diff; change summary created

### VA-P6-06: Learning feedback system (M)
- LLM task_label: review_summary (generates learning_points from corrections)
- Acknowledgment tracking (author marks feedback as read)
- AC: Corrections generate change summary with LLM learning points; author can acknowledge; unacknowledged feedback highlighted

### VA-P6-07: Workflow notifications (M)
- Notification events: task_assigned, task_submitted, review decision, deadline_approaching, deadline_overdue, workflow_completed
- Email templates for workflow events
- AC: All workflow events generate in-app + email notifications; deadline reminders fire at 24h and 4h

### VA-P6-08: Team management UI (M)
- /settings/teams — list, create, edit teams
- Team detail — member list, hierarchy tree visualization, add/remove/edit members
- Job function management
- AC: Teams CRUD in UI; hierarchy displayed as tree; member permissions editable

### VA-P6-09: Task inbox UI (L)
- /inbox — personal task inbox with tabs (My Tasks, Team Pool, Awaiting Review, Review Requests)
- Assignment cards with priority badges, deadlines, status
- /inbox/{id} — assignment detail with instructions panel and workspace link
- /assignments/new — create assignment wizard (type, entity, assignee, instructions, deadline, workflow)
- AC: Inbox shows all relevant tasks; pool claim works; create assignment wizard produces correct assignments

### VA-P6-10: Review workspace UI (L)
- /inbox/{id}/review — split layout (methodology + assumptions + review form)
- Methodology panel: chat history (read-only), approach summary (LLM task: methodology_context)
- Inline editing with change tracking (every edit recorded)
- Review decision form: approve/request_changes/reject with notes
- AC: Reviewer sees methodology context; inline edits tracked as diffs; decision persists and advances workflow

### VA-P6-11: Learning feedback UI (M)
- /inbox/feedback — list of change summaries with diff display
- Unacknowledged items highlighted
- Change diff visualization: old/new values with reasons
- LLM-generated learning points with "AI-generated" label
- Acknowledge button
- AC: Feedback displayed with structured diffs; learning points shown; acknowledge updates timestamp

### VA-P6-12: Test suite — Phase 6 (L)
- test_teams_api.py — CRUD, hierarchy validation, RLS
- test_workflow_engine.py — template creation, stage advancement, routing logic
- test_assignments_api.py — create, claim, submit, status transitions
- test_reviews_api.py — approve/return/reject, change tracking, summary generation
- test_workflow_integration.py — full flow: assign → build → submit → review → approve/return
- AC: All Phase 6 tests pass; workflow integration test covers complete lifecycle

---

## Phase 7 — Budgeting & Board Pack

### VA-P7-01: Budget data model & migrations (M)
- Migration: budgets, budget_line_items, budget_periods, budget_versions, budget_department_allocations tables with RLS
- Budget lifecycle state machine: draft → submitted → under_review → approved → active → closed
- Versioning: each budget has immutable snapshots (budget_version_id) so the CFO can see revision history
- AC: Budget CRUD works; state transitions enforced; versions are append-only; RLS tenant-scoped

### VA-P7-02: Budget CRUD & department allocation API (L)
- POST/GET/PATCH /api/v1/budgets — create, list, get, update budget metadata (fiscal year, label, status)
- POST /api/v1/budgets/{id}/line-items — add/update/remove line items (account ref, monthly amounts, notes)
- POST /api/v1/budgets/{id}/departments — allocate budget by department/cost centre with limits
- Budget cloning: POST /api/v1/budgets/{id}/clone (copy structure for next period or what-if)
- AC: Line items persist with monthly granularity; department allocations sum-checked against total; clone preserves structure

### VA-P7-03: Budget templates & LLM-assisted seeding (M)
- Pre-built budget templates per industry (manufacturing, SaaS, services, wholesale — reuse existing catalog)
- LLM task_label: budget_initialization — given prior-year actuals + strategic priorities, propose initial line-item amounts with confidence scores
- Template wizard: select template → answer questionnaire (headcount plan, capex outlook, growth targets) → LLM seeds budget
- AC: Budget created from template with LLM-proposed amounts; confidence badges displayed; user can accept/reject each line

### VA-P7-04: Actuals import & variance analysis engine (L)
- Import actuals from ERP sync snapshots (Phase 4 canonical_sync_snapshot) or CSV upload
- Variance calculation: budget vs actual (absolute, percentage, YTD cumulative) per line item per period
- Variance classification: favourable/unfavourable with materiality threshold (configurable per tenant)
- Drill-down: variance by department, by account, by period
- Endpoint: GET /api/v1/budgets/{id}/variance?period=YYYY-MM&department=x
- AC: Variance computed correctly; favourable/unfavourable classification correct; drill-down works by department and period

### VA-P7-05: Rolling forecast engine (M)
- Replace remaining budget periods with latest actuals + re-forecast
- POST /api/v1/budgets/{id}/reforecast — creates new budget version with actuals locked and remaining periods re-projected
- LLM task_label: budget_reforecast — given YTD actuals and original assumptions, propose revised forecast with variance explanations
- AC: Reforecast creates new version; actuals periods locked; revised forecast periods show LLM-assisted projections with confidence

### VA-P7-06: Budget approval workflow integration (M)
- Integrates with Phase 6 workflow engine
- Seed workflow template: Budget Approval (stages: department_head_review → finance_review → cfo_approval → board_presentation)
- Budget submission triggers workflow; each stage reviewer sees budget summary + variance highlights
- CFO approval transitions budget to active status
- AC: Budget submission creates workflow instance; stage progression works; CFO approval activates budget

### VA-P7-07: Board pack composer (L)
- Board pack template engine: configurable sections (executive summary, P&L, BS, CF, budget variance, KPI dashboard, scenario comparison, strategic commentary)
- Section ordering and inclusion controlled per pack
- Auto-populated from run results, budget variance, KPI data, scenario compare
- LLM task_label: board_pack_narrative — generates executive summary and commentary sections from financial data with facts-only constraints
- Branding: applies tenant logo, colour palette, and T&C footer (Phase 10 org settings)
- AC: Board pack assembles all sections; LLM narrative is factual and sourced; branding applied

### VA-P7-08: Board pack export (PDF/PPTX/HTML) (L)
- PDF generation with professional layout (cover page, ToC, numbered sections, charts, tables, page numbers)
- PPTX generation for board presentation (one section per slide, chart-heavy layout)
- HTML generation for web preview and email distribution
- Chart rendering: IS/BS/CF waterfall, budget variance bar, KPI trend lines, scenario tornado, MC fan
- Configurable: which sections to include, period range, comparison periods
- AC: PDF/PPTX/HTML exports render correctly; charts embedded; branding applied; file size reasonable (<10MB for standard pack)

### VA-P7-09: Board pack scheduling & distribution (M)
- Schedule recurring pack generation (e.g. monthly on 5th business day)
- Distribution list: email board pack to specified recipients with optional cover note
- Pack history: list of generated packs with download links and generation metadata
- AC: Scheduled generation runs on time; email delivery works; pack history accessible

### VA-P7-10: Budget & board pack UI (L)
- /budgets — list budgets with status badges, fiscal year filter
- /budgets/new — create budget wizard (template selection, period configuration, department setup)
- /budgets/[id] — budget workspace (line-item editor with monthly columns, department tabs, totals row, variance column when actuals available)
- /budgets/[id]/variance — variance dashboard (heatmap by department x period, drill-down tables, charts)
- /budgets/[id]/reforecast — rolling forecast view (locked actuals greyed out, editable forecast periods)
- /board-packs — list generated packs, create new pack
- /board-packs/new — pack composer (select sections, configure, preview, generate)
- /board-packs/[id] — pack preview with download buttons (PDF/PPTX/HTML)
- AC: All budget pages render correctly; line-item editor supports inline editing; variance heatmap displays; board pack preview matches export output

### VA-P7-11: Budget KPI dashboard (M)
- Dedicated budget-focused dashboard widgets: burn rate, runway, budget utilisation %, variance trend, department spend ranking
- Alerting: configurable thresholds (e.g. department >90% utilised, unfavourable variance >10%) trigger notifications
- CFO view: consolidated across all departments with drill-down
- AC: Dashboard widgets render correct data; alerts fire on threshold breach; drill-down navigates to variance detail

### VA-P7-12: Test suite — Phase 7 (L)
- test_budgets_api.py — CRUD, line items, department allocation, cloning, state transitions
- test_variance_engine.py — actuals import, variance calculation, classification, drill-down
- test_rolling_forecast.py — reforecast version creation, actuals locking, LLM projection
- test_board_pack.py — section assembly, LLM narrative, branding, export format validation
- test_budget_workflow_integration.py — full flow: create budget → submit → review stages → CFO approve → active
- AC: All Phase 7 tests pass; variance calculations verified against manual examples; board pack exports validated

---

## Post-Launch Backlog (v1.1+)
- Multi-currency and FX overlays
- SSO/SAML
- Template marketplace
- Connector marketplace and QuickBooks adapter
- Cross-team workflow routing (multi-team approval chains)
- Workflow analytics dashboard (cycle times, review rates, bottleneck detection)
- AI-assisted review suggestions (flag unusual assumptions for reviewer attention)
- Peer comparison (anonymous benchmarking of model accuracy across team)
- Board pack benchmarking (compare pack KPIs against industry median)
- Natural language budget queries (CFO asks "which department is over budget?" via chat)
