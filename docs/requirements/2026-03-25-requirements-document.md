# Virtual Analyst — Requirements Document
> Version: 1.0 · Generated: 2026-03-25
> Platform: AI-powered financial modeling and portfolio intelligence
> Audience: Internal development team, product owner, design partners
> Status: Living document — update after each sprint

## Version History
| Version | Date | Author | Summary of Changes |
|---------|------|--------|-------------------|
| 1.0 | 2026-03-25 | Claude Code | Initial generation from source documents + live codebase audit |

---

## 1. Executive Summary

Virtual Analyst (VA) is an AI-powered financial modeling and portfolio intelligence platform that combines deterministic financial engines (DCF, Monte Carlo, budgeting, three-statement models) with LLM-assisted analysis for accountants, financial analysts, and investment professionals. The platform is built as a monorepo with a Python/FastAPI backend, Next.js 14 frontend, and Supabase PostgreSQL database with row-level security.

The platform evolved from a Phase 1 core (February 2026) covering baselines, runs, three-statement generation, and KPI calculation into a comprehensive financial platform with two major module additions: the Annual Financial Statements (AFS) module (6 phases, all complete) and the Portfolio Intelligence Module (PIM) with 81-state Markov chain scoring, CIS composite scoring, sentiment ingestion, and PE benchmarking (7 sprints, all complete). A comprehensive platform review (2026-03-04, score 62/100) identified 41 findings which drove a remediation backlog (REM-01 through REM-23) — all now resolved.

Key design principles include: tenant-scoped RLS on all database tables, async-first Python with asyncpg, LLM-assisted but deterministically grounded analytics (ISA 520 compliance), and a clear separation between deterministic financial engines (`shared/fm_shared/`) and AI-augmented services (`apps/api/app/services/`). The frontend follows a custom VA design system (dark theme, Sora/Inter/JetBrains Mono fonts, VA component library).

As of Sprint 8 (2026-03-16), the platform has 973 passing backend tests, 68 frontend pages, 71 Playwright E2E specs, 38+ backend routers (all test-covered), and is deployed to production at `www.virtual-analyst.ai` (Vercel) with the API on Render. All Tier 1-3 ship blockers, AFS phases 1-6, PIM sprints 0-6, and Tier 5 nice-to-have items are complete. Remaining work includes DTF (Developer Testing Framework) completion, Excel add-in polish, and select review findings from the comprehensive platform review that were deferred beyond Sprint 8.

---

## 2. Stakeholders & User Roles

| Role | Description | Access Level |
|------|-------------|-------------|
| Owner | Tenant administrator, manages team, billing, and platform configuration | Full CRUD on all resources, billing management, team administration |
| Admin | Senior user with broad access for managing models, approvals, and AFS | Full CRUD on most resources, approval authority, no billing access |
| Analyst | Primary user building models, running analyses, drafting AFS, and using PIM | CRUD on own resources, run models, draft AFS, PIM analytics |
| Investor | Read-only stakeholder viewing reports, dashboards, and board packs | Read-only access to shared reports, dashboards, and board packs |

---

## 3. Functional Requirements

### 3.1 FR-AUTH — Authentication & RBAC

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-AUTH-01 | Supabase Auth integration with SSR (client + server + middleware) for login, session management, and protected routes | Done | [ORIGINAL] |
| FR-AUTH-02 | Optional SAML SSO via defusedxml for enterprise identity provider federation | Done | [REVIEW-2026-03-04] |
| FR-AUTH-03 | ES256 JWKS JWT verification with asyncio.Lock, 1-hour TTL cache, and httpx.AsyncClient to prevent race conditions | Done | [PIM-SPEC] |
| FR-AUTH-04 | RBAC with four roles (owner, admin, analyst, investor) enforced via `require_role()` dependency | Done | [ORIGINAL] |
| FR-AUTH-05 | Auto-provisioning of user record on first login via auth middleware | Done | [ORIGINAL] |
| FR-AUTH-06 | Return 503 Service Unavailable on DB connectivity failure during role lookup (no silent fallback) | Done | [REVIEW-2026-03-04] |

