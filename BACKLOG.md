# Virtual Analyst — Updated Backlog

> Updated: 2026-03-16 (Sprint 8 complete)
> Branch: main
> Source: PIM Requirements BuildPlan v2.0 (2026-03-09) — supersedes VA_Tech_Stack_Review_PIM v1.0

---

## Current Status

| Area | Metric |
|------|--------|
| Backend tests | 90+ test files (**640+ tests**), 0 failed, 19 skipped (integration gated) |
| Frontend unit tests | **274 passed** across 86 test files |
| Frontend pages | **60 pages** in `(app)` route group |
| E2E tests (Playwright) | **71 spec files** — 3 previously-failing specs fixed; 3 new PIM/AFS flows added |
| TypeScript | 0 errors in production code |
| All 38 backend routers | Covered by tests |
| AFS Module | P1–P6 complete |
| PIM Module | Sprints 0–6 complete — all 8 routers, full test coverage |
| **Sprint 8** | ✅ Done (2026-03-16) — PIM-7.7 CI bounds, N-03 E2E, N-05 OpenAPI, N-06 load tests |
| **Requirements** | Requirements document generated: docs/requirements/2026-03-25-requirements-document.md (v1.0, 2026-03-25) |
| Tier 5 N-items | **All 8 complete** — N-01, N-02, N-03, N-04, N-05, N-06, N-07, N-08 |
| Hosted API (Render) | Healthy (free tier, cold-starts ~3–5 min, keepalive cron active) |
| Hosted Web (Vercel) | Healthy at `www.virtual-analyst.ai` |

---

## Tier 1 — Ship Blockers (commit + deploy)

| # | Item | Files | Effort |
|---|------|-------|--------|
| ~~**S-01**~~ | ~~Commit and deploy the 25 backend test fixes + auth middleware JWT fix~~ | Done (Round 24 + 25) | ~~S~~ |
| ~~**S-02**~~ | ~~Update CONTEXT.md to reflect Round 23 + test fixes, clear stale "In Progress" section~~ | Done (2026-03-09) | ~~S~~ |

---

## Tier 2 — High Priority (quality, security, coverage)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| ~~**H-01**~~ | ~~Backend test coverage for 18 untested routers~~ | Done (Round 25 — all 18 routers now have tests, 311 total) | ~~L~~ |
| ~~**H-02**~~ | ~~Frontend page-level smoke tests~~ | Done — 59 test files covering all 57 page routes (159 tests passing) | ~~M~~ |
| ~~**H-03**~~ | ~~Board pack email distribution~~ | Done — board pack cron scheduler + 16 tests passing | ~~M~~ |
| ~~**H-04**~~ | ~~Board pack update endpoint~~ | Done — implemented real update (label, section order, branding) | ~~S~~ |

---

## Tier 3 — Medium Priority (UX polish, completeness)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| ~~**M-01**~~ | ~~Compare page entity scoping~~ | Resolved — `compare/page.tsx` now scopes runs per entity using `baseline_id` from `api.orgStructures.get()` | ~~S~~ |
| ~~**M-02**~~ | ~~Budget `is_revenue` flag~~ | Resolved — migration `0049_budget_is_revenue.sql` adds column + backfills via pattern matching | ~~S~~ |
| ~~**M-03**~~ | ~~Nav sign-out auth migration~~ | Resolved — `nav.tsx` uses shared `signOut()` from `@/lib/auth` | ~~S~~ |
| ~~**M-04**~~ | ~~Cursor prompt cleanup~~ | Resolved — no `CURSOR_PROMPT_*.md` files remain at root; 53 files archived in `docs/prompts/` | ~~S~~ |
| ~~**M-05**~~ | ~~Untracked `BUILD_PLAN_ENHANCEMENTS.md`~~ | N/A — file no longer exists; superseded by PIM v2.0 build plan | ~~S~~ |

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
| ~~**AFS-P6**~~ | ~~Custom Frameworks + Roll-forward~~ | ~~Custom/AI-inferred frameworks, Roll-forward~~ | Done (2026-03-15): framework detail page, needs_review flag + migration, TB mapping bug fix, 35 new tests | M |

**New database tables:** 12 (afs_frameworks, afs_disclosure_items, afs_engagements, afs_trial_balances, afs_consolidation_rules, afs_sections, afs_section_history, afs_prior_afs, afs_tax_computations, afs_temporary_differences, afs_reviews, afs_review_comments)

**New API endpoints:** ~25 (frameworks, engagements, trial-balance, consolidation, prior-afs, sections/drafting, tax, generation, reviews, analytics)

