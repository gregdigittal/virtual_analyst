# Build Plan — FinModel v1 (Revised)
**Date:** 2026-02-11
**Version:** 2.0 (Production-Ready)

## Overview
Six phases, each with clear inputs, outputs, and a gate (acceptance criteria that must pass before the next phase begins). Phases are sequential — do not start Phase N+1 until Phase N's gate passes.

This revised plan includes all foundational infrastructure, security, observability, and operational excellence requirements for a production-ready v1 release.

---

## Phase 0 — Foundation & Infrastructure
**Goal:** Establish development environment, CI/CD, error handling, logging, and monitoring foundation.

**Duration:** 1-2 weeks

### Dependencies
- None (starting point)

### Deliverables
1. **Repository scaffolding**
   - Monorepo structure (apps, shared, tests, docs)
   - Git initialization with .gitignore
   - README.md with setup instructions
2. **Python project setup**
   - pyproject.toml with all dependencies
   - Development environment (venv)
3. **Docker Compose** for local development
   - Postgres, Redis, Supabase containers
   - Volume persistence
4. **Environment configuration**
   - .env.example with all variables
   - Environment-based settings
5. **Error handling framework**
   - Error classes (ValidationError, EngineError, etc.)
   - Error response envelope
   - HTTP status code mapping
6. **Structured logging**
   - Structlog configuration
   - Correlation IDs
   - Context variables (tenant_id, user_id)
7. **Metrics & health checks**
   - Prometheus metrics endpoint
   - Liveness/readiness probes
   - Basic API metrics (requests, latency, errors)
8. **Security middleware**
   - Security headers (CSP, HSTS, X-Frame-Options, etc.)
   - Rate limiting (per IP, per tenant)
   - Input validation framework (Pydantic)
9. **CI/CD pipeline**
   - GitHub Actions workflow
   - Automated tests (lint, type check, unit tests)
   - Security scanning (dependencies)
10. **Pre-commit hooks**
    - Ruff (linting)
    - Black (formatting)
    - MyPy (type checking)
11. **FastAPI application skeleton**
    - Health endpoints
    - Metrics endpoint
    - CORS configuration
    - Error handlers

### Gate Criteria
- [ ] `docker-compose up` starts all services successfully
- [ ] Any developer can set up environment in <30 minutes
- [ ] FastAPI app starts and responds to `/api/v1/health/ready`
- [ ] Metrics endpoint `/metrics` returns Prometheus format
- [ ] Structured logs output correctly (JSON in prod, pretty in dev)
- [ ] Error responses use consistent envelope format
- [ ] Pre-commit hooks run and pass
- [ ] CI pipeline runs and passes (all checks green)
- [ ] Rate limiting blocks >100 req/min from single IP
- [ ] Security headers present in all responses

---

## Phase 1 — Core Model Engine
**Goal:** Given a model_config_v1 artifact, produce a deterministic 3-statement forecast with performance and observability.

**Duration:** 3-4 weeks

### Dependencies
- Phase 0 gate passed
- Supabase project provisioned (Postgres + Auth + Storage)
- Migration 0001_init.sql applied
- Migration 0002_functions_and_rls.sql applied

### Deliverables
1. **Pydantic models** for model_config_v1 (full schema validation)
2. **Runtime engine** — `shared/fm_shared/model/engine.py`
   - Parse model_config_v1
   - Build calculation graph from driver_blueprint
   - Execute time-series (monthly resolution, configurable horizon)
   - Produce Income Statement, Balance Sheet, Cash Flow Statement
   - Produce KPI outputs (margins, ratios, working capital metrics)
   - **Complexity limits enforcement** (max nodes, formulas, horizon)
   - **Execution timeout** (30s for deterministic, configurable)
   - **Performance logging** (execution time by phase)
3. **API routes** — baseline CRUD, run CRUD, artifact storage
   - `POST /api/v1/baselines` — create baseline from model_config
   - `GET /api/v1/baselines` — list baselines (paginated)
   - `GET /api/v1/baselines/{id}` — retrieve baseline
   - `PATCH /api/v1/baselines/{id}` — archive/restore baseline
   - `POST /api/v1/runs` — execute a run against a baseline
   - `GET /api/v1/runs` — list runs (paginated)
   - `GET /api/v1/runs/{id}` — retrieve run status + results
   - `GET /api/v1/runs/{id}/statements` — retrieve financial statements
   - `GET /api/v1/runs/{id}/kpis` — retrieve KPIs
