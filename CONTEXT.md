# Project Context — Virtual Analyst

> Last updated: 2026-03-17
> Commit: 7b567e2 — feat(sprint8): platform hardening — PIM-7.7 CI bounds, E2E fixes, OpenAPI + load test coverage
> Branch: main
> Total commits: 254

---

## Architecture

- **Backend**: Python 3.12+, FastAPI, asyncpg (Supabase Postgres with RLS), Celery + Redis
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, custom VA design system
- **LLM**: Hybrid — `LLMRouter` for single-turn structured output, `AgentService` (Claude Agent SDK) for multi-step tasks
- **Storage**: `ArtifactStore` (Supabase Storage or in-memory fallback) with async wrappers, tenant-scoped via `tenant_conn()`
- **Auth**: Supabase Auth + optional SAML SSO (defusedxml), ES256 JWKS JWT verification, RBAC (owner/admin/analyst/investor), auto-provisioning on first login
- **Billing**: Stripe-backed `BillingService` with plan-aware LLM quota; usage meter uses `FOR UPDATE`
- **Deployment**: Vercel (frontend at `www.virtual-analyst.ai`), API on Render (`virtual-analyst-api.onrender.com/api/v1`, free tier, cold-starts ~3–5 min)
- **Database**: Supabase PostgreSQL with pgbouncer pooler (requires `statement_cache_size=0` for asyncpg)

---

## Production Infrastructure

| Component | URL / Detail |
|-----------|-------------|
| Frontend | `https://www.virtual-analyst.ai` (Vercel) |
| Backend API | `https://virtual-analyst-api.onrender.com/api/v1` (Render) |
| Test user | `greg@disruptiveconsult.com` / `Test1234` |
| Test tenant | `f004fe0c-da81-49ab-afab-9a9a8286211e` |

---

## Current State

| Area | Metric |
|------|--------|
| Backend tests | 640+ tests, 0 failed |
| Frontend unit tests | **159 passed** across 32 test files |
| Frontend pages | **58 pages** in `(app)` route group |
| E2E tests (Playwright) | **71 spec files**, 0 failing |
| TypeScript | 0 errors (pre-existing E2E type issues only) |
| All 35 backend routers | Covered by tests |

---

## AFS Module Status (Annual Financial Statements)

> Design doc: `docs/plans/2026-02-24-afs-module-design.md`

| Phase | Description | Status |
|-------|-------------|--------|
| AFS-P1 | Framework Engine + Data Ingestion + Statement Generator | ✅ Complete |
| AFS-P2 | AI Disclosure Drafter + Prior AFS Analysis | ✅ Complete |
| AFS-P3 | Review Workflow + Tax Computation | ✅ Complete |
| AFS-P4 | Multi-entity Consolidation + iXBRL Output | ✅ Complete |
| AFS-P5 | Analytics & Industry Benchmarking | ✅ Complete |
| AFS-P6 | Custom Frameworks + Roll-forward | ✅ Complete (2026-03-15) |

- **Router**: `apps/api/app/routers/afs.py` (~52 endpoints)
- **Services**: `apps/api/app/services/afs/` (disclosure_drafter, tax_note_drafter, output_generator, analytics_ai, ratio_calculator)
- **Migrations**: 0052 (core), 0053 (sections), 0054 (reviews+tax), 0055 (consolidation+outputs)
- **Frontend**: `apps/web/app/(app)/afs/` (dashboard, setup, sections, tax, review, consolidation, output)

---

## PIM Module Status (Portfolio Intelligence Module)

> Design spec: `docs/plans/Portfolio_Intelligence_Module_Design_Spec.docx`
> Build plan v2.0: `docs/plans/2026-03-09-pim-v2-build-plan.md` (supersedes v1.0)
> Requirements spec: `docs/specs/PIM_Requirements_BuildPlan_v2.docx`
> Tech stack review: `docs/reviews/VA_Tech_Stack_Review_PIM.docx`

**Status:** 7 sprints complete. 71 backlog items across 7 sprints (Sprint 0–6).