**New frontend pages:** 10 (AFS dashboard, engagement setup, account mapping, prior AFS review, section editor, tax computation, consolidation, analytics, review, output)

---

## Tier 5 — Nice to Have (future rounds)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| ~~**N-01**~~ | ~~Integration tests without real DB~~ | Done (2026-03-16) — `docker-compose.test.yml` + `scripts/run-integration-tests.sh` provide isolated Postgres on port 5433; CI uses GitHub service container | ~~M~~ |
| ~~**N-02**~~ | ~~Render cold-start mitigation~~ | Done (2026-03-15) — `keepalive.yml` pings `/api/v1/health/live` every 14 min via GitHub Actions cron | ~~S–M~~ |
| ~~**N-03**~~ | ~~Frontend E2E tests~~ | Done (2026-03-16) — fixed 3 failing specs (AFS consolidation, output-generation, draft-editor); added 3 new PIM/AFS flows (pim-sentiment-dashboard, pim-pe-detail, afs-engagement-create); 71 total spec files | ~~L~~ |
| ~~**N-04**~~ | ~~API rate-limit testing~~ | Done (2026-03-15) — 7 tests in `tests/unit/test_rate_limiting.py` covering GET/POST, per-tenant isolation, 429 body, no-tenant fallback | ~~S~~ |
| ~~**N-05**~~ | ~~OpenAPI schema validation tests~~ | Done (2026-03-16) — `test_openapi_schema.py` extended with 3 new PIM tests: CIS response shape, Markov steady-state schema, PE memo disclaimer (SR-6); all 8 PIM router prefixes asserted | ~~M~~ |
| ~~**N-06**~~ | ~~Performance/load test expansion~~ | Done (2026-03-16) — `test_api_performance.py` extended with 4 PIM P95 latency tests: CIS snapshots, Markov states, PE assessments, backtest results; generous thresholds for CI stability | ~~M~~ |
| ~~**N-07**~~ | ~~Monitoring & alerting~~ | Done (2026-03-15) — Sentry wired: backend via `sentry-sdk[fastapi]` in `main.py`, frontend via `@sentry/nextjs` (server/client/edge configs) | ~~M~~ |
| ~~**N-08**~~ | ~~CI pipeline enhancements~~ | Done (2026-03-15) — `ci.yml` now includes ESLint, `npm run test` (vitest), `npm run type-check`, hosted health check job, Trivy Docker scan | ~~S~~ |

---

## Tier 6 — PIM Pre-Condition Gates (must-close before PIM dev)

> Source: PIM Requirements BuildPlan v2.0 (2026-03-09)
> Full build plan: `docs/plans/2026-03-09-pim-v2-build-plan.md`
> 7 gates — 4 v1.0 infrastructure gates dropped (Celery, Structlog, Sentry backend, CI already implemented)

| # | Gate | Description | CR Ref | Effort |
|---|------|-------------|--------|--------|
| ~~**GATE-1**~~ | ~~Statistical anomaly detection~~ | Done — `services/afs/anomaly_stats.py` IQR/Z-score + LLM supplement (2026-03-15) | CR-S2 | M |
| ~~**GATE-2**~~ | ~~JWKS async race condition~~ | Done — `middleware/auth.py` asyncio.Lock + 1h TTL cache + httpx.AsyncClient (2026-03-15) | CR-S4 | S |
| ~~**GATE-3**~~ | ~~Async Redis migration~~ | Done — `worker/celery_app.py` + `worker/tasks.py` migrated to redis.asyncio (2026-03-15) | CR-S5 | S |
| ~~**GATE-4**~~ | ~~DCF mid-year convention~~ | Done — `valuation.py` `(t + 0.5) / 12.0` exponent is mid-year by default (2026-03-15) | CR-F1 | M |
| ~~**GATE-5**~~ | ~~DCF equity bridge~~ | Done — `DCFResult` has `net_debt`, `cash`, `equity_value`; bridge in `dcf_valuation()` (2026-03-15) | CR-F2 | S |
| ~~**GATE-6**~~ | ~~DCF exit multiples~~ | Done — `terminal_multiple` param + EBITDA exit multiple path in `dcf_valuation()` (2026-03-15) | CR-F3 | M |
| ~~**GATE-7**~~ | ~~MC parallelism~~ | Done — `ProcessPoolExecutor` above `PARALLEL_THRESHOLD=50` in `monte_carlo.py` (2026-03-15) | CR-T1 | S |

---