4. **Storage layer** — save/load JSON artifacts to Supabase Storage
   - Schema validation before save
   - Compression for large artifacts (>100KB)
   - Versioning support
5. **Database optimizations**
   - Indexes on all foreign keys and frequently queried fields
   - Connection pooling (20 connections per instance)
   - Query optimization (avoid N+1)
6. **Performance monitoring**
   - Engine execution metrics (duration, nodes evaluated)
   - Database query metrics (count, duration)
   - API endpoint latency metrics
   - Performance dashboard (Grafana or similar)
7. **Audit logging** (initial implementation)
   - `baseline.created`, `baseline.accessed`, `baseline.archived`
   - `run.created`, `run.accessed`
   - Immutable audit log table
8. **Basic web UI** — Next.js app with:
   - Login (Supabase Auth: email/password)
   - Baseline list page (with search, filter, pagination)
   - Baseline detail page (view model_config)
   - Run results page showing IS/BS/CF tables
   - Error handling (toast notifications)
   - Loading states
9. **Test suite** — see TESTING_STRATEGY.md Phase 1 section
   - Unit tests: graph builder, expression evaluator, statements, KPIs
   - Integration tests: baseline CRUD, run lifecycle, RLS enforcement
   - Performance tests: engine execution time
   - Golden file tests: manufacturing template

### Gate Criteria
- [ ] Load the `manufacturing_discrete` template from default_catalog.json
- [ ] Create a model_config_v1 with sample assumptions
- [ ] Run the engine → produces 12-month IS/BS/CF in <500ms (P95)
- [ ] Balance sheet balances every month (assets = liabilities + equity, tolerance < 0.01)
- [ ] Re-run with same inputs → identical outputs (deterministic)
- [ ] All Phase 1 tests pass (unit + integration)
- [ ] API returns correct JSON envelope with request_id and correlation_id
- [ ] Web UI renders login → baseline list → run results
- [ ] Pagination works (50 items per page)
- [ ] RLS policies prevent cross-tenant access (integration test passes)
- [ ] Database queries complete in <50ms (P95)
- [ ] Audit log contains all baseline and run events
- [ ] Performance dashboard shows API latency, engine execution time
- [ ] Error responses use consistent error codes and user-friendly messages

---

## Phase 2 — Draft Layer + LLM Integration
**Goal:** Analysts can chat with an LLM to propose assumptions, then commit to a deterministic model_config. Includes background job queue and LLM quality metrics.

**Duration:** 3-4 weeks

### Dependencies
- Phase 1 gate passed
- At least one LLM provider API key configured (Anthropic or OpenAI)
- Redis deployed and accessible (for Celery)

### Deliverables
1. **Background job queue** — Celery with Redis backend
   - Worker processes for async tasks
   - Job status tracking
   - Dead letter queue for failed jobs
   - Retry with exponential backoff
2. **Draft session CRUD** — `POST/GET/PATCH/DELETE /api/v1/drafts`
   - State machine: active → ready_to_commit → committed | abandoned
   - Storage: draft workspace as mutable JSON in Supabase Storage
   - Auto-save every 30 seconds
3. **LLM service** — `apps/api/app/services/llm_service.py`
   - Provider abstraction (Anthropic Claude, OpenAI GPT-4)
   - Routing policy evaluation
   - Structured output (JSON mode) with schema validation
   - Call logging → llm_call_log_v1
   - Usage metering aggregation
   - Circuit breaker for provider failures
   - Fallback chain (primary → secondary → error)
4. **Analyst chat endpoint** — `POST /api/v1/drafts/{id}/chat`
   - Accepts user message, returns LLM-proposed assumptions
   - LLM output validated against expected structure
   - Proposed changes stored as draft deltas (not applied to baseline)
   - Chat history persisted
   - **Background processing** for heavy LLM calls (>10s expected)
5. **LLM quality metrics**
   - Proposal acceptance rate (% accepted vs. rejected)
   - User edit distance (how much users modify proposals)
   - Confidence accuracy (high confidence → higher acceptance)
   - Feedback mechanism (thumbs up/down on proposals)
6. **Commit pipeline** — `POST /api/v1/drafts/{id}/commit`
   - Validate draft against model_config_v1 schema
   - Run integrity checks (see DRAFT_COMMIT_SPEC.md)
   - Compile to frozen model_config_v1 artifact
   - Create new baseline version
   - Mark draft as committed
   - Audit log: `draft.committed`