### 3.2 FR-CORE — Financial Modeling Engine

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-CORE-01 | DAG-based calculation engine with topological sort, cycle detection (`GraphCycleError`), and safe AST evaluator | Done | [ORIGINAL] |
| FR-CORE-02 | DCF valuation with mid-year convention (`(t+0.5)/12.0`), equity bridge (net_debt, cash, equity_value), and EBITDA-based exit multiples | Done | [REVIEW-2026-03-04] |
| FR-CORE-03 | Monte Carlo simulation with ProcessPoolExecutor parallelism above PARALLEL_THRESHOLD=50, seeded RNG, and percentile aggregation (P5-P95) | Done | [REVIEW-2026-03-04] |
| FR-CORE-04 | Three-statement generation (IS/BS/CF) with funding waterfall (5-pass convergence), debt schedules (PIK, grace, convertible, ABL), capex/depreciation, working capital, and dividend policy | Done | [ORIGINAL] |
| FR-CORE-05 | KPI calculation: margins, ratios, FCF, CCC from BS/IS data | Done | [ORIGINAL] |
| FR-CORE-06 | Multi-entity consolidation with IAS 21 FX translation (per-period rate arrays via `FxRate = float | list[float]`), full/proportional/equity methods, intercompany elimination, and NCI | Done | [REVIEW-2026-03-04] |
| FR-CORE-07 | Sensitivity analysis with ProcessPoolExecutor parallelism, parameter path denylist (`_MAX_PATH_DEPTH=5`, `_PATH_DENYLIST` frozenset), and one-at-a-time OAT method | Done | [ORIGINAL] |
| FR-CORE-08 | NOL tax loss carryforward with cumulative balance tracking and offset against future EBT | Done | [REVIEW-2026-03-04] |
| FR-CORE-09 | Budget module with CRUD, variance analysis, actuals tracking, NL queries via LLM, and `is_revenue` flag | Done | [ORIGINAL] |
| FR-CORE-10 | Multiples-based valuation (comparable company analysis) with min/max implied EV range | Done | [ORIGINAL] |
| FR-CORE-11 | WACC calculator (CAPM-based cost of equity computation) | Deferred | [REVIEW-2026-03-04] |
| FR-CORE-12 | Declining balance depreciation method (schema defined but implementation uses straight-line only) | Partial | [REVIEW-2026-03-04] |
| FR-CORE-13 | Global sensitivity analysis via Morris screening or Sobol indices | Open | [REVIEW-2026-03-04] |
| FR-CORE-14 | Statistical forecasting methods (ARIMA, Holt-Winters, regression) with MAPE/RMSE metrics | Open | [REVIEW-2026-03-04] |
| FR-CORE-15 | Variance reduction techniques for Monte Carlo (antithetic variates, stratified sampling) | Open | [REVIEW-2026-03-04] |
| FR-CORE-16 | Convergence diagnostics for Monte Carlo (rolling P50 stability, `convergence_achieved` flag) | Open | [REVIEW-2026-03-04] |

