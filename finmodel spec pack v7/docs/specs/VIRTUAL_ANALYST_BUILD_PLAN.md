# Build Plan — Virtual Analyst v1
Date: 2026-02-11
Version: 1.0

## Purpose
This plan defines how we will execute Virtual Analyst v1 using the FinModel Spec Pack v7 as the authoritative source of architecture, artifacts, and requirements.

## Scope Alignment
- Virtual Analyst v1 is a rebrand of the FinModel v7 scope and feature set.
- All specs in `finmodel spec pack v7/docs/specs/` remain authoritative.
- This plan corrects minor naming mismatches and sets a clear execution path.

## Assumptions
- Backend: FastAPI + Python 3.12, Pydantic v2, Postgres (Supabase), Redis, Celery.
- Frontend: Next.js App Router + TypeScript + Tailwind + shadcn/ui.
- V1 includes: Xero integration, Stripe billing, Excel add-in, memo packs.
- Post-launch: multi-currency, SSO/SAML, template marketplace.

## Corrections Applied
- Use `docs/specs/BUILD_PLAN.md` and `docs/specs/BACKLOG.md` (no `_V2` suffix).
- Phase 0 is mandatory and uses the new foundation specs.
- Phase 5 migration name is `0005_excel_and_memos.sql`.
- Master prompt must be updated to v7 to include Phase 0 and new specs.

---

## Phase 0 — Foundation & Infrastructure (1-2 weeks)
Goal: Establish dev environment, CI/CD, security, error handling, logging, metrics.

Deliverables:
- Monorepo scaffolding, environment config, Docker Compose.
- Error handling framework and standard API envelope.
- Structured logging, metrics endpoint, health checks.
- Security middleware (headers, rate limiting, CORS).
- CI/CD pipeline and pre-commit hooks.
- FastAPI app skeleton with health and metrics endpoints.

Gate Criteria:
- `docker-compose up` starts Postgres, Redis, Supabase locally.
- `/api/v1/health/ready` returns 200 when dependencies are up.
- `/metrics` returns Prometheus format metrics.
- Error responses use the standard envelope and codes.
- CI pipeline is green (lint, type check, tests).
- Security headers and rate limiting are enforced.

---

## Phase 1 — Core Deterministic Engine (3-4 weeks)
Goal: Deterministic 3-statement forecasting engine with baseline/run workflow.

Deliverables:
- Pydantic schema models for `model_config_v1`.
- Graph builder, expression evaluator, time-series engine.
- Statements generator (IS/BS/CF) and KPI calculator.
- Baseline and run APIs, artifact storage with validation.
- Initial web UI (login, baseline list, run results).
- Unit, integration, and performance tests.

Gate Criteria:
- Manufacturing template runs deterministically and balances BS monthly.
- P95 runtime <500ms for 12-month deterministic run.
- RLS blocks cross-tenant data access.
- UI supports login -> baseline list -> run results.
- Audit events are logged for baseline/run lifecycle.

---

## Phase 2 — Draft Layer + LLM Integration (3-4 weeks)
Goal: LLM-assisted drafting with a strict Draft -> Commit boundary.

Deliverables:
- Celery job queue with retries and DLQ.
- Draft session CRUD with state machine and autosave.
- LLM provider abstraction with routing, circuit breaker, metering.
- Draft chat endpoint with structured outputs and validation.
- Commit pipeline and changeset workflow.
- Draft workspace UI, changeset UI, notifications.

Gate Criteria:
- Draft created -> chat -> proposal -> commit -> new baseline.
- LLM calls logged and metered; routing and fallback work.
- Changeset dry-run and merge create new baseline version.
- Background jobs process long-running LLM calls.

---

## Phase 3 — Monte Carlo + Scenarios + Valuation (3-4 weeks)
Goal: Probabilistic simulation, scenario management, valuation outputs.

Deliverables:
- Distribution engine and Monte Carlo runner.
- Async MC execution with progress reporting.
- Scenario CRUD and baseline comparison.
- Valuation module (DCF, multiples).
- Sensitivity analysis and charting components.

Gate Criteria:
- 1,000 sim MC run completes with deterministic seed outputs.
- Scenario comparison and valuation outputs in UI.
- Sensitivity and waterfall charts render correctly.

---

## Phase 4 — Integrations + Billing + Compliance (4-5 weeks)
Goal: ERP integrations, billing, and compliance readiness.

Deliverables:
- Integration framework with Xero adapter and sync runs.
- Stripe subscription and usage metering.
- Full audit logging and export.
- GDPR export/deletion endpoints.
- CSV import and covenant monitoring.
- Notifications (email + in-app).

Gate Criteria:
- Xero OAuth and sync produce canonical snapshots.
- Stripe subscription lifecycle and usage limits enforced.
- Audit log is immutable and exportable.
- GDPR export and deletion operate correctly.

---

## Phase 5 — Excel + Memos + Collaboration (3-4 weeks)
Goal: Excel bidirectional sync, memo generation, and collaboration.

Deliverables:
- Excel export and live connection APIs.
- Office.js add-in with pull/push bindings.
- Memo pack generator (HTML/PDF).
- Document management and comments.
- Activity feed and basic collaboration features.

Gate Criteria:
- Excel export produces correct IS/BS/CF sheets.
- Excel push creates changeset with role enforcement.
- Memo generator produces HTML/PDF with correct data.
- Comments and activity feed are visible in UI.

---

## Release Timeline Estimate
| Phase | Duration | Cumulative |
|---|---|---|
| Phase 0 | 1-2 weeks | 2 weeks |
| Phase 1 | 3-4 weeks | 6 weeks |
| Phase 2 | 3-4 weeks | 10 weeks |
| Phase 3 | 3-4 weeks | 14 weeks |
| Phase 4 | 4-5 weeks | 19 weeks |
| Phase 5 | 3-4 weeks | 23 weeks |
| Total | ~23 weeks | ~5.5 months |

Buffer: add 20 percent for unknowns (total ~28 weeks).

---

## Cross-Cutting Quality Gates
- Test coverage >70 percent for shared engine code.
- P95 API latency <1s (non-MC endpoints).
- Error rate <1 percent under expected load.
- No high or critical security vulnerabilities.
- Observability dashboards and alerts in place.

---

## Kickoff Checklist (Week 1)
- Confirm project scope and naming (Virtual Analyst = FinModel v7 scope).
- Complete Phase 0 backlog items.
- Provision Supabase project (Auth, Storage, RLS).
- Establish CI/CD and developer setup docs.
- Create baseline manufacturing template run in Phase 1.
