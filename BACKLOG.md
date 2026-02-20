# Virtual Analyst — Updated Backlog

> Generated: 2026-02-20
> Branch: main
> Latest commit: 33dd2e8 (Round 23: P1-P10 feature enhancements)
> Uncommitted: 12 files — backend test fixes + auth middleware JWT audience fix + XSS validation

---

## Current Status

| Area | Metric |
|------|--------|
| Backend tests | **214 passed**, 0 failed, 18 skipped |
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
| **S-01** | **Commit and deploy the 25 backend test fixes + auth middleware JWT fix** | 12 files (uncommitted) | S — commit only |
| **S-02** | **Update CONTEXT.md** to reflect Round 23 + test fixes, clear stale "In Progress" section | `CONTEXT.md` | S |

---

## Tier 2 — High Priority (quality, security, coverage)

| # | Item | Description | Effort |
|---|------|-------------|--------|
| **H-01** | Backend test coverage for 18 untested routers | `activity`, `audit`, `benchmark`, `board_pack_schedules`, `comments`, `compliance`, `connectors`, `covenants`, `documents`, `feedback`, `health`, `import_csv`, `integrations`, `marketplace`, `metrics_summary`, `notifications`, `org_structures` — at minimum, "requires X-Tenant-ID" + happy-path smoke tests with mocked `tenant_conn` | L |
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

## Tier 4 — Nice to Have (future rounds)

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
| Has tests | **17** | baselines, runs, budgets, board_packs, changesets, currency, drafts, excel (3), jobs, scenarios, teams, ventures, workflows, assignments, auth_saml, billing, memos |
| No tests | **18** | activity, audit, benchmark, board_pack_schedules, comments, compliance, connectors, covenants, documents, feedback, health, import_csv, integrations, marketplace, metrics_summary, notifications, org_structures |

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
| Round 24 (uncommitted) | — | 25 backend test fixes, JWT audience bug fix, XSS entity_name validation |