7. **Changeset support** — `POST/GET /api/v1/changesets`
   - Create changeset against existing baseline
   - Test changeset (dry-run)
   - Merge changeset → new baseline version
   - Diff viewer (show what changed)
8. **Venture template wizard** — API + UI
   - Select template from catalog
   - Answer question_plan questions
   - LLM proposes initial assumptions from answers
   - User reviews → commit
9. **Draft workspace UI** enhancements
   - Chat panel with message history
   - Assumption editor (tree view, inline editing)
   - Pending proposals (accept/reject UI)
   - Integrity check status (traffic light: green/amber/red)
   - Commit confirmation dialog
   - Activity log (who changed what, when)
10. **Changeset UI**
    - Diff viewer (before/after comparison)
    - Dry-run results preview
    - Merge confirmation
11. **Notifications service** (initial)
    - Email notifications (draft ready, run complete)
    - In-app notifications (bell icon)
    - Notification preferences

### Gate Criteria
- [ ] Create draft session via API
- [ ] Send chat message → LLM responds with structured assumption proposals
- [ ] LLM call logged with tokens, cost, latency
- [ ] LLM call routed to correct provider based on routing policy
- [ ] Circuit breaker opens after 5 consecutive provider failures
- [ ] Edit proposed assumptions in UI
- [ ] Commit draft → new baseline created
- [ ] Committed baseline produces valid run (Phase 1 engine)
- [ ] Changeset: create, test (dry-run shows diff), merge
- [ ] Background job queue processes LLM calls asynchronously
- [ ] LLM quality metrics dashboard shows acceptance rate, edit distance
- [ ] User feedback (thumbs up/down) recorded
- [ ] Audit log contains `draft.created`, `draft.committed` events
- [ ] All Phase 2 tests pass
- [ ] Email notification sent when draft is ready to commit
- [ ] Activity log shows all changes with user and timestamp

---

## Phase 3 — Monte Carlo + Scenarios + Valuation
**Goal:** Run probabilistic simulations (async), manage scenarios, and produce valuations. Includes comparison tools and sensitivity analysis.

**Duration:** 3-4 weeks

### Dependencies
- Phase 2 gate passed
- Background job queue operational

### Deliverables
1. **Distribution engine** — `shared/fm_shared/analysis/distributions.py`
   - Support: triangular, normal, lognormal, uniform, PERT
   - Seeded RNG for reproducibility
   - Sample N draws per driver per simulation
2. **Monte Carlo runner** — `shared/fm_shared/analysis/monte_carlo.py`
   - Outer loop: for each simulation, sample drivers → run deterministic engine → collect outputs
   - Collect: revenue, EBITDA, FCF, net income per period per simulation
   - Compute percentiles: P5, P10, P25, P50, P75, P90, P95
   - Store MC results as run artifact
   - **Vectorized computation** (NumPy)
   - **Parallel execution** (ProcessPoolExecutor for heavy runs)
3. **Async MC execution**
   - MC runs >1,000 sims execute as background job (Celery)
   - Progress reporting (via WebSocket or polling)
   - Status: queued → running → succeeded | failed
   - Timeout: 10 minutes max
4. **Scenario management** — `POST/GET/PATCH/DELETE /api/v1/scenarios`
   - Named scenario with override set
   - Apply overrides to base model_config at runtime
   - Compare scenarios side-by-side
   - Scenario tags/categories
5. **Valuation module** — `shared/fm_shared/analysis/valuation.py`
   - DCF: configurable WACC, terminal growth, terminal multiple
   - Multiples: EV/EBITDA, EV/Revenue, P/E with comparable inputs
   - Output: enterprise value range (P10/P50/P90 if MC enabled)
6. **Baseline comparison** — `POST /api/v1/baselines/compare`
   - Compare two baseline versions
   - Show differences (assumptions, results)
   - Variance analysis
7. **Sensitivity analysis** — `POST /api/v1/runs/{id}/sensitivity`
   - One-at-a-time driver variation
   - Tornado chart inputs (which drivers have biggest impact)
   - Automated execution (vary each driver ±20%)
8. **Waterfall charts** — Component library
   - Revenue bridge
   - EBITDA bridge
   - Cash flow waterfall
