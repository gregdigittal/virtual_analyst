# Virtual Analyst — Updated Backlog

> Updated: 2026-03-08
> Branch: main
> Latest commit: cf9bda7 (AFS Phase 5 — Analytics & Industry Benchmarking)
> Source: VA Tech Stack Review PIM document (2026-03-08)

---

## Current Status

| Area | Metric |
|------|--------|
| Backend tests | 85 test files (**547+ tests**), 0 failed, 19 skipped (integration gated) |
| Frontend unit tests | **159 passed** across 32 test files |
| Frontend pages | **58 pages** in `(app)` route group |
| E2E tests (Playwright) | **68 spec files** — 32 pass, 2 skip, 3 fail (UI detail page links) |
| TypeScript | 0 errors |
| All 35 backend routers | Covered by tests |
| AFS Module | P1–P5 complete, P6 remaining |
| Hosted API (Render) | Healthy (free tier, cold-starts ~3–5 min) |
| Hosted Web (Vercel) | Healthy at `www.virtual-analyst.ai` |

---

## Tier 1 — Ship Blockers (commit + deploy)

| # | Item | Files | Effort |
|---|------|-------|--------|
| ~~**S-01**~~ | ~~Commit and deploy the 25 backend test fixes + auth middleware JWT fix~~ | Done (Round 24 + 25) | ~~S~~ |
| **S-02** | **Update CONTEXT.md** to reflect Round 23 + test fixes, clear stale "In Progress" section | `CONTEXT.md` | S |

---

## Tier 2 — High Priority (quality, security, coverage)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| ~~**H-01**~~ | ~~Backend test coverage for 18 untested routers~~ | Done (Round 25 — all 18 routers now have tests, 311 total) | ~~L~~ |
| **H-02** | Frontend page-level smoke tests | 0 of 51 pages have tests. Priority targets: `dashboard`, `baselines/[id]`, `runs/[id]`, `compare`, `workflows`, `budgets/[id]` — render without crash + auth redirect check | M |
| **H-03** | Board pack email distribution | `board_pack_schedules.py:247` stubs email sending. Wire to SendGrid or SES for real distribution | M |
| **H-04** | Board pack update endpoint | `board_packs.py:368` is a "Phase 10 stub" — implement real update (label, section order, branding) | S |

---

## Tier 3 — Medium Priority (UX polish, completeness)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| **M-01** | Compare page entity scoping | `compare/page.tsx:119` — TODO: scope runs per entity once `baseline_id` is exposed on `OrgStructureItem` | S |
| **M-02** | Budget `is_revenue` flag | `budgets.py:1388` — TODO: add explicit `is_revenue` flag to `budget_line_items` for accuracy | S |
| **M-03** | Nav sign-out auth migration | `nav.tsx` still uses raw `createClient()` for sign-out — migrate to shared auth utility for consistency | S |
| **M-04** | Cursor prompt cleanup | 47 `CURSOR_PROMPT_*.md` files in repo root. All applied — archive to `docs/prompts/` or remove | S |
| **M-05** | Untracked `BUILD_PLAN_ENHANCEMENTS.md` | Either commit or add to `.gitignore` | S |

---

## Tier 4 — Major Feature: AFS Module (Annual Financial Statements)

> Design doc: `docs/plans/2026-02-24-afs-module-design.md`

AI-powered Annual Financial Statement generation with multi-framework compliance, NL-driven disclosure drafting, consolidation, tax computation, and review workflows.

| # | Phase | Sub-modules | Description | Effort |
|---|-------|-------------|-------------|--------|
| **AFS-P1** | Framework + Ingestion | Framework Engine, Data Ingestion (single entity), Statement Generator (PDF/DOCX) | Pre-built frameworks (IFRS, IFRS-SME, US GAAP, SA GAAP), trial balance import (VA baselines + Excel/CSV), account mapping (AI-assisted), basic statement generation with branding | XL |
| **AFS-P2** | AI Disclosure Drafter | AI Drafter, Prior AFS Analysis | Upload prior-year AFS (PDF extraction + Excel), section-by-section NL prompting, full draft generation via LLM + RAG over standards, iteration loop, compliance validation against checklist | XL |
| **AFS-P3** | Workflow + Tax | Review Workflow, Tax Computation | Multi-stage approval (draft → preparer → manager → partner), version control, redlining, audit trail, lock/unlock. Current + deferred tax computation, tax reconciliation, tax note generation | L |
| **AFS-P4** | Consolidation + Filing | Multi-entity Consolidation, iXBRL/XBRL output | Aggregate trial balances, intercompany elimination, minority interests, currency translation. Machine-readable regulatory output (CIPC, SEC) | L |
| **AFS-P5** | Analytics | AFS Analytics | Ratio analysis, YoY trends, industry benchmarking, anomaly detection, going concern indicators, management commentary suggestions | M |
| **AFS-P6** | Custom Frameworks + Roll-forward | Custom/AI-inferred frameworks, Roll-forward | User-defined frameworks, AI-inferred frameworks from NL description, automatic prior-year roll-forward with update flags | M |

