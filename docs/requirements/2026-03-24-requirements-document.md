# Virtual Analyst — Requirements Document

> Version: 1.0 · Generated: 2026-03-24
> Platform: AI-powered financial modeling and portfolio intelligence
> Audience: Internal development team, product owner, design partners
> Status: Living document — update after each sprint

## Version History

| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-03-24 | Claude Code | Initial generation from source documents + live codebase audit |

---

## 3.2 Executive Summary

Virtual Analyst is an AI-powered financial modeling and portfolio intelligence platform built for accountants, financial analysts, and investment professionals operating primarily in the African mid-market and fintech sectors. It combines deterministic financial engines (DCF, Monte Carlo simulation, three-statement generation) with large-language-model-assisted analysis, narrative drafting, and portfolio scoring. The platform is deployed as a multi-tenant SaaS on Vercel (frontend) and Render (API), backed by Supabase PostgreSQL with row-level security.

The platform evolved in three distinct phases from its February 2026 baseline. The original Phase 1 scope established the core financial modeling engine: a DAG-based calculation graph, three-statement generation, DCF valuation, Monte Carlo simulation, KPI calculation, and Supabase authentication with RBAC. A comprehensive code and financial review conducted on 2026-03-04 (score: 62/100) identified seven critical and high-priority gaps — including missing mid-year DCF convention, LLM-only anomaly detection, no tax loss carryforward, and a security vulnerability in auth middleware. All seven gap items were resolved as Sprint 0 pre-conditions before PIM development began.

The platform then expanded in two parallel directions. The Annual Financial Statements (AFS) module (Phases 1–6, completed 2026-03-15) adds AI-powered AFS generation with multi-framework compliance (IFRS, IFRS-SME, US GAAP, SA GAAP), disclosure drafting via LLM + RAG, multi-stage review workflows, tax computation (IAS 12 / ASC 740), iXBRL output, multi-entity consolidation, and analytics with statistical anomaly detection. The Portfolio Intelligence Module (PIM, Sprints 0–6, completed 2026-03-16) adds an 81-state Markov chain portfolio scoring model, multi-source sentiment ingestion (Polygon.io + NewsAPI), FRED economic indicators, Composite Investment Score (CIS) computation, portfolio construction with greedy optimisation and constraint enforcement, walk-forward backtesting, and PE benchmarking with DPI/TVPI/IRR.

The key design principles are: (1) deterministic engines + LLM narrative — quantitative outputs are always computed deterministically, with LLM used only for interpretation and narrative; (2) multi-tenant by default — all data is scoped by `tenant_id` via Supabase RLS and the `tenant_conn()` async context manager; (3) security-first — no hardcoded secrets, ES256 JWKS JWT verification with `asyncio.Lock` and 1h TTL cache, 503 on DB error instead of silent role fallback, XSS escaping on all HTML output.

As of 2026-03-25, the platform is in active production at `www.virtual-analyst.ai` with 640+ passing tests across 38 backend routers, 60 frontend pages, 71 Playwright E2E specs, and 0 TypeScript errors. The hosted API runs on Render free tier with cold-start mitigation via a 14-minute keepalive cron. Known constraints include generous performance thresholds in test files to accommodate CI environment variability and Render cold-start latency. The billing module (Stripe integration) is the primary planned feature that remains deferred post-beta by product decision.

---

## 3.3 Stakeholders & User Roles

| Role | Description | Access Level |
|------|-------------|-------------|
| Owner | Tenant admin; manages team members, all analytical features, billing | All features |
| Admin | Team management + all analytical features | All except billing |
| Analyst | Core financial modeling, AFS, PIM | Core + AFS + PIM |
| Investor | Read-only dashboards and reports | Read-only |

---

## 3.4 Functional Requirements

### FR-AUTH — Authentication & RBAC

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-AUTH-01 | Supabase Auth JWT verification with ES256 JWKS, `asyncio.Lock`, 1h TTL cache, and `httpx.AsyncClient` (no blocking calls) | ✅ Done | [REVIEW-2026-03-04] CR-S4 |
| FR-AUTH-02 | RBAC roles: owner / admin / analyst / investor, enforced per-endpoint via `require_role()` | ✅ Done | [ORIGINAL] |
| FR-AUTH-03 | Auto-provisioning of tenant record on first login (no manual admin step) | ✅ Done | [ORIGINAL] |
| FR-AUTH-04 | Return HTTP 503 on DB connectivity failure during role lookup — no silent fallback to "investor" | ✅ Done | [REVIEW-2026-03-04] CR-S3 |
| FR-AUTH-05 | Optional SAML SSO via `defusedxml` (enterprise SSO, disabled by default) | ✅ Done | [ORIGINAL] |