### 3.3 FR-AFS — Annual Financial Statements

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-AFS-01 | Framework engine supporting IFRS (full), IFRS for SMEs, US GAAP, SA Companies Act/GAAP, and custom frameworks with disclosure schema JSON and statement templates | Done | [AFS-SPEC] |
| FR-AFS-02 | Trial balance ingestion from VA baselines, Excel/CSV upload, and PDF extraction with AI-assisted account mapping | Done | [AFS-SPEC] |
| FR-AFS-03 | AI disclosure drafter using LLM + RAG over accounting standards for section-by-section NL-prompted draft generation with iteration loop | Done | [AFS-SPEC] |
| FR-AFS-04 | Prior AFS analysis: upload prior-year PDF or Excel, AI extraction of sections/notes, dual-source reconciliation with discrepancy resolution | Done | [AFS-SPEC] |
| FR-AFS-05 | Multi-stage review workflow (draft, preparer review, manager review, partner sign-off) with version control, comments, and lock/unlock | Done | [AFS-SPEC] |
| FR-AFS-06 | Tax computation: current/deferred tax, temporary differences, tax reconciliation, and AI-generated tax note (IAS 12 / ASC 740) | Done | [AFS-SPEC] |
| FR-AFS-07 | iXBRL output generation with XBRL namespace declarations, `<ix:nonFraction>` tags, and taxonomy mapping (IFRS/US GAAP) | Done | [AFS-SPEC] |
| FR-AFS-08 | Multi-entity consolidation linking AFS engagement to org-structure with intercompany elimination and consolidated trial balance | Done | [AFS-SPEC] |
| FR-AFS-09 | AFS analytics: 16 financial ratios from trial balance, industry benchmarking with percentile positioning, YoY trends | Done | [AFS-SPEC] |
| FR-AFS-10 | Statistical anomaly detection (IQR + Z-score) pre-screening before LLM narrative — ISA 520 compliant | Done | [REVIEW-2026-03-04] |
| FR-AFS-11 | Going concern assessment with quantitative risk indicators fed to LLM for narrative | Done | [AFS-SPEC] |
| FR-AFS-12 | AI-inferred custom frameworks from natural language description of jurisdiction/requirements | Done | [AFS-SPEC] |
| FR-AFS-13 | Roll-forward of sections and comparatives from prior engagement into new engagement with `rolled_forward_from` tracking | Done | [AFS-SPEC] |
| FR-AFS-14 | Output generation in PDF (WeasyPrint), DOCX (python-docx), and iXBRL formats with cover page, TOC, and branding | Done | [AFS-SPEC] |
| FR-AFS-15 | XSS hardening on entity names (HTML tag rejection in `Metadata` schema) and input sanitization | Done | [EMERGENT] |
| FR-AFS-16 | JSON resilience: structured output from LLM parsed defensively with fallback error logging | Done | [EMERGENT] |
| FR-AFS-17 | YTD management accounts missing-month extrapolation via NL-described projection basis | Done | [AFS-SPEC] |

### 3.4 FR-PIM — Portfolio Intelligence Module

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-PIM-01 | Sentiment ingestion from Polygon.io news API with LLM sentiment scoring ([-1, +1] with confidence), weekly/monthly aggregation, and Celery-scheduled refresh | Done | [PIM-SPEC] |
| FR-PIM-02 | Economic context module: FRED API integration (5+ indicators), regime classification (expansion/contraction/transition), monthly snapshots | Done | [PIM-SPEC] |
| FR-PIM-03 | Composite Investment Score (CIS): 5-factor weighted sum (FQ 35%, FM 20%, IS 25%, SM 10%, SP 10%), normalised to [0, 100], with analytical CI bounds (ci_lower/ci_upper/ci_method) | Done | [PIM-SPEC] |
| FR-PIM-04 | 81-state Markov chain engine (3 levels x 4 dimensions), Laplace smoothing, QuantEcon steady-state, Numba JIT on hot loops, Dirichlet CI on steady-state probabilities | Done | [PIM-SPEC] |
| FR-PIM-05 | Portfolio construction: greedy top-N selection ranked by CIS, configurable constraints (max position, sector caps, min liquidity), rebalancing, portfolio run snapshots | Done | [PIM-SPEC] |
| FR-PIM-06 | Walk-forward backtesting with IC/ICIR/SPC metrics, strategy comparison (PIM vs benchmark vs equal-weight), no look-ahead bias (SR-2), transaction cost reporting (SR-7) | Done | [PIM-SPEC] |
| FR-PIM-07 | PE benchmarking: fund assessment CRUD (DPI/TVPI/IRR), J-curve analysis, peer comparison, venture-stage overlay, LLM PE memo generation with SR-6 limitations disclosure | Done | [PIM-SPEC] |
| FR-PIM-08 | PIM billing gate: `pim_enabled` per tenant, `check_pim_access` middleware returning HTTP 403 when disabled, LLM usage metered via billing service quota | Done | [PIM-SPEC] |
| FR-PIM-09 | PE hub summary widget and board pack PE portfolio section (HTML + PPTX) | Done | [EMERGENT] |
| FR-PIM-10 | D3.js Markov state-transition diagram visualisation on frontend | Deferred | [PIM-SPEC] |
| FR-PIM-11 | AlphaSense earnings transcript sentiment (Tier 2 data source) | Deferred | [PIM-SPEC] |
| FR-PIM-12 | Social media sentiment (Twitter/Reddit APIs, Tier 3 data source) | Deferred | [PIM-SPEC] |