**New database tables:** 12 (afs_frameworks, afs_disclosure_items, afs_engagements, afs_trial_balances, afs_consolidation_rules, afs_sections, afs_section_history, afs_prior_afs, afs_tax_computations, afs_temporary_differences, afs_reviews, afs_review_comments)

**New API endpoints:** ~25 (frameworks, engagements, trial-balance, consolidation, prior-afs, sections/drafting, tax, generation, reviews, analytics)

**New frontend pages:** 10 (AFS dashboard, engagement setup, account mapping, prior AFS review, section editor, tax computation, consolidation, analytics, review, output)

---

## Tier 5 — Nice to Have (future rounds)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| **N-01** | Integration tests without real DB | The 18 skipped integration tests require `INTEGRATION_TESTS=1` + PostgreSQL. Consider a Docker Compose test target or Supabase local dev for CI | M |
| **N-02** | Render cold-start mitigation | Free tier spins down → 3–5 min cold starts. Options: upgrade to paid tier, add a cron health ping, or move to Railway/Fly.io | S–M |
| **N-03** | Frontend E2E tests (Playwright/Cypress) | No browser-level E2E tests exist. Priority flows: login → dashboard → create run → view results | L |
| **N-04** | API rate-limit testing | Security middleware has per-tenant rate limiting but no tests exercise it | S |
| **N-05** | OpenAPI schema validation tests | Ensure all endpoints match documented schemas; auto-generate TypeScript types from OpenAPI | M |
| **N-06** | Performance/load test expansion | `tests/load/test_engine_performance.py` exists but scope is limited to the engine. Add API-level load tests for key flows | M |
| **N-07** | Monitoring & alerting | No Sentry, Datadog, or equivalent configured. Add error tracking and uptime monitoring | M |
| **N-08** | CI pipeline enhancements | Current CI runs lint + pytest + integration. Add: frontend `vitest`, TypeScript check, hosted health check, Docker image scan | S |

---

## Tier 6 — Tech Stack Remediation (PIM Gates)

> Source: `docs/reviews/VA_Tech_Stack_Review_PIM.docx` (2026-03-08)
> These 8 items are **mandatory prerequisites** before PIM development can begin.
> Incremental cost: ~$220–260/month (Supabase Large + Sentry + BetterUptime)

| # | Item | Description | CR Ref | Effort |
|---|------|-------------|--------|--------|
| **G-01** | Fix JWKS async race condition | Cache JWKS response with TTL; current implementation re-fetches on every request under concurrent load | CR-S4 | S |
| **G-02** | Replace sync Redis with `redis.asyncio` | `redis.Redis` blocks the async event loop; migrate all call sites to `redis.asyncio.Redis` | CR-S5 | S |
| **G-03** | Replace `unknown` TypeScript types | `StatementsData` and related interfaces use `unknown`; add proper typed interfaces for all financial data structures | CR-Q8 | M |
| **G-04** | Upgrade Supabase to Large compute | PIM requires higher connection limits, more CPU/RAM for time-series queries and concurrent Celery workers. Upgrade via Supabase dashboard | — | Config |
| **G-05** | Add Celery + Redis broker + Flower | Async job queue for: sentiment ingestion, backtest execution, DTF-A calibration, scheduled sentiment refresh. Redis already deployed (reuse as broker). Add Flower for task monitoring | — | M |
| **G-06** | Add Structlog structured JSON logging | Replace ad-hoc `print`/`logging` with structured JSON logs. Enable correlation IDs, tenant context, and log aggregation readiness | — | S |
| **G-07** | Add Sentry error tracking | Integrate `sentry-sdk[fastapi]` for backend + `@sentry/nextjs` for frontend. Configure source maps, environment tags, user context | — | S |
| **G-08** | Add GitHub Actions CI pipeline | Automated: `ruff check`, `pytest`, `vitest`, `tsc --noEmit`, ESLint. Run on PR + push to main. Block merge on failure | — | M |