### FR-CORE — Financial Modeling Engine

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-CORE-01 | DAG-based financial model engine: topological sort, cycle detection (`GraphCycleError`), deterministic `CalcGraph.from_blueprint` | ✅ Done | [ORIGINAL] |
| FR-CORE-02 | Safe AST evaluator for user-defined formulas — no arbitrary code execution; `EvalError` on invalid expressions | ✅ Done | [ORIGINAL] |
| FR-CORE-03 | Three-statement generation: Income Statement, Balance Sheet, Cash Flow Statement with funding waterfall (up to 5 passes) | ✅ Done | [ORIGINAL] |
| FR-CORE-04 | KPI calculation: margins, FCF yield, CCC, working capital ratios, debt coverage ratios | ✅ Done | [ORIGINAL] |
| FR-CORE-05 | DCF valuation with mid-year convention (`(t+0.5)/12.0` discount exponent), equity bridge (`enterprise_value − net_debt + cash = equity_value`), and EBITDA-based exit multiple fallback | ✅ Done | [REVIEW-2026-03-04] CR-F1/F2/F3 |
| FR-CORE-06 | Monte Carlo simulation with `ProcessPoolExecutor` parallelism above `PARALLEL_THRESHOLD=50`; vectorised percentile output (P5–P95); reproducible seeded RNG | ✅ Done | [REVIEW-2026-03-04] CR-T1 |
| FR-CORE-07 | Sensitivity analysis: one-way, two-way, tornado charts; `ProcessPoolExecutor` for parallel parameter sweeps; `_validate_path()` denylist guard | ✅ Done | [ORIGINAL] |
| FR-CORE-08 | Tax loss carryforward (NOL): cumulative `nol_balance` tracks losses; `nol_offset` reduces taxable income in profitable periods (IAS 12 / ASC 740) | ✅ Done | [REVIEW-2026-03-04] CR-F4 |
| FR-CORE-09 | Multi-entity consolidation: full, proportional, equity method; NCI per period; `FxRate = float | list[float]` for per-period IAS 21-compliant FX rates | ✅ Done | [REVIEW-2026-03-04] CR-F5 |
| FR-CORE-10 | Budget module: actuals import, variance analysis, period templates, `is_revenue` flag for revenue/cost line classification, reforecast agent | ✅ Done | [ORIGINAL] |
| FR-CORE-11 | Scenario management: scenario overrides applied at run time against a baseline model config | ✅ Done | [ORIGINAL] |
| FR-CORE-12 | Versioned baselines with `ArtifactStore` (Supabase Storage or in-memory fallback); path `{tenant_id}/{artifact_type}/{id}.json` | ✅ Done | [ORIGINAL] |

### FR-AFS — Annual Financial Statements

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-AFS-01 | Framework engine: pre-built frameworks (IFRS, IFRS-SME, US GAAP, SA GAAP); version management for standard updates | ✅ Done | [AFS-SPEC] |
| FR-AFS-02 | Custom and AI-inferred frameworks: user uploads own disclosure checklist, or describes requirements in NL for AI to generate a custom framework dynamically | ✅ Done | [AFS-SPEC] AFS-P6 |
| FR-AFS-03 | Trial balance ingestion: VA baselines/runs, Excel/CSV upload, Xero/QuickBooks connectors; AI-assisted account mapping | ✅ Done | [AFS-SPEC] |
| FR-AFS-04 | AI disclosure drafter: section-by-section NL prompting, LLM generation using RAG over standards, iteration loop, section locking | ✅ Done | [AFS-SPEC] AFS-P2 |
| FR-AFS-05 | Prior AFS analysis: PDF extraction + structured Excel; discrepancy detection between PDF and Excel sources; resolution workflow with audit trail | ✅ Done | [AFS-SPEC] AFS-P2 |
| FR-AFS-06 | Review workflow: multi-stage sign-off (draft → preparer → manager → partner), version control, audit trail, redlining, `needs_review` flag | ✅ Done | [AFS-SPEC] AFS-P3 |
| FR-AFS-07 | Tax computation: current + deferred tax (IAS 12 / ASC 740), temporary differences, tax reconciliation note, deferred tax asset/liability classification | ✅ Done | [AFS-SPEC] AFS-P3 |
| FR-AFS-08 | iXBRL / XBRL output for regulatory filing: CIPC (SA) and SEC (US) tagging profiles | ✅ Done | [AFS-SPEC] AFS-P4 |
| FR-AFS-09 | Multi-entity consolidation within AFS: aggregate trial balances, intercompany eliminations, minority interests, currency translation | ✅ Done | [AFS-SPEC] AFS-P4 |
| FR-AFS-10 | Roll-forward: auto-populate comparatives from prior period; carry forward prior-year disclosure notes with flags for required updates | ✅ Done | [AFS-SPEC] AFS-P6 |
| FR-AFS-11 | AFS analytics: ratio analysis, YoY trends, industry benchmarking (percentile positioning), statistical anomaly detection (IQR/Z-score per ISA 520), going concern indicators | ✅ Done | [AFS-SPEC] AFS-P5 |
| FR-AFS-12 | XSS hardening: `html.escape()` applied to all user-controlled strings in HTML output paths | ✅ Done | [REVIEW-2026-03-04] |
| FR-AFS-13 | JSON resilience: graceful degradation on malformed LLM JSON responses; safe parsing with fallback rather than 500 error | ✅ Done | [EMERGENT] |

