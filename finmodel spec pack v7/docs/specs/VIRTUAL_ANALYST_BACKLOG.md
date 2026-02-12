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

### VA-P2-02: Draft session CRUD (M)
- State machine and autosave
- AC: Draft lifecycle transitions enforced

### VA-P2-03: LLM provider abstraction (L)
- Anthropic + OpenAI with structured outputs
- AC: Both providers return valid JSON outputs

### VA-P2-04: LLM governance (M)
- Circuit breaker, routing, metering
- AC: Routing, fallback, and limits enforced

### VA-P2-05: Draft chat endpoint (L)
- Structured proposals stored as draft deltas
- AC: Proposal validation and persistence works

### VA-P2-06: Commit pipeline + changesets (L)
- Compile to frozen model_config; diff and merge
- AC: Commit creates baseline; changeset merge works

### VA-P2-07: Venture template wizard (M)
- Template selection and LLM-generated draft
- AC: Draft generated from questionnaire

### VA-P2-08: Draft workspace UI (L)
- Chat, assumption editor, integrity status
- AC: End-to-end draft -> commit flow in UI

### VA-P2-09: Notifications (M)
- Email and in-app notifications
- AC: Key events generate notifications

---

## Phase 3 — Monte Carlo + Scenarios + Valuation

### VA-P3-01: Distribution engine + MC runner (L)
- Supported distributions and seeded RNG
- AC: MC results deterministic with seed

### VA-P3-02: Async MC execution (M)
- Background jobs with progress reporting
- AC: 1k sim run completes and reports progress

### VA-P3-03: Scenario management (M)
- CRUD with overrides and comparison
- AC: Scenario comparison produces expected variance

### VA-P3-04: Valuation module (M)
- DCF and multiples outputs
- AC: Valuation outputs appear in run results

### VA-P3-05: Sensitivity + charts (M)
- Tornado, fan, waterfall charts
- AC: Charts render with correct inputs

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

### VA-P5-04: Document management + collaboration (M)
- Attachments, comments, activity feed
- AC: Documents viewable; comments notify users

---

## Post-Launch Backlog (v1.1+)
- Multi-currency and FX overlays
- SSO/SAML
- Template marketplace
- Advanced approval workflows
- Connector marketplace and QuickBooks adapter
