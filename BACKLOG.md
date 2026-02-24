# Virtual Analyst — Updated Backlog

> Updated: 2026-02-24
> Branch: main
> Latest commit: c7633fa (Round 25: structlog imports fix)
> Uncommitted: none (clean working tree)

---

## Current Status

| Area | Metric |
|------|--------|
| Backend tests | **311 passed**, 0 failed, 18 skipped |
| Frontend tests | **33 passed** (5 test files — 3 component, 2 utility) |
| TypeScript | 0 errors |
| Hosted API (Render) | Healthy (free tier, cold-starts ~3–5 min) |
| Hosted Web (Vercel) | Healthy at `virtual-analyst-ten.vercel.app` |
| Phases P1–P8 | All numbered backlog items complete (VA-P5 through VA-P8) |
| Round 23 P1–P10 | All 10 enhancements implemented and committed |

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