### FR-PIM — Portfolio Intelligence Module

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-PIM-01 | Sentiment ingestion: Polygon.io news API + SEC EDGAR filings; LLM sentiment scoring (`pim_sentiment_extraction`, temp=0.1); per-company score in [-1, +1] with confidence in [0, 1]; Celery-scheduled refresh (6h default) | ✅ Done | [PIM-SPEC] Sprint 1 |
| FR-PIM-02 | Economic context: FRED API (GDP, CPI, unemployment, yield curve, ISM PMI); regime classification (expansion/contraction/transition); monthly snapshots in `pim_economic_snapshots` | ✅ Done | [PIM-SPEC] Sprint 2 |
| FR-PIM-03 | Composite Investment Score (CIS): weighted sum of 5 sub-scores — Fundamental Quality 35%, Fundamental Momentum 20%, Idiosyncratic Sentiment 25%, Sentiment Momentum 10%, Sector Positioning 10%; each sub-score normalised to [0, 100] before weighting | ✅ Done | [PIM-SPEC] Sprint 3 |
| FR-PIM-04 | Markov chain engine: 81-state space (3 levels × 4 dimensions); transition matrix via QuantEcon `MarkovChain`; Laplace smoothing (alpha=1) for zero-count transitions (SR-4); Numba JIT on inner loops | ✅ Done | [PIM-SPEC] Sprint 3 |
| FR-PIM-05 | Analytical confidence intervals on CIS (`ci_lower`/`ci_upper`) and Dirichlet CI on Markov steady-state probabilities (81-element CI arrays); graceful null when n<3 (SR-3, PIM-7.7) | ✅ Done | [PIM-SPEC] Sprint 8 |
| FR-PIM-06 | Portfolio construction (FR-5): greedy top-N selection ranked by CIS; configurable constraints (max position size, sector caps, min liquidity); portfolio run snapshot (holdings, weights, CIS scores); manual and scheduled rebalancing | ✅ Done | [PIM-PORTFOLIO] Sprint 4 |
| FR-PIM-07 | Backtesting: walk-forward backtest; IC and ICIR computation; strategy comparison vs benchmark and equal-weight; no look-ahead bias (SR-2); materialised views for IC/ICIR/SPC | ✅ Done | [PIM-SPEC] Sprint 5 |
| FR-PIM-08 | PE benchmarking: fund CRUD (vintage year, commitment, drawdowns, distributions); DPI/TVPI/IRR per fund and per vintage year; J-curve analysis; peer comparison vs benchmark percentiles; LLM PE memo (`pim_pe_memo`, temp=0.4); venture-stage overlay | ✅ Done | [PIM-SPEC] Sprint 6 |
| FR-PIM-09 | DTF-A: manual Markov calibration CLI (`tools/dtf/calibrate.py`) for developer parameter tuning; calibration run history in `dtf_calibration_runs` | ✅ Done | [PIM-SPEC] |
| FR-PIM-10 | DTF-B: automated weekly IC validation (`tools/dtf/weekly_validator.py`); prediction vs actual outcomes tracked in `dtf_prediction_outcomes` | ✅ Done | [PIM-SPEC] |
| FR-PIM-11 | PIM billing gate: `pim_enabled` per-tenant flag in `billing_plans` table; `require_pim_access` dependency returns HTTP 403 when disabled | ✅ Done | [PIM-SPEC] |
| FR-PIM-12 | Required SR-6 limitations disclosure on all PIM reports: model-based estimates, no investment advice, Markov stationarity assumption | ✅ Done | [PIM-SPEC] SR-6 |

### FR-AGENT — Agentic Features

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-AGENT-01 | LLMRouter: single-turn structured output with Pydantic response models, calibrated temperatures per task label, circuit breaker, retry with backoff | ✅ Done | [ORIGINAL] |
| FR-AGENT-02 | AgentService: multi-step agentic tasks via Claude Agent SDK; billing quota enforcement; timeout management | ✅ Done | [ORIGINAL] |
| FR-AGENT-03 | Budget NL query agent: natural language questions over budget data translated to structured queries | ✅ Done | [ORIGINAL] |
| FR-AGENT-04 | Excel ingestion agent: parse uploaded Excel workbooks and map to model config via AI-assisted account matching | ✅ Done | [ORIGINAL] |
| FR-AGENT-05 | Reforecast agent: AI-driven reforecast generation from actuals + NL instructions | ✅ Done | [ORIGINAL] |
| FR-AGENT-06 | Draft session agent: multi-step drafting workflows with version history and changeset tracking | ✅ Done | [ORIGINAL] |

### FR-EXCEL — Excel Add-in

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-EXCEL-01 | Pull: fetch model binding data from VA API and write cell values to active Excel workbook via `Excel.run` | ✅ Done | [EMERGENT] |
| FR-EXCEL-02 | Push: read current cell values from named ranges via `Excel.run` and send changes back to VA API | ✅ Done | [EMERGENT] |
| FR-EXCEL-03 | Connection selector: dropdown to choose the VA connection/model to bind the workbook to | ✅ Done | [EMERGENT] |
| FR-EXCEL-04 | Graceful degradation: all `Excel.run` calls are wrapped in try/catch; add-in remains functional outside Office context with console warnings only | ✅ Done | [EMERGENT] |