### 3.5 FR-AGENT — Agentic Features

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-AGENT-01 | LLMRouter: task-label routing with provider fallback, structured JSON output, calibrated temperatures, and circuit breaker | Done | [ORIGINAL] |
| FR-AGENT-02 | AgentService: Claude Agent SDK integration for multi-step tasks with billing, timeout, and quota enforcement | Done | [ORIGINAL] |
| FR-AGENT-03 | Budget natural language queries: NL-to-SQL and NL-to-analysis via LLM in budgets module | Done | [ORIGINAL] |
| FR-AGENT-04 | Excel ingestion agent: AI-powered parsing of uploaded Excel files into structured model configurations | Done | [ORIGINAL] |
| FR-AGENT-05 | Reforecast agent: LLM-assisted budget reforecasting with trend detection | Done | [ORIGINAL] |
| FR-AGENT-06 | PIM sentiment extraction via `pim_sentiment_extraction` label (temp=0.1) | Done | [PIM-SPEC] |
| FR-AGENT-07 | PIM factor attribution narrative via `pim_factor_attribution` label (temp=0.2) | Done | [PIM-SPEC] |
| FR-AGENT-08 | AFS disclosure drafting via `afs_disclosure_draft` label with iteration loop | Done | [AFS-SPEC] |
| FR-AGENT-09 | AFS tax note generation via `afs_tax_note` label (IAS 12 / ASC 740) | Done | [AFS-SPEC] |

### 3.6 FR-EXCEL — Excel Add-in

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-EXCEL-01 | Pull operation: fetch connection bindings from API and write values into Excel cells via `Excel.run` | Done | [ORIGINAL] |
| FR-EXCEL-02 | Push operation: read current cell values from Excel and post updates back to API endpoint | Done | [ORIGINAL] |
| FR-EXCEL-03 | Connection dropdown: dynamic loading of available connections per tenant with auto-refresh | Done | [ORIGINAL] |
| FR-EXCEL-04 | Graceful degradation: `Excel.run` failures caught and logged without crashing the taskpane | Done | [ORIGINAL] |

### 3.7 FR-INFRA — Infrastructure & Operations

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-INFRA-01 | Multi-tenant RLS via `current_setting('app.tenant_id', true)` on all tables with 4 policies per table (select/insert/update/delete) | Done | [ORIGINAL] |
| FR-INFRA-02 | Per-tenant rate limiting via security middleware with 429 response | Done | [ORIGINAL] |
| FR-INFRA-03 | Celery + Redis async worker for background tasks (sentiment refresh, board pack scheduling) | Done | [ORIGINAL] |
| FR-INFRA-04 | Board pack generation with cron scheduling, email distribution (SendGrid), and HTML/PPTX export | Done | [ORIGINAL] |
| FR-INFRA-05 | OpenAPI schema with TypeScript codegen (`openapi-typescript@7.13`, `generate:api` script) | Done | [PIM-SPEC] |
| FR-INFRA-06 | Render keepalive cron (`keepalive.yml`) pinging `/api/v1/health/live` every 14 minutes | Done | [EMERGENT] |
| FR-INFRA-07 | Sentry integration: backend via `sentry-sdk[fastapi]`, frontend via `@sentry/nextjs` (server/client/edge configs, DSN-gated) | Done | [EMERGENT] |
| FR-INFRA-08 | Health endpoint (`/api/v1/health/live`) for production monitoring | Done | [ORIGINAL] |
| FR-INFRA-09 | CI pipeline: ruff, black, mypy, Safety, pytest, vitest, tsc, ESLint, Docker, Trivy scan, hosted health check | Done | [EMERGENT] |
| FR-INFRA-10 | OIDC/SAML SSO integration via Supabase Auth + defusedxml | Done | [ORIGINAL] |
| FR-INFRA-11 | Docker Compose test environment (`docker-compose.test.yml`) with isolated Postgres on port 5433 | Done | [EMERGENT] |
| FR-INFRA-12 | Stripe-backed billing service with plan-aware LLM quota and `FOR UPDATE` usage metering | Done | [ORIGINAL] |

### 3.8 FR-UX — Frontend & Navigation