**Cross-references to existing items:**
- G-01 (CR-S4) → overlaps with Comprehensive Review Sprint 1 security items
- G-02 (CR-S5) → overlaps with Comprehensive Review Sprint 7 item 34
- G-03 (CR-Q8) → overlaps with Comprehensive Review Sprint 7 item 33
- G-06 → partially done (structlog already imported in some modules)
- G-07 → supersedes N-07 (monitoring & alerting)
- G-08 → supersedes N-08 (CI pipeline enhancements)

---

## Tier 7 — PIM Tech Stack Enhancements (post-gate)

> Source: `docs/reviews/VA_Tech_Stack_Review_PIM.docx` (2026-03-08)
> These are implemented as needed during PIM development sprints.

| # | Item | Description | Priority | Effort |
|---|------|-------------|----------|--------|
| **P-01** | Numba JIT for Monte Carlo + Markov hot loops | `@njit` decorator on inner simulation loops for 10–100× speedup. NumPy vectorized Markov transitions via matrix power P^n | High | M |
| **P-02** | `pg_partman` time-series partitioning | Partition `pim_price_history` and `pim_sentiment_scores` by month using native PostgreSQL partitioning (TimescaleDB deprecated on Supabase PG17) | High | M |
| **P-03** | `ProcessPoolExecutor` for MC/Markov parallelism | CPU-bound simulation parallelism using `ProcessPoolExecutor` with `asyncio.run_in_executor()`. Overlaps with Comprehensive Review Sprint 4 item 16 (CR-T1) | High | S |
| **P-04** | QuantEcon library | Markov chain utilities (steady-state computation, `MarkovChain` class, ergodicity checks). Avoids reimplementing standard stochastic methods | Medium | S |
| **P-05** | D3.js for PIM visualizations | Supplement Recharts with D3.js for: Markov state diagrams, sentiment heatmaps, backtest comparison charts, PE distribution overlays | Medium | M |
| **P-06** | Materialized views for backtest aggregates | Pre-computed views for IC/ICIR/SPC metrics, portfolio returns, strategy comparisons. Refresh on schedule or after backtest completion | Medium | S |
| **P-07** | Supabase read replica | Offload heavy analytical queries (backtests, universe screening) to read replica. Keep writes on primary | Low | Config |
| **P-08** | Migrate to new Supabase API key format | Transition from legacy `anon`/`service_role` JWTs to `sb_publishable_*` / `sb_secret_*` keys. Supabase plans to deprecate legacy format | Low | S |
| **P-09** | Evaluate DuckDB for DTF-A calibration | Embedded analytical engine for developer-only calibration pipeline. Process EDGAR/FRED/Yahoo bulk data without hitting PostgreSQL | Low | S (eval) |
| **P-10** | Evaluate Polars for backtest data processing | Upgrade path from pandas if backtest DataFrames exceed memory at 500+ company universes. Lazy evaluation + multi-threaded execution | Low | S (eval) |

**Cross-references to existing items:**
- P-03 → overlaps with Comprehensive Review Sprint 4 item 16 (ProcessPoolExecutor for MC)
- P-05 → D3.js is additive to existing Recharts setup, not a replacement

---

## Tier 8 — PIM Module (Portfolio Intelligence Module)

> Design spec: `docs/plans/Portfolio_Intelligence_Module_Design_Spec.docx`
> Build plan: `docs/plans/2026-03-08-pim-tech-stack-build-plan.md`
> Prerequisites: All Tier 6 gate items must be complete before PIM development begins.

AI-powered portfolio analytics with 81-state Markov chain model, multi-source sentiment analysis, backtesting framework, and PE benchmarking.