### FR-INFRA — Infrastructure & Operations

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-INFRA-01 | Multi-tenant Supabase RLS: all tables scoped by `current_setting('app.tenant_id')`; `tenant_conn(tenant_id)` async context manager enforces isolation | ✅ Done | [ORIGINAL] |
| FR-INFRA-02 | Per-tenant rate limiting: configurable limits enforced by `security.py` middleware; 429 response with tenant context | ✅ Done | [REVIEW-2026-03-04] |
| FR-INFRA-03 | Celery + Redis async workers: `redis.asyncio` for all async operations; DLQ with max 10,000 entries; beat schedule for sentiment refresh (6h) and economic context (monthly) | ✅ Done | [ORIGINAL] |
| FR-INFRA-04 | Board pack generation: PDF/PPTX export of financial dashboards; scheduled email distribution via SendGrid | ✅ Done | [ORIGINAL] |
| FR-INFRA-05 | OpenAPI schema + TypeScript codegen: `openapi-typescript@7.13` generates typed API bindings; `generate:api` script in `package.json` | ✅ Done | [REVIEW-2026-03-04] |
| FR-INFRA-06 | Keepalive cron: GitHub Actions workflow (`keepalive.yml`) pings `/api/v1/health/live` every 14 minutes to mitigate Render free-tier cold starts | ✅ Done | [EMERGENT] |
| FR-INFRA-07 | Sentry observability: `sentry-sdk[fastapi]` on backend; `@sentry/nextjs` on frontend (server, client, edge configs); DSN-gated | ✅ Done | [REVIEW-2026-03-04] |
| FR-INFRA-08 | Health endpoint: `GET /api/v1/health/live` (liveness), structured response with `status` (healthy/degraded/unhealthy), `store`, and connectivity sub-checks | ✅ Done | [EMERGENT] |
| FR-INFRA-09 | CI pipeline: ruff, black, mypy, Safety, pytest, vitest, `npm run type-check`, ESLint, Trivy Docker image scan, hosted health check job | ✅ Done | [ORIGINAL] |
| FR-INFRA-10 | Integration test environment: `docker-compose.test.yml` with isolated Postgres on port 5433; `scripts/run-integration-tests.sh`; GitHub service container in CI | ✅ Done | [ORIGINAL] |
| FR-INFRA-11 | Structlog structured logging: used across 30+ backend files; correlation IDs bound per request | ✅ Done | [ORIGINAL] |

### FR-UX — Frontend & Navigation

| ID | Requirement | Status | Source |
|----|-------------|--------|--------|
| FR-UX-01 | VA design system: dark theme with `va-midnight`/`va-blue`/`va-panel`/`va-border` tokens; Sora (brand), Inter (sans), JetBrains Mono (mono) fonts; glow shadows | ✅ Done | [ORIGINAL] |
| FR-UX-02 | VASidebar: SETUP, CONFIGURE, ANALYZE, REPORT, AFS, INTELLIGENCE navigation groups; active route highlighting; sign-out via shared `signOut()` | ✅ Done | [ORIGINAL] |
| FR-UX-03 | InstructionsDrawer: floating help button on all authenticated pages; route-aware manual content mapped across ch01–ch34 (covering all modules including PIM Sprint 6) | ✅ Done | [ORIGINAL] |
| FR-UX-04 | 60 authenticated pages in `(app)` route group (Next.js 14 App Router); includes AFS dashboard, PIM dashboards, PE hub, backtest studio | ✅ Done | [ORIGINAL] |
| FR-UX-05 | Excel add-in taskpane: Office JS-based task pane with pull/push/connection UI; Office-agnostic graceful degradation | ✅ Done | [EMERGENT] |

---

## 3.5 Non-Functional Requirements

| ID | Category | Requirement | Source | Status |
|----|----------|-------------|--------|--------|
| NFR-01 | Performance | Monte Carlo P95 latency: no dedicated MC threshold in load test file; `ProcessPoolExecutor` activated above `PARALLEL_THRESHOLD=50`; sequential fallback for smaller runs | [REVIEW-2026-03-04] | ✅ Done (parallelism implemented; explicit latency threshold not captured in `tests/load/test_api_performance.py`) |
| NFR-02 | Performance | PIM economic/snapshots endpoint P95 < 500ms; PIM markov/states P95 < 600ms; PE assessments P95 < 500ms; backtest results P95 < 500ms — generous thresholds for CI stability on Render free tier | [PIM-SPEC] | ✅ Done — actual thresholds from `tests/load/test_api_performance.py` lines 145, 178, 211, 243 |
| NFR-03 | Performance | Health/live P95 < 50ms; connectors list P95 < 100ms; OpenAPI schema P95 < 200ms | [EMERGENT] | ✅ Done — from `tests/load/test_api_performance.py` lines 53, 67, 81 |
| NFR-04 | Security | No hardcoded secrets — all secrets via environment variables; `.env*.local` in `.gitignore`; `get_settings()` with `@lru_cache` | [ORIGINAL] | ✅ Done |
| NFR-05 | Security | XSS prevention: `html.escape()` on all user-controlled strings in HTML output paths; `entity_name` HTML tag rejection in Pydantic validator | [REVIEW-2026-03-04] | ✅ Done |
| NFR-06 | Security | SQL injection prevention: parameterised queries only via asyncpg; no f-string SQL in production code paths | [ORIGINAL] | ✅ Done |
| NFR-07 | Reliability | HTTP 503 on DB failure during auth role lookup — no silent role downgrade to "investor" | [REVIEW-2026-03-04] | ✅ Done |
| NFR-08 | Reliability | JWKS cache with `asyncio.Lock` and 1h TTL — no per-request JWKS fetch race condition under concurrent load | [REVIEW-2026-03-04] | ✅ Done |
| NFR-09 | Accuracy | AFS balance check: `assets == liabilities + equity` or discrepancy flagged; `StatementImbalanceError` if cash flow closing balance drift > 0.01 | [AFS-SPEC] | ✅ Done |
| NFR-10 | Accuracy | Monte Carlo reproducible seeding: seed value logged per run for audit trail; deterministic output for same seed | [REVIEW-2026-03-04] | ✅ Done |
| NFR-11 | Accuracy | Monetary values: `Decimal` types or explicit rounding; no raw `float` accumulation for money | [ORIGINAL] | ✅ Done |
| NFR-12 | Scalability | Markov transition matrix: row sums == 1.0 +/- 1e-9; Laplace smoothing (alpha=1) ensures no zero-probability rows (SR-4) | [PIM-SPEC] | ✅ Done |
| NFR-13 | Coverage | Backend test coverage: 640+ tests across 38 routers; 0 failed; integration tests gated by `INTEGRATION_TESTS=1` | [ORIGINAL] | ✅ Done |
| NFR-14 | Coverage | Frontend: 274 tests across 86 Vitest test files; 71 Playwright E2E specs; 0 TypeScript errors | [ORIGINAL] | ✅ Done |
| NFR-15 | Compliance | IAS/ISA/CFA standards cited in docstrings for all financial calculations (IAS 12, IAS 21, IAS 7, ISA 520, ISA 570, CFA Level II DCF) | [REVIEW-2026-03-04] | ✅ Done |
| NFR-16 | Observability | Sentry captures all unhandled exceptions on backend (`sentry-sdk[fastapi]`) and frontend (`@sentry/nextjs`); both DSN-gated | [REVIEW-2026-03-04] | ✅ Done |
| NFR-17 | Compliance | PIM outputs must include SR-6 verbatim limitations disclosure on all reports; PE memo must include disclaimer (validated in OpenAPI schema tests) | [PIM-SPEC] | ✅ Done |