| ID | Description | Status | Source |
|----|-------------|--------|--------|
| FR-UX-01 | VA design system: dark theme (`bg-va-midnight`), custom tokens, Sora/Inter/JetBrains Mono fonts, VA component library (VAButton, VACard, VATabs, VABadge, VAInput, VASelect, VASpinner, VAPagination) | Done | [ORIGINAL] |
| FR-UX-02 | VASidebar with 6 navigation groups: SETUP, AFS, CONFIGURE, ANALYZE, INTELLIGENCE, REPORT | Done | [ORIGINAL] |
| FR-UX-03 | InstructionsDrawer: floating help button on all authenticated pages with route-aware manual content for 50+ routes (chapters 01-34) | Done | [EMERGENT] |
| FR-UX-04 | 68 pages in `(app)` route group covering all modules (dashboard, baselines, drafts, runs, budgets, AFS, PIM, board packs, settings, etc.) | Done | [ORIGINAL] |
| FR-UX-05 | Excel add-in taskpane with connection dropdown, Pull/Push buttons, and status display | Done | [ORIGINAL] |
| FR-UX-06 | Pagination and filtering on 13 list pages | Done | [ORIGINAL] |
| FR-UX-07 | Form validation on 16 forms with error display | Done | [ORIGINAL] |

---

## 4. Non-Functional Requirements

| ID | Category | Requirement | Source | Status |
|----|----------|-------------|--------|--------|
| NFR-01 | Performance | Monte Carlo endpoint P95 latency: mocked tests use 500ms threshold (generous for CI) | [PIM-SPEC] | Done |
| NFR-02 | Performance | CIS economic snapshots endpoint P95 latency < 500ms (mocked, generous CI threshold) | [PIM-SPEC] | Done |
| NFR-03 | Performance | Health endpoint P95 latency < 50ms | [ORIGINAL] | Done |
| NFR-04 | Performance | Connectors list P95 latency < 100ms | [ORIGINAL] | Done |
| NFR-05 | Performance | OpenAPI schema P95 latency < 200ms | [ORIGINAL] | Done |
| NFR-06 | Performance | 10 concurrent health requests complete within 1s total | [ORIGINAL] | Done |
| NFR-07 | Performance | Markov states endpoint P95 < 600ms (mocked, generous CI threshold) | [PIM-SPEC] | Done |
| NFR-08 | Performance | PE assessments endpoint P95 < 500ms (mocked, generous CI threshold) | [PIM-SPEC] | Done |
| NFR-09 | Performance | Backtest results endpoint P95 < 500ms (mocked, generous CI threshold) | [PIM-SPEC] | Done |
| NFR-10 | Security | All API keys, tokens, and credentials via environment variables only; no hardcoded secrets | [ORIGINAL] | Done |
| NFR-11 | Security | HMAC signature verification, XSS sanitization, safe JSON parsing | [EMERGENT] | Done |
| NFR-12 | Reliability | Async Redis (`redis.asyncio`) to prevent event loop blocking | [REVIEW-2026-03-04] | Done |
| NFR-13 | Observability | structlog for all backend logging; Sentry for error tracking (backend + frontend) | [EMERGENT] | Done |
| NFR-14 | Compliance | ISA 520 compliance: all analytical procedures must have statistical basis (expectation, threshold, investigation) | [PIM-SPEC] | Done |
| NFR-15 | Compliance | SR-6 limitations disclosure on all PIM reports (verbatim text specified in PIM spec) | [PIM-SPEC] | Done |
| NFR-16 | Testing | 973+ backend tests passing, 68+ frontend pages, 71 E2E specs, all 38+ routers test-covered | [EMERGENT] | Done |
| NFR-17 | Data Integrity | pgbouncer transaction mode requires `statement_cache_size=0` on all asyncpg connections | [ORIGINAL] | Done |
| NFR-18 | Reproducibility | Monte Carlo: seeded RNG logged for audit trail; deterministic reproducibility across all statistical functions | [ORIGINAL] | Done |

---

## 5. Delta Analysis — Phase 1 Baseline to Current

### 5.1 Added (not in original Phase 1 scope)