9. **API routes**
   - `POST /api/v1/runs` — extended with `mc_enabled`, `num_simulations`, `scenario_id`, `seed`, `valuation_config`
   - `GET /api/v1/runs/{id}/mc` — percentile outputs
   - `GET /api/v1/runs/{id}/valuation` — valuation outputs
   - `GET /api/v1/runs/{id}/sensitivity` — sensitivity results
   - `POST/GET/PATCH/DELETE /api/v1/scenarios`
10. **Web UI updates**
    - MC results: fan charts, tornado sensitivity, distribution histograms
    - Scenario comparison table (side-by-side)
    - Valuation summary card (EV range, implied multiples)
    - Baseline comparison page (diff viewer)
    - Waterfall charts (revenue, EBITDA, FCF)
    - Real-time MC progress (WebSocket or polling)

### Gate Criteria
- [ ] Run 1,000 simulations with triangular distributions on utilization, yield, price
- [ ] P50 FCF within 5% of deterministic base case
- [ ] Same seed → identical MC outputs (deterministic with seed)
- [ ] Scenario "Downside: Supply Disruption" produces lower revenue vs base
- [ ] DCF valuation produces enterprise value with range from MC
- [ ] Fan chart renders in UI (P10/P50/P90 bands)
- [ ] Tornado chart shows driver sensitivity correctly
- [ ] MC run with 10,000 sims completes as background job in <5 minutes
- [ ] Real-time progress updates during MC execution
- [ ] Baseline comparison shows correct differences
- [ ] Sensitivity analysis identifies top 5 impact drivers
- [ ] Waterfall chart renders correctly
- [ ] All Phase 3 tests pass
- [ ] Audit log contains `run.created` with mc_enabled flag
- [ ] Performance: 100 sims <5s, 1k sims <30s, 10k sims <5min

---

## Phase 4 — ERP Integrations + Billing + Compliance
**Goal:** Connect to accounting systems, sync data, meter usage, manage subscriptions. Includes audit logging, compliance reporting, and notifications.

**Duration:** 4-5 weeks

### Dependencies
- Phase 3 gate passed
- Migration 0004_integrations_billing_llm.sql applied
- At least one ERP sandbox (Xero or QuickBooks) available for testing
- Stripe account provisioned

### Deliverables
1. **Integration framework** — `apps/api/app/services/integrations/`
   - Connection management (OAuth2 flows)
   - Provider adapters: Xero (initial), QuickBooks Online (optional for v1)
   - Canonical mapping: provider-specific → canonical accounts
   - Sync runner: pull data → map → store canonical_sync_snapshot_v1
   - Sync scheduling (configurable interval)
   - Error handling and retry
2. **ERP discovery** — `POST /api/v1/integrations/discover`
   - Probe connected ERP for available data (chart of accounts, periods)
   - Store as erp_discovery_session_v1
3. **Billing service** — `apps/api/app/services/billing.py`
   - Plan management (Starter/Pro/Enterprise)
   - Subscription lifecycle (create, upgrade, downgrade, cancel)
   - Usage metering: aggregate llm_call_log + sync events + MC runs
   - Limit enforcement: check plan limits before expensive operations
   - Stripe integration for payment processing
   - Invoice generation
4. **Audit logging** (complete implementation)
   - All event types per AUDIT_COMPLIANCE_SPEC.md
   - Immutable audit log table (append-only)
   - S3 backup for compliance (7-year retention)
   - Audit log viewer UI (admin only)
   - Export audit logs (CSV, JSON)
   - Audit event search and filter
5. **Compliance reporting**
   - Quarterly compliance report generation
   - SOC 2 audit package preparation
   - GDPR data export endpoint (`GET /api/v1/gdpr/data-export`)
   - GDPR data deletion endpoint (`DELETE /api/v1/gdpr/delete-user`)
   - Consent management
6. **Notifications** (complete implementation)
   - Email service (SendGrid or AWS SES)
   - Notification templates (run complete, draft ready, limit exceeded, etc.)
   - In-app notification system
   - Notification preferences (per user)
   - Webhook support (for integrations)
7. **CSV data import**
   - `POST /api/v1/import/csv` — upload CSV with assumptions
   - Mapping wizard (map CSV columns to model fields)
   - Validation and preview
   - Create draft from CSV