---

## 3.6 Delta Analysis — Original vs. Current

### Added (not in original Phase 1 scope)

| Requirement | Module | Source | Sprint Added |
|-------------|--------|--------|--------------|
| AI Disclosure Drafter (NL section prompting, LLM + RAG generation) | AFS | [AFS-SPEC] | AFS-P2 |
| Prior AFS Analysis (PDF extraction, source reconciliation, discrepancy resolution) | AFS | [AFS-SPEC] | AFS-P2 |
| Multi-stage Review Workflow (draft to preparer to manager to partner) | AFS | [AFS-SPEC] | AFS-P3 |
| Tax Computation (current + deferred, IAS 12 / ASC 740) | AFS | [AFS-SPEC] | AFS-P3 |
| iXBRL / XBRL regulatory output (CIPC, SEC) | AFS | [AFS-SPEC] | AFS-P4 |
| Custom & AI-inferred frameworks + roll-forward | AFS | [AFS-SPEC] | AFS-P6 |
| Statistical anomaly detection (IQR/Z-score pre-screening, ISA 520) | AFS | [REVIEW-2026-03-04] | Sprint 0 (GATE-1) |
| Sentiment Ingestion Engine (Polygon.io, NewsAPI, LLM scoring, Celery) | PIM | [PIM-SPEC] | PIM Sprint 1 |
| Economic Context Module (FRED API, regime classification) | PIM | [PIM-SPEC] | PIM Sprint 2 |
| Composite Investment Score (CIS, 5-factor weighted model) | PIM | [PIM-SPEC] | PIM Sprint 3 |
| 81-State Markov Chain (QuantEcon + Numba JIT) | PIM | [PIM-SPEC] | PIM Sprint 3 |
| CI bounds on CIS and Markov steady-state (Dirichlet CI, SR-3) | PIM | [PIM-SPEC] | PIM Sprint 8 |
| Portfolio Construction / Portfolio Function (greedy optimizer, constraints, rebalancing, transaction cost model) | PIM | [PIM-PORTFOLIO] | PIM Sprint 4 |
| Walk-forward Backtesting (IC/ICIR/SPC, no look-ahead bias, SR-2/SR-7) | PIM | [PIM-SPEC] | PIM Sprint 5 |
| PE Benchmarking (DPI/TVPI/IRR, J-curve, peer comparison) | PIM | [PIM-SPEC] | PIM Sprint 6 |
| Developer Testing Framework DTF-A + DTF-B | PIM | [PIM-SPEC] | PIM Sprint 6 |
| Excel Add-in (Push/Pull, connection selector) | EXCEL | [EMERGENT] | Post-Phase 1 |
| InstructionsDrawer with route-aware manual (ch01–ch34) | UX | [EMERGENT] | Round 23 |
| OpenAPI schema + TypeScript codegen | INFRA | [REVIEW-2026-03-04] | Sprint 0 |
| Sentry frontend integration (`@sentry/nextjs`) | INFRA | [REVIEW-2026-03-04] | Sprint 0 |
| Keepalive cron (GitHub Actions, 14-min interval) | INFRA | [EMERGENT] | N-02 |
| Docker Compose integration test environment | INFRA | [ORIGINAL] | N-01 |
| Per-tenant rate limiting middleware | INFRA | [REVIEW-2026-03-04] | Round 25 |
| AgentService multi-step agentic workflows (Claude Agent SDK) | AGENT | [ORIGINAL] | Phase 2+ |
| SAML SSO via defusedxml (optional enterprise auth) | AUTH | [ORIGINAL] | Phase 2+ |