| # | Phase | Sub-systems | Description | Effort |
|---|-------|-------------|-------------|--------|
| **PIM-1** | Sentiment Ingestion | Sentiment Engine, Data Sources | Multi-source sentiment ingestion (news APIs, earnings transcripts, social), NLP scoring via LLM, Celery-scheduled refresh, tenant-scoped storage | XL |
| **PIM-2** | Economic Context | Macro Indicators, FRED Integration | Economic regime classification (expansion/contraction/transition), FRED API integration, indicator dashboard, regime-aware model conditioning | L |
| **PIM-3** | Fundamental Aggregation | Company Financials, Universe Manager | EDGAR/Yahoo fundamental data ingestion, financial ratio computation, sector/peer grouping, universe CRUD, quality scoring | XL |
| **PIM-4** | Portfolio Scoring | Composite Score, Markov States | 81-state Markov chain (3 sentiment × 3 fundamental × 3 economic × 3 momentum), state transition matrix estimation, portfolio-level composite scoring | XL |
| **PIM-5** | Markov Chain Engine | Transition Matrix, Steady State | Numba-accelerated Markov simulation, `QuantEcon.MarkovChain` integration, steady-state distribution, state persistence, matrix calibration via DTF | L |
| **PIM-6** | Backtesting Framework | Strategy Backtester, IC/ICIR | Walk-forward backtesting, information coefficient calculation, strategy comparison, materialized view aggregates, backtest studio UI | XL |
| **PIM-7** | PE Benchmarking | PE Assessments, Peer Analysis | Private equity benchmark database, fund return comparison, J-curve analysis, vintage year analytics, DPI/TVPI/IRR computation | L |

**New infrastructure requirements:**
- Celery workers (from G-05) for async ingestion + backtest execution
- `pg_partman` partitioned tables (from P-02) for time-series data
- Numba JIT (from P-01) for simulation hot loops
- D3.js (from P-05) for Markov diagrams and sentiment heatmaps

---

## Test Coverage Summary

### Backend (35 routers)

| Status | Count | Routers |
|--------|-------|---------|
| Has tests | **35** | All routers covered (Round 25 added: activity, audit, benchmark, board_pack_schedules, comments, compliance, connectors, covenants, documents, feedback, health, import_csv, integrations, marketplace, metrics_summary, notifications, org_structures) |
| No tests | **0** | — |

### Frontend (51 pages)

| Status | Count |
|--------|-------|
| Component/utility tests | 5 files (VAInput, VASelect, VAPagination, format, logger) |
| Page-level tests | **0** of 51 pages |

---

## Completed Rounds (for reference)

| Round | Commit | Summary |
|-------|--------|---------|
| Production readiness | b566e3a | A-01 through C-11 |
| Round 17 | 0c69516 | API client bindings (18 groups, 25 interfaces) |
| P0 UI/UX | fd72903 | Confirmation dialogs, toast, UUID dropdowns, VASelect |
| P1 UI/UX | 9e85005 | Nav active state, error boundary, spinners, date format |
| Round 19A | 2dd1c4f | Pagination + filter on 13 list pages |
| Round 19B | 9c63910 | Form validation on 16 forms |
| Round 19G | e34d0aa | Financial dashboard, tornado, MC fan chart, timeline, comments |
| Round 19F | 5504450 | Backend test coverage (MC P50, memo, excel_export, circuit_breaker) |
| Round 20 | be43037 + fe39cb1 | Middleware, download fix, budget variance, ventures form |
| Round 21 | 91f0f1e | Logger.ts, middleware /compare, .env.example, api.boardPacks |
| Round 22 | 6003f44 + 8ede924 | Auth standardisation, W6 multi-tenancy, G-05 board pack builder, KPI cards |
| Round 23 | 33dd2e8 | P1-P10: excel export, scenarios, run config, dashboard, charts, comparison, workflows, versions, config viewer |
| Round 24 | 4d48540 | 25 backend test fixes, JWT audience bug fix, XSS entity_name validation |
| Round 25 | 6d1bf32 + c7633fa | 18 router test files, security hardening (HMAC, XSS, secrets, safe parsing), structlog imports |
| E2E Seed | d681334 | 68 E2E spec files, 13 backend fixes (CORS, JWT, Redis, pgbouncer, tenant provisioning) |
| AFS P1–P5 | cf9bda7 | AFS module phases 1–5 complete (52 endpoints, 12 tables, 10 frontend pages) |
| Instructions | a5bd4bb | InstructionsDrawer + drafts fixes + 27 manual chapters updated |