| Requirement | Module | Source | Sprint Added |
|------------|--------|--------|-------------|
| AFS module (6 phases, 52+ endpoints, 12 tables, 10+ pages) | FR-AFS | [AFS-SPEC] | AFS P1-P6 |
| PIM module (8 routers, 9 tables, 7 sprints, Markov/CIS/sentiment/PE) | FR-PIM | [PIM-SPEC] | PIM Sprint 0-6 |
| Statistical anomaly detection (IQR/Z-score pre-screening) | FR-AFS-10 | [REVIEW-2026-03-04] | Sprint 0 |
| NOL tax loss carryforward | FR-CORE-08 | [REVIEW-2026-03-04] | Sprint 1 |
| DCF mid-year convention, equity bridge, EBITDA exit multiples | FR-CORE-02 | [REVIEW-2026-03-04] | Sprint 0 |
| Monte Carlo ProcessPoolExecutor parallelism | FR-CORE-03 | [REVIEW-2026-03-04] | Sprint 0 |
| Per-period FX rates for IAS 21 consolidation | FR-CORE-06 | [REVIEW-2026-03-04] | Sprint 1 |
| InstructionsDrawer with route-aware help (34 chapters) | FR-UX-03 | [EMERGENT] | Instructions round |
| Sentry frontend + backend integration | FR-INFRA-07 | [EMERGENT] | N-07 |
| Keepalive cron for Render cold-start mitigation | FR-INFRA-06 | [EMERGENT] | N-02 |
| CI pipeline enhancements (ESLint, vitest, Trivy, health check) | FR-INFRA-09 | [EMERGENT] | N-08 |
| Docker Compose integration test environment | FR-INFRA-11 | [EMERGENT] | N-01 |
| OpenAPI TypeScript codegen | FR-INFRA-05 | [PIM-SPEC] | REM-22 |
| PE board pack section (HTML + PPTX) | FR-PIM-09 | [EMERGENT] | Sprint 7 |
| CIS analytical confidence intervals | FR-PIM-03 | [PIM-SPEC] | Sprint 8 |
| Markov Dirichlet CI on steady-state | FR-PIM-04 | [PIM-SPEC] | Sprint 8 |

### 5.2 Changed (in original scope, but spec evolved)

| Original Requirement | Original Spec | Current Implementation | Reason for Change |
|---------------------|--------------|----------------------|-------------------|
| DCF valuation | Period-end discounting, FCF exit multiple, EV only | Mid-year convention, EBITDA exit multiple, equity bridge | Comprehensive review (2026-03-04) identified CFA non-compliance |
| Monte Carlo simulation | Sequential for-loop per simulation | ProcessPoolExecutor with PARALLEL_THRESHOLD=50 | Performance: single-threaded loop untenable for PIM backtesting |
| Consolidation FX rates | Single scalar avg/closing rate | `FxRate = float | list[float]` per-period rate arrays | IAS 21.39-40 compliance per comprehensive review |
| Auth middleware DB error | Silent fallback to "investor" role | Returns 503 Service Unavailable | Security: prevents unauthorized data access during DB outage |
| Anomaly detection | Entirely LLM-based | IQR + Z-score statistical pre-screening, then LLM narrative | ISA 520 compliance: must have deterministic statistical basis |
| `budgets.py` router | Single 1,618-line file | Split into 6-file package (`budgets/`) | Code quality: SRP violation identified in review |
| `afs.py` router | Single 2,657-line file | Split into 10-file package (`afs/`) | Code quality: SRP violation identified in review |
| RunStatus enum | Frontend used "completed", backend used "succeeded" | Aligned to "succeeded" with CHECK constraint on runs table | Bug fix: Excel export button never appeared |
| Tax computation | `tax = max(0.0, ebt * tax_rate)` with no NOL | NOL carryforward with cumulative balance, offset, and tracking | IAS 12 / ASC 740 compliance |

### 5.3 Deferred (planned but not implemented)