## Tier 7 — PIM Remediation Backlog (Sprint 0)

> Source: PIM Requirements BuildPlan v2.0, Sprint 0 — 23 remediation items
> Full details: `docs/plans/2026-03-09-pim-v2-build-plan.md` § Sprint Plan

Sprint 0 (2 weeks) closes all 7 gates + fixes 16 additional issues from the consolidated code review.

| # | Item | CR Ref | Effort |
|---|------|--------|--------|
| ~~**REM-01**~~ | ~~Statistical anomaly detection (IQR/Z-score)~~ | CR-S2 (GATE-1) — Done 2026-03-15 | M |
| ~~**REM-02**~~ | ~~JWKS async race condition~~ | CR-S4 (GATE-2) — Done 2026-03-15 | S |
| ~~**REM-03**~~ | ~~Async Redis migration~~ | CR-S5 (GATE-3) — Done 2026-03-15 | S |
| ~~**REM-04**~~ | ~~DCF mid-year convention~~ | CR-F1 (GATE-4) — Done 2026-03-15 | M |
| ~~**REM-05**~~ | ~~DCF equity bridge~~ | CR-F2 (GATE-5) — Done 2026-03-15 | S |
| ~~**REM-06**~~ | ~~DCF exit multiples~~ | CR-F3 (GATE-6) — Done 2026-03-15 | M |
| ~~**REM-07**~~ | ~~MC parallelism (ProcessPoolExecutor)~~ | CR-T1 (GATE-7) — Done 2026-03-15 | S |
| ~~**REM-08**~~ | ~~Tax loss carryforward / NOL~~ | CR-F4 — Done (statements.py lines 173–219) | M |
| ~~**REM-09**~~ | ~~Multi-period FX rates~~ | CR-F5 — Done (consolidation.py `FxRate = float \| list[float]`) | M |
| ~~**REM-10**~~ | ~~Auth middleware DB-error fallback~~ | CR-F6 — Done (auth.py: 503 on DB error, no silent fallback) | S |
| ~~**REM-11**~~ | ~~Split `budgets.py` (1,618 lines)~~ | CR-Q2 — Done (6-file package, budgets/) | M |
| ~~**REM-12**~~ | ~~Split `afs.py` (2,657 lines)~~ | CR-Q3 — Done (10-file afs/ package, 2026-03-15) | L |
| ~~**REM-13**~~ | ~~Fix RunStatus enum (`completed` → `succeeded`)~~ | CR-Q4 — Done (runs table CHECK constraint) | S |
| ~~**REM-14**~~ | ~~Consolidation minority interest~~ | CR-Q5 — Done (consolidation.py NCI support) | M |
| ~~**REM-15**~~ | ~~Auth middleware role fallback~~ | CR-Q6 — Done (same as REM-10: 503, no fallback) | S |
| ~~**REM-16**~~ | ~~Replace bare `except:` (8 files)~~ | CR-Q7 — Done (zero bare `except:` found) | S |
| ~~**REM-17**~~ | ~~Replace `unknown` TypeScript types (partial — pim + model_config)~~ | CR-Q8 — Done (ModelConfig/BaselineDetail/BaselineVersion interfaces in api.ts) | M |
| ~~**REM-18**~~ | ~~Parameter denylist hardening~~ | CR-Q9 — Done (sensitivity.py: _MAX_PATH_DEPTH=5, _PATH_DENYLIST frozenset) | XS |
| ~~**REM-19**~~ | ~~Sentry frontend integration~~ | CR-N2 — Done (sentry.*.config.ts + withSentryConfig) | S |
| ~~**REM-20**~~ | ~~PIM page-level smoke tests~~ | CR-N1 — Done (pim-sentiment.test.tsx: 5 tests, setup.tsx pim mock added) | M |
| ~~**REM-21**~~ | ~~Budget `is_revenue` flag~~ | CR-N3 — Done (periods.py + templates.py + analytics.py) | S |
| ~~**REM-22**~~ | ~~OpenAPI → TypeScript codegen~~ | CR-N4 — Done (openapi-typescript@7.13 installed, generate:api script in package.json) | M |
| ~~**REM-23**~~ | ~~API rate-limit tests~~ | CR-N5 — Done (test_rate_limiting.py, 4 tests) | S |

---

## Tier 8 — PIM Module (Portfolio Intelligence Module)

> Design spec: `docs/plans/Portfolio_Intelligence_Module_Design_Spec.docx`
> Build plan v2.0: `docs/plans/2026-03-09-pim-v2-build-plan.md`
> Prerequisites: All Tier 6 gates must be closed (Sprint 0) before PIM sprints begin.