| Sprint | Focus | Status |
|--------|-------|--------|
| Sprint 0 (2w) | Remediation — 7 gates + 16 fixes (REM-01–REM-23) | ✅ Complete |
| Sprint 1 (3w) | Sentiment Ingestion (FR-1) — Polygon.io, NewsAPI, LLM scoring | ✅ Complete — routers/pim_sentiment.py, services/pim/sentiment_ingestor.py |
| Sprint 2 (3w) | Economic Context (FR-2) — FRED integration, regime classification | ✅ Complete — services/pim/fred.py, routers/pim_universe.py |
| Sprint 3 (3w) | CIS & Markov Engine (FR-3, FR-4) — 81-state chain, QuantEcon, Numba | ✅ Complete — routers/pim_cis.py, routers/pim_markov.py |
| Sprint 4 (4w) | Portfolio Construction (FR-5) — greedy optimizer, constraints, rebalancing | ✅ Complete — routers/pim_portfolio.py, services/pim/portfolio.py |
| Sprint 5 (3w) | Backtesting (FR-6) — walk-forward, IC/ICIR/SPC, backtest studio | ✅ Complete — routers/pim_backtest.py, materialized view migrations |
| Sprint 6 (4w) | PE Benchmarking + DTF (FR-7) — DPI/TVPI/IRR, DTF-B validation | ✅ Complete — routers/pim_pe.py, routers/pim_peer.py |

**Key changes from v1.0:**
- 4 infrastructure gates dropped (Celery, Structlog, Sentry backend, CI — already implemented)
- 7 statistical standards added (SR-1–SR-7, ISA 520 compliance)
- CIS (Composite Investment Score) formula specified: FQ 35% + FM 20% + IS 25% + SM 10% + SP 10%
- DTF split: DTF-A (manual calibration) vs DTF-B (automated weekly validation)
- New procurement: Polygon.io ($29/mo), AlphaSense, MSCI Barra, Claude Sonnet

---

## Recent Changes (since last CONTEXT update)

### Sprint 8 — Platform Hardening (2026-03-16)
- CI confidence intervals for CIS and Markov steady-state
- 11 new E2E specs
- Load tests
- OpenAPI schema validation
- ruff per-file-ignores

### PIM v2.0 Build Plan (2026-03-09)
- Created comprehensive build plan at `docs/plans/2026-03-09-pim-v2-build-plan.md`
- Supersedes v1.0 (`docs/plans/2026-03-08-pim-tech-stack-build-plan.md`)
- 29 consolidated code review issues verified against codebase (5 corrections found)
- 7 PIM gates (down from 8 in v1.0 — 4 infrastructure gates already implemented)
- 71 master backlog items across 7 sprints (Sprint 0–6, ~22 weeks total)
- 7 statistical standards (SR-1–SR-7) for ISA 520 compliance
- 9 new PIM tables + 4 DTF tables + 6 LLM task labels
- DTF specification: DTF-A (manual calibration) + DTF-B (automated weekly validation)
- Updated BACKLOG.md Tiers 6-8 to match v2.0 sprint structure

### AFS Phase 5 — Analytics & Industry Benchmarking (2026-03-07)
- 5 new backend analytics endpoints in `afs.py` (compute, get analytics, get ratios, get anomalies, get going concern)
- `_analytics_id()` UUID generator + `ComputeAnalyticsBody` Pydantic model
- Parallel AI analysis via `asyncio.gather` (anomaly detection, commentary, going concern) with graceful failure handling
- Industry benchmark percentile positioning (below_p25 through above_p75)
- 18 new tests in `test_afs_analytics_api.py` — all passing
- Router now at 52 endpoints (was 44)
- H-03 board pack cron scheduler: 16 tests passing
- H-02 frontend page smoke tests: 159 tests across 32 files
- Full backend suite: 547 passed, 0 failed, 19 skipped

### a5bd4bb — Instructions Button + Drafts Fixes (2026-03-06)
- `InstructionsDrawer.tsx` + `instructions-config.ts` — floating help button on all authenticated pages, route-aware manual content for 50+ routes
- Fixed comments `entity_type` ("draft" → "draft_session") on drafts page
- Added chat retry logic for transient server errors
- Updated all 27 user manual chapters with "Page Help" subsections

### 9017b89..d681334 — Production Bug Fixes (2026-03-04 – 03-06)
- Fixed AFS 500 errors (LLM response schema `required` fields)
- Fixed Marketplace 500 errors (billing service bypass until billing module implemented)
- Improved 500 error responses with `error_message` and `error_type`
- Added X-Debug header for production error diagnostics
- Budget period date type fixes for asyncpg
- CORS fixes for primary Vercel domain + preview regex