| Requirement | Source | Reason Deferred | Sprint Target |
|------------|--------|----------------|---------------|
| WACC calculator (CAPM-based Re + Rd) | [REVIEW-2026-03-04] | Medium priority; WACC is input-only for now | Post-beta |
| Global sensitivity analysis (Morris/Sobol) | [REVIEW-2026-03-04] | Complex implementation; OAT sufficient for current use cases | Post-beta |
| Statistical forecasting (ARIMA, Holt-Winters) | [REVIEW-2026-03-04] | Requires time-series infrastructure not yet built | Post-beta |
| MC variance reduction (antithetic variates) | [REVIEW-2026-03-04] | Medium priority; ProcessPoolExecutor parallelism addressed immediate performance needs | Post-beta |
| MC convergence diagnostics | [REVIEW-2026-03-04] | Nice-to-have; results currently useful without convergence flag | Post-beta |
| D3.js Markov state diagram | [PIM-SPEC] | Frontend visualisation; core analytics functional without it | Post-beta |
| AlphaSense sentiment (Tier 2 source) | [PIM-SPEC] | Procurement dependency; Polygon.io provides sufficient coverage for launch | Post-beta |
| Social media sentiment (Tier 3 source) | [PIM-SPEC] | Low priority; API stability concerns with Twitter/Reddit | Future |
| Declining balance depreciation | [REVIEW-2026-03-04] | Schema defined but only straight-line implemented; low user demand | Backlog |
| DTF-A manual calibration CLI | [PIM-SPEC] | Agent spec exists but no production code yet | In progress |
| DTF-B automated weekly validation | [PIM-SPEC] | Depends on DTF-A completion | In progress |
| Goodness-of-fit testing for distribution selection | [REVIEW-2026-03-04] | Statistical enhancement; current manual selection sufficient | Post-beta |
| EV distribution from Monte Carlo | [REVIEW-2026-03-04] | DCF and MC modules not yet integrated for per-simulation EV | Post-beta |

### 5.4 Removed (was planned, dropped)

No requirements have been formally removed. All original Phase 1 scope items remain implemented. Deferred items in Section 5.3 are postponed, not dropped.

---

## 6. Open Requirements (genuinely not implemented)

The following requirements are confirmed NOT yet implemented based on codebase verification:

1. **FR-CORE-11** — WACC calculator: No CAPM-based computation exists; WACC is a user-provided input only.
2. **FR-CORE-13** — Global sensitivity analysis (Morris screening / Sobol indices): Only OAT analysis exists in `sensitivity.py`.
3. **FR-CORE-14** — Statistical forecasting methods: No ARIMA, Holt-Winters, or regression trend analysis modules exist.
4. **FR-CORE-15** — MC variance reduction: No antithetic variates or stratified sampling implemented in `monte_carlo.py`.
5. **FR-CORE-16** — MC convergence diagnostics: No `convergence_achieved` flag or rolling P50 stability check in `MCResult`.
6. **FR-PIM-10** — D3.js Markov state-transition diagram: PIM Markov pages exist but use standard Recharts, not D3.js interactive diagrams.
7. **FR-PIM-11** — AlphaSense sentiment source: Not implemented; only Polygon.io is active.
8. **FR-PIM-12** — Social media sentiment source: Not implemented.
9. **FR-CORE-12** — Declining balance depreciation: Schema allows `"declining_balance"` value but `statements.py` always applies straight-line.
10. **DTF-A / DTF-B** — Developer Testing Framework: Agent spec at `.claude/agents/dtf-engineer.md` but no production tables or code.

---

## 7. Emergent Requirements (implemented but not in any source doc)

The following requirements were found in the codebase but do not appear in the original Phase 1 baseline, AFS design docs, PIM build plan, or comprehensive review:

| Requirement | Module | Evidence |
|------------|--------|----------|
| HMAC signature verification on webhooks | FR-INFRA | Security hardening in Round 25 (`c7633fa`) |
| XSS sanitization on entity names (HTML tag rejection in `Metadata` schema) | FR-AFS | `schemas.py` validation; Round 24 (`4d48540`) |
| Safe JSON parsing utilities | FR-INFRA | Round 25 security hardening |
| InstructionsDrawer floating help with 34 chapters of route-aware content | FR-UX | `a5bd4bb` — not in any spec, built as UX enhancement |
| Keepalive cron via GitHub Actions (`keepalive.yml`) | FR-INFRA | Render cold-start mitigation; not in any spec |
| Docker Compose test environment for isolated integration testing | FR-INFRA | `docker-compose.test.yml` + `scripts/run-integration-tests.sh` |
| Trivy Docker security scan in CI pipeline | FR-INFRA | CI enhancement N-08 |
| ruff per-file-ignores for S101 in test files | FR-INFRA | Sprint 8 tooling improvement |
| PE hub summary widget API endpoint | FR-PIM | Sprint 7 — not in original PIM spec |
| Board pack PE portfolio section (HTML + PPTX) | FR-PIM | Sprint 7 — not in original PIM spec |
| Venture overlay on PE detail page | FR-PIM | Sprint 7 — links Ventures module to PE benchmarking |
| OpenAPI schema validation tests for PIM endpoints | FR-INFRA | Sprint 8 N-05 extension |
| Load/performance tests for PIM endpoints (4 new P95 tests) | FR-INFRA | Sprint 8 N-06 extension |
| Financial services marketplace template catalog | FR-UX | Round `62822fa` — marketplace templates for fintech |
| structlog rebind in auth middleware for request-scoped logging | FR-INFRA | Auth middleware improvement |

---

## 8. Constraints & Assumptions

| Constraint | Impact |
|-----------|--------|
| Render free tier (API hosting) | Cold starts of 3-5 minutes; mitigated by keepalive cron every 14 minutes; no guaranteed uptime SLA |
| Supabase pgbouncer in transaction mode | Requires `statement_cache_size=0` on all asyncpg connections; prevents prepared statement caching |
| Numba `@njit` for Markov hot loops | JIT-compiled functions must be pure (no Python objects in hot path); first invocation has compilation overhead |
| pg_partman for PIM time-series tables | Queries must include partition key; partition maintenance required |
| Billing deferred post-beta | Stripe billing service exists with `FOR UPDATE` metering but full billing enforcement is not production-gated yet |
| Single-tenant frontend (session user.id as tenant) | No multi-tenant UI switcher; frontend uses session `user.id` as tenant_id |
| PIM data sources require API keys | Polygon.io ($29/mo) and FRED API keys are optional; modules degrade gracefully when absent |
| LLM cost | Claude Sonnet and GPT-4o calls metered via billing service; cost per AFS draft or PIM memo not capped beyond plan quota |

---

## 9. Glossary

| Term | Definition |
|------|-----------|
| AFS | Annual Financial Statements — module for generating compliant financial statements with AI-assisted disclosure drafting |
| CIS | Composite Investment Score — PIM's 5-factor weighted score (FQ 35%, FM 20%, IS 25%, SM 10%, SP 10%) normalised to [0, 100] per company |
| DCF | Discounted Cash Flow — valuation method computing PV of explicit FCFs + terminal value; implemented with mid-year convention and equity bridge |
| DTF | Developer Testing Framework — calibration (DTF-A) and automated weekly validation (DTF-B) framework for PIM model parameters |
| IC | Information Coefficient — correlation between predicted and realised returns, used in PIM backtest evaluation |
| ICIR | IC Information Ratio — IC divided by its standard deviation; measures signal consistency |
| iXBRL | Inline eXtensible Business Reporting Language — machine-readable regulatory filing format for financial statements (CIPC in SA, SEC in US) |
| JWKS | JSON Web Key Set — public key set used for ES256 JWT verification; cached with asyncio.Lock and 1-hour TTL |
| NOL | Net Operating Loss — cumulative tax losses carried forward to offset future taxable income (IAS 12 / ASC 740) |
| PIM | Portfolio Intelligence Module — AI-powered portfolio analytics with sentiment, Markov chain, CIS scoring, backtesting, and PE benchmarking |
| PIM-PORTFOLIO | FR-5 in PIM spec: portfolio construction via greedy top-N CIS selection with configurable constraints (max position, sector caps, min liquidity), rebalancing, and snapshot versioning |
| RLS | Row-Level Security — PostgreSQL feature enforcing tenant data isolation via `current_setting('app.tenant_id', true)` policies on all tables |
| SPC | Statistical Process Control — anomaly flagging methodology requiring > 2 sigma deviation from control limits (SR-5) |
| SR-6 | Statistical Standard 6 — all PIM reports must include a verbatim limitations disclosure statement |