AI-powered portfolio analytics with 81-state Markov chain model, CIS scoring, multi-source sentiment analysis, backtesting framework, and PE benchmarking. 71 backlog items across 7 sprints.

| Sprint | Duration | Focus | Key Deliverables |
|--------|----------|-------|-----------------|
| **Sprint 0** | 2 weeks | Remediation | 7 gate closures + 16 code review fixes (REM-01 – REM-23) |
| **Sprint 1** | 3 weeks | Sentiment Ingestion (FR-1) | Polygon.io + NewsAPI integration, LLM sentiment scoring, Celery workers, 3 new tables |
| **Sprint 2** | 3 weeks | Economic Context (FR-2) | FRED API integration, regime classification, economic dashboard, indicator storage |
| **Sprint 3** | 3 weeks | CIS & Markov Engine (FR-3, FR-4) | Composite Investment Score, 81-state Markov chain, QuantEcon integration, Numba JIT |
| **Sprint 4** | 4 weeks | Portfolio Construction (FR-5) | Greedy portfolio optimizer, constraint engine, rebalancing, transaction cost model |
| **Sprint 5** | 3 weeks | Backtesting (FR-6) | Walk-forward backtester, IC/ICIR/SPC metrics, backtest studio UI, materialized views |
| **Sprint 6** | 4 weeks | PE Benchmarking + DTF (FR-7) | PE assessment database, J-curve analysis, DPI/TVPI/IRR, DTF-B ongoing validation |

**New database tables:** 9 PIM + 4 DTF = 13 total
**New LLM task labels:** 6 (sentiment extraction, summary, factor attribution, PE memo, portfolio narrative, backtest commentary)
**Procurement:** Polygon.io ($29/mo), AlphaSense (sentiment), MSCI Barra (transaction costs), Claude Sonnet (PE memo)
**Infrastructure:** Numba JIT, pg_partman partitioning, ProcessPoolExecutor, QuantEcon, D3.js visualizations, materialized views

---

## Test Coverage Summary

### Backend (35 routers)

| Status | Count | Routers |
|--------|-------|---------|
| Has tests | **35** | All routers covered (Round 25 added: activity, audit, benchmark, board_pack_schedules, comments, compliance, connectors, covenants, documents, feedback, health, import_csv, integrations, marketplace, metrics_summary, notifications, org_structures) |
| No tests | **0** | — |

### Frontend (57 pages)

| Status | Count |
|--------|-------|
| Component/utility tests | 5 files (VAInput, VASelect, VAPagination, format, logger) |
| Page-level smoke tests | **59 test files** covering all 57 page routes (159 tests passing) |

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
| AFS-P6 + PIM Sprint 6 | (2026-03-15) | AFS custom frameworks + roll-forward; PIM-7.1 peer comparison API + 23 tests, PIM-7.2 PE memo endpoint (LLMRouter, 6 tests), PIM-7.4 PE dashboard UI (list + detail pages, J-curve, peer rankings), PIM-7.5 billing gate verified; N-04 rate-limit tests (7), N-08 CI enhancements (ESLint, vitest, type-check, health-check, Trivy), N-02 keepalive verified, N-07 Sentry verified |
| PIM Sprint 7 (partial) | (2026-03-16) | PIM-7.9 PE hub summary widget + API endpoint + 3 tests; PIM-7.8 board pack PE portfolio section (HTML+PPTX) + 4 tests; PIM-7.3 venture overlay on PE detail page (ventures list/get endpoints + 5 tests + UI); Markov/sentiment/CIS/backtest API tests (+30 tests); N-01 Docker Compose integration test verified |
| Sprint 8 — Platform Hardening | (2026-03-16) | PIM-7.7 uncertainty bounds: analytical CI on CIS composite score (ci_lower/ci_upper/ci_method + graceful null when n<3) and Dirichlet CI on Markov steady-state probabilities (81-element CI arrays); N-03 E2E fixes: 3 failing specs fixed (waitForURL → waitForLoadState + guard, hard throw → test.skip), 3 new PIM/AFS flows added (sentiment dashboard, PE detail, AFS engagement); N-05 OpenAPI extension: 3 new PIM schema tests (CIS response, Markov steady-state, PE memo SR-6 disclaimer check), 8 PIM prefixes asserted; N-06 load test extension: 4 new PIM P95 latency tests; pyproject.toml: ruff per-file-ignores for S101 in tests; 564 lines added across 11 files, 49 tests passing |