### Changed (in original scope, but spec evolved)

| Original Requirement | Original Spec | Current Implementation | Reason for Change |
|---------------------|---------------|----------------------|-------------------|
| DCF terminal value | Simple Gordon Growth Model; exit multiple applied to FCF | Mid-year convention `(t+0.5)/12.0`; equity bridge; EBITDA-based exit multiple when `ebitda_series` provided | [REVIEW-2026-03-04] CR-F1/F2/F3 — financial accuracy |
| Auth middleware DB error handling | Silently fall back to "investor" role | Return HTTP 503; no role granted on DB failure | [REVIEW-2026-03-04] CR-S3 — security least-privilege |
| JWKS verification | Synchronous `httpx.get()` per request; no lock | `asyncio.Lock` + 1h TTL cache; `httpx.AsyncClient` | [REVIEW-2026-03-04] CR-S4 — concurrency safety |
| Monte Carlo simulation | Sequential Python for-loop over all sims | `ProcessPoolExecutor` above threshold of 50 sims | [REVIEW-2026-03-04] CR-T1 — performance |
| AFS anomaly detection | Purely LLM-based (no quantitative criteria) | IQR/Z-score statistical pre-screening + LLM for narrative only | [REVIEW-2026-03-04] CR-S2 — ISA 520 compliance |
| Tax calculation in multi-year models | `tax = max(0.0, ebt * tax_rate)` — no carryforward | NOL accumulation with `nol_balance` tracker; `nol_used` offsets future EBT | [REVIEW-2026-03-04] CR-F4 — IAS 12 compliance |
| Multi-entity consolidation FX | Single scalar avg/closing rate for all periods | `FxRate = float | list[float]` union type for per-period arrays | [REVIEW-2026-03-04] CR-F5 — IAS 21 compliance |
| budgets router (single file) | One 1,618-line god file | Split into 5-file package: `crud.py`, `periods.py`, `templates.py`, `analytics.py`, `_common.py` | [REVIEW-2026-03-04] CR-Q2 — maintainability |
| afs router (single file) | One 2,657-line god file | Split into 10-file package across `routers/afs/` | [REVIEW-2026-03-04] CR-Q3 — maintainability |
| Frontend run status enum | Frontend checked `"completed"` for export button | Aligned to `"succeeded"` backend enum; export button renders correctly | [REVIEW-2026-03-04] CR-Q4 — bug fix |

### Deferred (planned but not yet implemented)

| Requirement | Source | Reason Deferred | Sprint Target |
|-------------|--------|-----------------|---------------|
| Billing / Stripe integration | [ORIGINAL] VA_Master_Build_Plan | Deferred post-beta by product decision; `BillingService` skeleton exists with bypasses | TBD |
| WACC calculator (CAPM-based: Rf + Beta × ERP) | [REVIEW-2026-03-04] F11 | Medium priority; WACC is input-only currently | TBD |
| Declining balance depreciation (IAS 16) | [REVIEW-2026-03-04] F12 | Schema supports it; implementation uses straight-line only | TBD |
| Interest/tax separate disclosure in OCF (IAS 7.35) | [REVIEW-2026-03-04] F13 | Medium priority | TBD |
| Altman Z' and Z'' variants (private company / non-manufacturing) | [REVIEW-2026-03-04] F9 | Medium priority; original Z-score implemented | TBD |
| Morris global sensitivity analysis (captures parameter interactions) | [REVIEW-2026-03-04] ST6 | High effort; OAT sensitivity is implemented | TBD |
| Statistical forecasting (ARIMA, Holt-Winters, MAPE/RMSE) | [REVIEW-2026-03-04] ST7 | Reforecast agent uses LLM; statistical methods not implemented | TBD |
| Antithetic variates for MC variance reduction | [REVIEW-2026-03-04] ST9 | Nice-to-have; core MC parallelism is done | TBD |
| MC convergence diagnostics + standard errors | [REVIEW-2026-03-04] ST10 | Nice-to-have | TBD |
| EV distribution from Monte Carlo (DCF + MC integration) | [REVIEW-2026-03-04] ST13 | Medium effort | TBD |
| Proper CTA calculation with historical equity component rates | [REVIEW-2026-03-04] F14 | Complex; current CTA is simplified | TBD |
| IFRS 11 joint venture / joint operation distinction | [REVIEW-2026-03-04] F7 | Proportional consolidation implemented; IFRS 11 distinction not enforced | TBD |
| D3.js Markov state-transition diagram (PIM FR-4.7) | [PIM-SPEC] | Should-priority; Recharts used currently | TBD |
| AlphaSense earnings transcript ingestion (Tier 2 sentiment) | [PIM-SPEC] | Post-launch; Polygon.io (Tier 1) implemented | TBD |

### Removed (was planned, dropped)

| Requirement | Source | Reason Removed |
|-------------|--------|----------------|
| Unauthenticated `debug-auth` endpoint (`GET /api/v1/health/debug-auth`) | [REVIEW-2026-03-04] S1 (CRITICAL) | Exposed PII in production; removed immediately in Sprint 1 security fix |

---

## 3.7 Open Requirements (not yet implemented)

Based on the live codebase audit, the following requirements from source documents are confirmed NOT yet implemented:

| ID | Description | Source | Effort | Blocking Dependencies |
|----|-------------|--------|--------|-----------------------|
| OPEN-01 | WACC calculator: CAPM-based (`Re = Rf + Beta x ERP`; full capital structure weighting) | [REVIEW-2026-03-04] F11 | M | None; input-only WACC works today |
| OPEN-02 | Declining balance depreciation: schema field exists (`depreciation_method`) but code always uses straight-line | [REVIEW-2026-03-04] F12 | S | None |
| OPEN-03 | Interest paid + taxes paid as separate OCF line items (IAS 7.35 / ASC 230-10-45-25) | [REVIEW-2026-03-04] F13 | S | None |
| OPEN-04 | Altman Z' (private company, 1983) and Z'' (non-manufacturing, 1993) variants in AFS ratio calculator | [REVIEW-2026-03-04] F9 | S | None |
| OPEN-05 | Morris screening global sensitivity analysis (captures parameter interaction effects) | [REVIEW-2026-03-04] ST6 | L | None; OAT sensitivity is done |
| OPEN-06 | Statistical forecasting: linear regression trend, Holt-Winters exponential smoothing, MAPE/RMSE accuracy reporting | [REVIEW-2026-03-04] ST7 | L | None |
| OPEN-07 | Monte Carlo convergence diagnostics: rolling P50 stability check, standard errors on percentile estimates | [REVIEW-2026-03-04] ST10 | M | None |
| OPEN-08 | EV distribution output from Monte Carlo: run DCF per simulation, collect P5/P50/P95 of enterprise value | [REVIEW-2026-03-04] ST13 | M | FR-CORE-05 (DCF) already done |
| OPEN-09 | Proper CTA calculation with historical rates for equity components (IAS 21.41) | [REVIEW-2026-03-04] F14 | M | Multi-period FX (FR-CORE-09) done |
| OPEN-10 | IFRS 11 joint arrangement distinction: enforce equity method for joint ventures vs proportional for joint operations | [REVIEW-2026-03-04] F7 | M | FR-CORE-09 (consolidation) done |
| OPEN-11 | Billing / Stripe integration: plan-aware LLM quota enforcement (skeleton exists in `BillingService`; Marketplace bypasses billing) | [ORIGINAL] | XL | Product decision (post-beta) |
| OPEN-12 | D3.js interactive Markov state-transition diagram on PIM frontend (FR-4.7 Should priority) | [PIM-SPEC] | M | FR-PIM-04 (Markov engine) done |
| OPEN-13 | AlphaSense earnings transcript ingestion (Tier 2 sentiment source, FR-1 Should priority) | [PIM-SPEC] | L | FR-PIM-01 (Tier 1) done |
| OPEN-14 | Antithetic variates for Monte Carlo variance reduction (30–50% variance reduction at near-zero cost) | [REVIEW-2026-03-04] ST9 | S | None |

---

## 3.8 Emergent Requirements (implemented but not in any source document)

The following requirements appear in the codebase but were not explicitly specified in any source document. They represent pragmatic engineering decisions made during development.

| ID | Description | Where Found | Rationale |
|----|-------------|-------------|-----------|
| EMRG-01 | Excel add-in: full Pull/Push/connection-selector implementation in `apps/excel-addin/taskpane.js` | `apps/excel-addin/taskpane.js` | Enables model data exchange with Excel without requiring users to write API calls manually |
| EMRG-02 | Graceful Excel.run degradation: all `Excel.run` calls wrapped in try/catch with console.warn fallback | `taskpane.js:126,181` | Add-in must remain usable in testing environments without Office context |
| EMRG-03 | Keepalive cron via GitHub Actions (`keepalive.yml`, every 14 min) | `.github/workflows/keepalive.yml` | Mitigates Render free-tier 3–5 min cold starts; not in any spec document |
| EMRG-04 | Health endpoint degraded state: returns HTTP 200 with `status: "degraded"` when downstream dependencies are unreachable (rather than 503) | `apps/api/app/routers/health.py` | Matches startup warning behaviour; API remains available when dependencies are slow |
| EMRG-05 | JSON resilience in LLM response parsing: safe parse with graceful degradation on malformed output | Multiple AFS service files | LLM outputs occasionally produce invalid JSON; hard 500 errors are unacceptable in AFS workflows |
| EMRG-06 | InstructionsDrawer with 34 user manual chapters (ch01–ch34), floating help button on all authenticated pages | `InstructionsDrawer.tsx`, `instructions-config.ts` | Reduces support burden for self-serve users; not in any design spec |
| EMRG-07 | `parameter_path` traversal denylist in sensitivity analysis (`_MAX_PATH_DEPTH=5`, `_PATH_DENYLIST` frozenset) | `shared/fm_shared/analysis/sensitivity.py` | Hardening against model traversal abuse; denylist was already present but explicitly strengthened |
| EMRG-08 | HMAC signature verification for webhook endpoints | `apps/api/app/routers/` (Round 25) | Board-pack and integration webhooks require request authenticity verification |
| EMRG-09 | `X-Debug` header in 500 error responses for production diagnostics | `apps/api/app/main.py` | Enables production debugging without exposing full stack traces publicly |
| EMRG-10 | pgbouncer compatibility: `statement_cache_size=0` on all asyncpg connections | `apps/api/app/db/connection.py` | Required for Supabase pgbouncer in transaction mode; not documented in original schema design |
| EMRG-11 | `secrets` module (HMAC) + `safe_json_parse()` helper for secure request verification | Round 25 hardening | Security hardening beyond what any spec required |
| EMRG-12 | Billing service bypass for Marketplace until billing module is implemented (prevents 500 errors on marketplace endpoints) | `apps/api/app/routers/marketplace.py` | Pragmatic workaround enabling Marketplace UI before billing is complete |