### d681334 — Sprint 1 Security Review Fixes (2026-03-04)
- Removed temporary deploy tag from root endpoint
- CORS regex for Vercel preview deployments
- Security hardening from comprehensive review

### 62822fa — Financial Services Marketplace Templates (2026-03-04)
- Added fintech and financial services template catalog

### E2E Seed Scenario (2026-03-04)
- Full E2E test suite: 68 spec files, seeded baseline/draft/run
- 13 backend fixes across 8+ sessions (CORS, JWT, Redis, pgbouncer, tenant provisioning, etc.)
- Seeded IDs in `apps/web/e2e/functional/fixtures/seeded-ids.json`

### Round 25 (c7633fa) — Security Hardening + Router Tests
- 18 new router test files (all 35 routers now covered)
- HMAC signature verification, XSS sanitization, secrets management, safe JSON parsing
- structlog import fixes

### Round 24 (4d48540) — Backend Test Fixes
- Fixed all 25 failing tests across 9 test files
- JWT audience bug fix (python-jose 3.5.0 compat)
- XSS validation on `entity_name`

### Round 23 (33dd2e8) — P1-P10 Feature Enhancements
- Excel export UI, scenario management, run config viewer
- Dashboard enhancements, chart improvements, comparison page
- Workflow detail, version history, config viewer component

### Earlier rounds
- Round 22: Auth standardisation, multi-tenancy, board pack builder, KPI cards
- Round 21: Logger.ts, middleware, .env.example, api.boardPacks
- Round 20: Middleware auth, download fix, budget variance, ventures form
- Round 19: Pagination (13 pages), form validation (16 forms), competitive features
- Full history in BACKLOG.md completed rounds table

---

## Comprehensive Platform Review (2026-03-04)

> Full document: `docs/reviews/2026-03-04-comprehensive-platform-review.md`
> Score: 62/100 — REQUEST CHANGES
> 41 findings: 2 Critical, 17 High, 22 Medium

**7 Critical/High Priority Issues:**
1. CRIT — Unauthenticated debug endpoint leaks PII (S1)
2. HIGH — DCF lacks mid-year convention, equity bridge, EBITDA exit multiples (F1-F3)
3. CRIT — Anomaly detection entirely LLM-based, zero stats (ST1)
4. HIGH — No tax loss carryforward / NOL (F4)
5. HIGH — Monte Carlo per-sim loop, no parallelism (ST3)
6. HIGH — Single FX rate for entire consolidation horizon (F6)
7. HIGH — Auth middleware falls back to "investor" on DB error (S2)

**Sprint roadmap**: 7 sprints over 25-40 dev days (Security → DCF → Tax → Stats → Consolidation → Forecasting → Code Quality)

---

## Backlog Summary

See `BACKLOG.md` for full details.

| Tier | Status | Key Items |
|------|--------|-----------|
| Tier 1 Ship Blockers | ✅ Done | — |
| Tier 2 High Priority | ✅ H-02, H-03, H-04 done | — |
| Tier 3 Medium | ✅ All resolved | Compare scoping, budget flag, nav auth, prompt cleanup — all verified complete |
| Tier 4 AFS Module | ✅ Done | All phases complete |
| Tier 5 Nice to Have | **7 open** | Integration tests, cold-start, E2E, rate-limit, perf, monitoring, CI |
| Tier 6 PIM Gates | ✅ Done | All 7 gates closed |
| Tier 7 PIM Remediation | ✅ Done | All 23 REM items closed |
| Tier 8 PIM Module | ✅ Done | All 7 sprints complete (Sprint 0–6) |
| DTF | **In progress** | DTF-A (manual calibration) + DTF-B (automated validation) |
| Excel Add-in | **Pending** | Excel add-in integration |
| Review Findings | **29 tracked** | Consolidated in PIM v2.0 build plan (CR-S1–CR-N9) |
| Review Findings | **41 open** | 7 sprints: security, DCF, tax, stats, consolidation, forecasting, code quality |

---

## Key Files & Patterns

