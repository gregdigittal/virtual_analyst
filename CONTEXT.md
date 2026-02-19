# Project Context — Virtual Analyst

> Last updated: 2026-02-19T22:35:00Z
> Commit: b5d8925 — Add frontend unit tests: vitest + React Testing Library (33 tests)
> Branch: main

## Architecture

- **Backend**: Python 3.12+, FastAPI, asyncpg (Supabase Postgres with RLS), Celery + Redis
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, Shadcn UI
- **LLM**: Hybrid — `LLMRouter` for single-turn structured output, `AgentService` (Claude Agent SDK) for multi-step tasks
- **Storage**: `ArtifactStore` (Supabase Storage or in-memory) with async wrappers, tenant-scoped via `tenant_conn()`
- **Auth**: Supabase Auth + optional SAML SSO (defusedxml), JWT verification, RBAC (owner/admin/analyst/investor)
- **Billing**: Stripe-backed `BillingService` with plan-aware LLM quota; usage meter uses `FOR UPDATE`
- **Deployment**: Vercel (frontend at virtual-analyst.ai), API on Render/similar

## Recent Changes (this commit)

- P0 UI/UX: confirmation dialogs, toast notifications, UUID dropdowns, VASelect component (fd72903)
- P1 UI/UX: nav active state, error boundary (error.tsx), VASpinner across 36 pages, shared date formatting, empty states, missing nav links (9e85005)
- Round 17 API client bindings (18 binding groups, 25 TypeScript interfaces) committed in 0c69516

## Current State

- All production readiness items (A-01 through C-11) implemented
- TypeScript `tsc --noEmit` reports 0 errors (33 frontend tests pass)
- Agent SDK flags default to `true`; `claude-agent-sdk` is optional (`pip install .[agent]`)
- Migration 0048 applied to Supabase
- Backend tests: `python -m pytest tests/unit/ tests/golden/ -q` (root-level `tests/`; 171 pass, ~20 fail on external deps — Stripe, LLM providers, OSError in workflow templates)
- Custom domain `virtual-analyst.ai` active on Vercel
- Round 19 cursor prompts applied: pagination/filter, form validation, missing backend tests, competitive features (dashboard, tornado, MC fan chart, timeline, comments)
- Round 20 applied: middleware auth for 22 routes, download fix, API_URL dedup, budget variance UI, ventures questionnaire form, logger.ts, .env.example, api.boardPacks.update
- Backlog cursor prompts on disk: G-02 (compare — implemented), G-05 (board pack builder), W6 (multi-tenancy enforcement), I1 (error logging)

## In Progress / Next Steps

- G-05: Board pack section builder (`board-packs/[id]/builder`) — cursor prompt on disk
- W6: Multi-tenancy auth.ts enforcement (`NEXT_PUBLIC_REQUIRE_TENANT_ID`) — cursor prompt on disk
- Missing pages: `/import` (CSV import UI), `/runs/[id]/valuation`
- Auth pattern standardisation: ~12 pages use raw `createClient()` instead of `getAuthContext()` + redirect
- Compare page (`/compare`): run-fetch logic needs scoping per entity (currently fetches global latest)
- KPI card display on run detail page (raw JSON pre block today)
- Backend test failures: ~20 tests failing on external deps (Stripe, LLM providers, OSError in workflow templates) — need mocking or skip markers

## Key Files & Patterns

- `apps/api/app/core/settings.py` — all config, production validators, agent + metrics flags
- `apps/api/app/deps.py` — DI: `get_llm_router()`, `get_agent_service()`, `get_billing_service()`, `get_artifact_store()`
- `apps/api/app/middleware/auth.py` — JWT verification, tenant/role resolution, structlog rebind
- `apps/api/app/middleware/security.py` — per-tenant rate limiting, security headers, Permissions-Policy
- `apps/api/app/services/agent/service.py` — `AgentService` with billing, timeout, quota
- `apps/api/app/services/llm/provider.py` — providers with SDK-aware retry (RETRYABLE_EXCEPTIONS)
- `apps/api/app/services/llm/circuit_breaker.py` — `CircuitBreaker` + `RedisCircuitBreaker`
- `shared/fm_shared/errors.py` — error hierarchy (IntegrationError, AuthError) with context in to_dict()
- `shared/fm_shared/storage/artifact_store.py` — sync + async methods
- `shared/fm_shared/model/schemas.py` — `ModelConfig`, `BlueprintNode` (with classification field)
- `apps/web/lib/api.ts` — typed API client with 18+ binding groups (including metrics, budgets.reforecast)
- `.github/workflows/ci.yml` — lint + pytest + integration tests

## Conventions

- Python 3.12+, type annotations, ruff-clean (E, F, I, N, W, UP, B, S)
- Pydantic `BaseModel` for all request bodies, `Field` with aliases for settings
- `tenant_conn(tenant_id)` async context manager for all DB access (RLS enforced)
- `structlog` for logging, domain errors (`LLMError`, `StorageError`, `IntegrationError`, `AuthError`)
- List endpoints return `{"items": [...], "total": N, "limit": N, "offset": N}`
- Tests: pytest + pytest-asyncio, mock `tenant_conn` and SDK, no real API calls
- Frontend: Next.js App Router, Tailwind, Shadcn UI, `fetchApi()` wrapper, strict TypeScript
- Auth pattern: `getAuthContext()` → redirect to `/login` if null, then `api.setAccessToken(ctx.accessToken)`