---

## 3.9 Constraints & Assumptions

| Constraint | Impact |
|-----------|--------|
| Render free tier (cold starts ~3–5 min) | Keepalive cron required (EMRG-03); performance thresholds in load tests are generous (500–600ms P95 for PIM endpoints in CI) |
| Supabase pgbouncer transaction mode | `statement_cache_size=0` required on all asyncpg connections (EMRG-10); prepared statement caching is disabled |
| Numba `@njit` (pure functions only) | Markov hot loop must contain no Python objects in the critical path; only numeric types allowed inside Numba-compiled functions |
| pg_partman partitioned tables (PIM sentiment and economic tables) | PIM queries must include the partition key in WHERE clauses for performance; missing partition key causes full-table scans across all partitions |
| Billing deferred post-beta | No Stripe integration in any sprint plan; `BillingService` skeleton exists with bypasses; `pim_enabled` gate is enforced, but billing plans table managed manually |
| LLM outputs are non-deterministic | All financial figures in AFS disclosures are deterministically checked against trial balance; LLM is used only for narrative, never for numbers |
| ProcessPoolExecutor requires serialisable functions | Monte Carlo simulation functions must be defined at module level (`_run_single_sim`); no closures or lambda functions in the parallel path |
| FRED/Polygon.io API keys optional | PIM economic and sentiment modules degrade gracefully when API keys are absent; mock/static data used in development |
| Supabase RLS enforcement | All DB queries must go through `tenant_conn(tenant_id)` context manager — direct pool access bypasses RLS and is never used in production code |

---

## 3.10 Glossary

| Term | Definition |
|------|-----------|
| AFS | Annual Financial Statements module — AI-powered multi-framework AFS generation with disclosure drafting, review workflow, tax computation, and iXBRL output |
| AST | Abstract Syntax Tree — used in the safe formula evaluator to execute user-defined model formulas without arbitrary code execution |
| CCC | Cash Conversion Cycle (Days Inventory Outstanding + Days Sales Outstanding minus Days Payable Outstanding) |
| CIS | Composite Investment Score — per-company portfolio score: Fundamental Quality 35% + Fundamental Momentum 20% + Idiosyncratic Sentiment 25% + Sentiment Momentum 10% + Sector Positioning 10%; normalised to [0, 100] |
| CTA | Cumulative Translation Adjustment — equity reserve for FX translation differences on consolidation (IAS 21.41) |
| DAG | Directed Acyclic Graph — the dependency graph underlying the financial model engine; topological sort determines calculation order |
| DCF | Discounted Cash Flow valuation using mid-year convention, equity bridge, and EBITDA-based exit multiple (CFA Level II standard) |
| DPI | Distributions to Paid-In capital — PE performance metric |
| DTF | Developer Testing Framework: DTF-A (manual Markov calibration CLI at `tools/dtf/calibrate.py`) + DTF-B (automated weekly IC validation at `tools/dtf/weekly_validator.py`) |
| EV | Enterprise Value = PV of explicit FCFs + PV of terminal value |
| IC | Information Coefficient — Spearman rank correlation between CIS-ranked predictions and actual investment outcomes; key PIM backtesting metric |
| ICIR | Information Coefficient Information Ratio — IC divided by standard deviation of IC; measures signal consistency |
| iXBRL | Inline eXtensible Business Reporting Language — machine-readable regulatory filing format (CIPC for SA, SEC for US) |
| JWKS | JSON Web Key Set — ES256 public key endpoint at `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` for JWT signature verification |
| NOL | Net Operating Loss — tax loss carryforward tracked in `nol_balance`; offsets future taxable income per IAS 12 / ASC 740 |
| NCI | Non-Controlling Interest — minority interest in consolidated entities not fully owned by the parent |
| PIM | Portfolio Intelligence Module — AI-powered portfolio scoring, sentiment ingestion, Markov chain state modelling, backtesting, and PE benchmarking |
| PIM-PORTFOLIO | Portfolio Function (FR-5 in PIM build plan Sprint 4) — greedy CIS-ranked top-N optimizer, configurable constraint engine (position size, sector caps, liquidity), scheduled and manual rebalancing, transaction cost model |
| RBAC | Role-Based Access Control — four roles: owner / admin / analyst / investor |
| RLS | Row-Level Security — Supabase/Postgres feature enforcing tenant isolation via `current_setting('app.tenant_id')` |
| SR-1 to SR-7 | Statistical Requirements from PIM build plan: ISA 520 compliance (SR-1), no look-ahead bias (SR-2), CI bounds on estimates (SR-3), Laplace smoothing (SR-4), 2-sigma SPC threshold (SR-5), limitations disclosure (SR-6), transaction cost reporting (SR-7) |
| TVPI | Total Value to Paid-In capital — PE performance metric (DPI + RVPI) |
| WACC | Weighted Average Cost of Capital — currently input-only; CAPM-based calculator is a deferred requirement (OPEN-01) |