### Backend
- `apps/api/app/core/settings.py` — all config, production validators, agent + metrics flags. Uses `alias=` (constructor requires alias names)
- `apps/api/app/deps.py` — DI: `get_llm_router()`, `get_agent_service()`, `get_billing_service()`, `get_artifact_store()`, `require_role()`
- `apps/api/app/middleware/auth.py` — ES256 JWKS JWT verification, tenant/role resolution, auto-provisioning, structlog rebind
- `apps/api/app/middleware/security.py` — per-tenant rate limiting, security headers, Permissions-Policy
- `apps/api/app/services/agent/service.py` — `AgentService` with billing, timeout, quota
- `apps/api/app/services/llm/provider.py` — providers with SDK-aware retry (RETRYABLE_EXCEPTIONS)
- `apps/api/app/services/llm/circuit_breaker.py` — `CircuitBreaker` + `RedisCircuitBreaker`
- `shared/fm_shared/errors.py` — error hierarchy (IntegrationError, AuthError) with context in `to_dict()`
- `shared/fm_shared/storage/artifact_store.py` — sync + async methods (`load()` is synchronous — mock with `MagicMock` not `AsyncMock`)
- `shared/fm_shared/model/schemas.py` — `ModelConfig`, `BlueprintNode`, `Metadata` (HTML tag rejection on `entity_name`)

### Frontend
- `apps/web/lib/api.ts` — typed API client (~1850 lines, 18+ binding groups, 17+ AFS interfaces)
- `apps/web/lib/instructions-config.ts` — route-to-chapter mapping for 50+ routes
- `apps/web/components/InstructionsDrawer.tsx` — floating help button + slide-out drawer
- `apps/web/components/VASidebar.tsx` — navigation sidebar (SETUP, CONFIGURE, ANALYZE, REPORT groups)
- `apps/web/components/ui/` — VAButton, VACard, VATabs, VABadge, VAInput, VASpinner, etc.
- `apps/web/tailwind.config.ts` — design tokens: va-midnight, va-blue, va-panel, va-border, glow shadows

### Design System
- Dark theme: `bg-va-midnight`, `text-va-text`, accent `va-blue`
- Fonts: Sora (brand), Inter (sans), JetBrains Mono (mono)
- Border radius: va-xs(6px) through va-xl(24px)
- Glow shadows: `va-glow-blue`, `va-glow-violet`

### Documentation
- User manual: `docs/user-manual/` (26 chapters + glossary, all with "Page Help" subsections)
- Comprehensive review: `docs/reviews/2026-03-04-comprehensive-platform-review.md`
- Tech stack review (PIM): `docs/reviews/VA_Tech_Stack_Review_PIM.docx`
- AFS design doc: `docs/plans/2026-02-24-afs-module-design.md`
- PIM design spec: `docs/plans/Portfolio_Intelligence_Module_Design_Spec.docx`
- PIM build plan: `docs/plans/2026-03-08-pim-tech-stack-build-plan.md`

---

## Conventions

- Python 3.12+, type annotations, ruff-clean (E, F, I, N, W, UP, B, S)
- Pydantic `BaseModel` for all request bodies, `Field` with aliases for settings
- `tenant_conn(tenant_id)` async context manager for all DB access (RLS enforced)
- `structlog` for logging, domain errors (`LLMError`, `StorageError`, `IntegrationError`, `AuthError`)
- List endpoints return `{"items": [...], "total": N, "limit": N, "offset": N}`
- Frontend: Next.js App Router, Tailwind, VA design system, `fetchApi()` wrapper, strict TypeScript
- Auth pattern: `getAuthContext()` → redirect to `/login` if null, then `api.setAccessToken(ctx.accessToken)`
- pgbouncer: Must set `statement_cache_size=0` on all asyncpg connections (Supabase pooler in transaction mode)

---

## Testing Notes

- Settings constructor in tests must use alias names: `Settings(SUPABASE_JWT_SECRET=..., ENVIRONMENT="test")`
- `tenant_conn` patch target: `apps.api.app.db.connection.tenant_conn` or `apps.api.app.routers.<router>.tenant_conn`
- Dev RBAC fallback: `ROLE_ANALYST` when no JWT secret; teams/billing routers require `OWNER_OR_ADMIN` — patch `deps.ROLE_ANALYST` to `"owner"` for validation tests
- LLM providers create real API clients in `__init__` — construct provider INSIDE `with patch` block
- Billing `get_settings` patch target: `apps.api.app.core.settings.get_settings` (lazy import in webhook handler)
- `ArtifactStore.load()` is synchronous — mock with `MagicMock`, not `AsyncMock`
- Frontend tests: stable router refs in `tests/pages/setup.tsx` to prevent useEffect infinite loops
- E2E: seeded IDs in `apps/web/e2e/functional/fixtures/seeded-ids.json`