8. **Covenant monitoring** (for credit use cases)
   - Define covenant thresholds (debt/equity < 2.5, DSCR > 1.2, etc.)
   - Automatic monitoring on each run
   - Alert when covenant breached
   - Covenant dashboard
9. **API routes**
   - `POST/GET /api/v1/integrations/connections`
   - `POST /api/v1/integrations/connections/{id}/sync`
   - `GET /api/v1/integrations/connections/{id}/snapshots`
   - `GET /api/v1/billing/subscription`
   - `GET /api/v1/billing/usage`
   - `POST /api/v1/billing/upgrade` (change plan)
   - `GET /api/v1/audit/events` (admin only)
   - `GET /api/v1/audit/events/export`
   - `GET /api/v1/compliance/report`
   - `GET /api/v1/gdpr/data-export`
   - `DELETE /api/v1/gdpr/delete-user`
   - `POST /api/v1/import/csv`
10. **Web UI updates**
    - Integration connection wizard
    - Sync status dashboard
    - Billing / usage page (current plan, usage, upgrade)
    - Audit log viewer (admin)
    - Notifications page (inbox)
    - Notification preferences
    - CSV import wizard
    - Covenant dashboard

### Gate Criteria
- [ ] Connect Xero sandbox → OAuth2 flow completes
- [ ] Sync trial balance → canonical_sync_snapshot_v1 stored
- [ ] Sync run logged as integration_sync_run_v1
- [ ] Usage meter shows LLM tokens + sync events for current period
- [ ] Plan limit enforcement: blocked when over limit, clear error message
- [ ] Stripe subscription created and webhook handlers functional
- [ ] Invoice generated and viewable
- [ ] Audit log contains all event types from catalog
- [ ] Audit log export works (CSV and JSON)
- [ ] GDPR data export returns all user data
- [ ] GDPR data deletion works and anonymizes audit logs
- [ ] Email notifications sent for key events
- [ ] In-app notifications work (bell icon with count)
- [ ] CSV import creates draft from uploaded file
- [ ] Covenant breach triggers alert
- [ ] All Phase 4 tests pass
- [ ] Compliance report generates correctly

---

## Phase 5 — Export, Memos & Collaboration
**Goal:** Bidirectional Excel integration, automated document generation, and collaboration features.

**Duration:** 3-4 weeks

### Dependencies
- Phase 4 gate passed
- Migration 0005_excel_and_memos.sql applied

### Deliverables
1. **Excel export** (static) — `GET /api/v1/runs/{id}/export/excel`
   - Export run results to Excel (IS, BS, CF as sheets)
   - Export multiple scenarios to single workbook
   - Formatted with headers, currency, etc.
   - Charts embedded (optional)
2. **Excel connection API** (bidirectional)
   - `POST/GET /api/v1/excel/connections` — create/manage bindings
   - `POST /api/v1/excel/connections/{id}/pull` — server → Excel
   - `POST /api/v1/excel/connections/{id}/push` — Excel → server (creates changeset)
   - WebSocket endpoint for real-time refresh notifications
   - Role-based push permissions (can_push_roles)
3. **Office.js add-in** — `apps/excel-addin/`
   - Manifest + taskpane
   - Auth via Supabase token
   - Binding registration (map named ranges to model paths)
   - Pull: populate cells from run results
   - Push: detect changes, validate, send to API
   - Push behavior: draft_override | changeset | blocked (per connection config)
   - Role-gated push (check can_push_roles)
   - Conflict detection (version checks)
4. **Memo pack generator** — `apps/api/app/services/memo_service.py`
   - Template-driven: investment_committee, credit_memo, valuation_note
   - Section assembly from run results + assumptions + evidence
   - Content blocks: markdown, table_ref, chart_ref, assumption_refs, risk_summary
   - Output formats: HTML (primary), PDF (via weasyprint)
   - Store as memo_pack_v1 artifact
5. **PDF statement upload + OCR** (optional for v1, but valuable)
   - `POST /api/v1/upload/pdf` — upload financial statements
   - OCR extraction (Tesseract or AWS Textract)
   - Map extracted data to model fields
   - Create draft from PDF data
6. **Document management**
   - Attach evidence documents to assumptions
   - Upload supporting files (PDFs, spreadsheets)
   - File storage in Supabase Storage
   - File viewer in UI
7. **Collaboration features**
   - Comments on assumptions
   - @mentions in draft chat
   - Activity feed (who changed what)
   - Real-time presence (who's viewing draft)
8. **API routes**
   - `GET /api/v1/runs/{id}/export/excel`
   - `POST/GET /api/v1/excel/connections`
   - `POST /api/v1/excel/connections/{id}/pull`
   - `POST /api/v1/excel/connections/{id}/push`
   - `POST /api/v1/memos` — generate memo
   - `GET /api/v1/memos` — list memos
   - `GET /api/v1/memos/{id}` — metadata
   - `GET /api/v1/memos/{id}/download?format=html|pdf`
   - `POST /api/v1/upload/pdf`
   - `POST /api/v1/documents` — attach document
   - `POST /api/v1/comments` — add comment
9. **Web UI updates**
   - Excel connection management page
   - Memo generation wizard (select run → choose type → preview → generate)
   - Memo viewer (HTML render in iframe)
   - Download buttons for PDF
   - PDF upload wizard
   - Document library
   - Comments UI (threaded)
   - Activity feed

### Gate Criteria
- [ ] Export run to Excel → download works, contains IS/BS/CF sheets
- [ ] Export multiple scenarios → single workbook with multiple sheets
- [ ] Create Excel connection with 2+ bindings
- [ ] Pull: assumptions + KPIs populate in Excel
- [ ] Push: change assumption in Excel → changeset created on server
- [ ] Push rejected for investor role (not in can_push_roles)
- [ ] Conflict detection: push rejected if baseline version changed
- [ ] Generate IC memo from run → HTML/PDF outputs
- [ ] Memo sections contain correct data from run results
- [ ] PDF upload extracts data and creates draft
- [ ] Document attached to assumption and viewable
- [ ] Comment added to assumption, @mention notifies user
- [ ] Activity feed shows recent changes
- [ ] All Phase 5 tests pass
- [ ] Excel add-in loads in Excel Online and Desktop

---

## Post-Launch Backlog (v1.1+)
- Multi-currency support + FX overlays
- NCI (non-controlling interest) consolidation
- Deep research sessions (long-running LLM research)
- Connector marketplace (community ERP adapters)
- QuickBooks Online adapter
- Advanced Office.js features (real-time collaboration)
- DOCX memo output
- SSO/SAML for enterprise
- Dedicated environments
- Advanced approval workflows
- Template marketplace (custom templates)
- AI-powered insights (anomaly detection)

---

## Release Timeline Estimate

| Phase | Duration | Cumulative | Team Size |
|---|---|---|---|
| Phase 0 | 1-2 weeks | 2 weeks | 2 developers |
| Phase 1 | 3-4 weeks | 6 weeks | 3-4 developers |
| Phase 2 | 3-4 weeks | 10 weeks | 3-4 developers |
| Phase 3 | 3-4 weeks | 14 weeks | 3-4 developers |
| Phase 4 | 4-5 weeks | 19 weeks | 4-5 developers |
| Phase 5 | 3-4 weeks | 23 weeks | 4-5 developers |
| **Total** | **~23 weeks** | **~5.5 months** | **Avg 3-4 devs** |

**Buffer:** Add 20% for unknowns = **~28 weeks (~6.5 months)**

---

## Quality Gates Summary

Every phase must pass:
- [ ] All tests passing (unit, integration, E2E where applicable)
- [ ] Code coverage >70% for shared/fm_shared
- [ ] Security scan passes (no high/critical vulnerabilities)
- [ ] Performance targets met (per PERFORMANCE_SPEC.md)
- [ ] Error handling consistent (per ERROR_HANDLING_SPEC.md)
- [ ] Logging comprehensive (per OBSERVABILITY_SPEC.md)
- [ ] Audit events logged (per AUDIT_COMPLIANCE_SPEC.md)
- [ ] Documentation updated (README, API docs)
- [ ] Manual testing of key user flows
- [ ] Staging deployment successful
- [ ] Product owner sign-off

---

## Success Metrics (v1 Launch)

**Technical:**
- API P95 latency <1s (non-MC endpoints)
- Error rate <1%
- Test coverage >70%
- Zero critical security vulnerabilities
- 99.5% uptime

**Product:**
- Time to first model <60 minutes (new user)
- Baseline commit success rate >90%
- Run success rate >95%
- LLM proposal acceptance rate >60%

**Business:**
- 5+ beta customers on paid plans
- Trial→paid conversion >15%
- Gross margin >70%
- NPS >40
