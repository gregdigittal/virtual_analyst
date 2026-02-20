# Project Context — Virtual Analyst

> Last updated: 2026-02-20T10:00:00Z
> Commit: 33dd2e8 — Round 23: P1-P10 feature enhancements
> Uncommitted: 12 files — backend test fixes, JWT audience bug fix, XSS entity_name validation
> Branch: main

## Architecture

- **Backend**: Python 3.12+, FastAPI, asyncpg (Supabase Postgres with RLS), Celery + Redis
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, Shadcn UI
- **LLM**: Hybrid — `LLMRouter` for single-turn structured output, `AgentService` (Claude Agent SDK) for multi-step tasks
- **Storage**: `ArtifactStore` (Supabase Storage or in-memory) with async wrappers, tenant-scoped via `tenant_conn()`
- **Auth**: Supabase Auth + optional SAML SSO (defusedxml), JWT verification, RBAC (owner/admin/analyst/investor)
- **Billing**: Stripe-backed `BillingService` with plan-aware LLM quota; usage meter uses `FOR UPDATE`
- **Deployment**: Vercel (frontend at virtual-analyst-ten.vercel.app), API on Render (free tier, cold-starts ~3–5 min)

## Recent Changes

### Round 23 (33dd2e8) — P1-P10 feature enhancements
- Excel export UI, scenario management, run configuration viewer
- Dashboard enhancements, chart improvements, comparison page
- Workflow detail page, version history, config viewer component

### Round 24 (uncommitted) — Test fixes + security hardening
- Fixed all 25 failing backend tests across 9 test files
- **JWT audience bug fix** (`auth.py`): `python-jose 3.5.0` doesn't support list audience — changed to manual audience check with `verify_aud: False`
- **XSS validation** (`schemas.py`): Added `@field_validator("entity_name")` to reject HTML tags in `Metadata`
- Test fix categories: Settings alias names, `tenant_conn` mocking, RBAC assertion updates, LLM provider mock ordering, billing patch paths, `ArtifactStore.load` sync mock

### Earlier rounds
- Round 22: Auth standardisation, W6 multi-tenancy, G-05 board pack builder, KPI cards
- Round 21: Logger.ts, middleware /compare, .env.example, api.boardPacks.update
- Round 20: Middleware auth for 22 routes, download fix, API_URL dedup, budget variance UI, ventures form
- Round 19: Pagination/filter (13 pages), form validation (16 forms), backend tests, competitive features (dashboard, tornado, MC fan chart, timeline, comments)
- Full history in BACKLOG.md completed rounds table

## Current State

- **Backend tests**: 214 passed, 0 failed, 18 skipped (integration + e2e gated by env vars)
- **Frontend tests**: 33 passed (5 test files — 3 component, 2 utility)
- **TypeScript**: 0 errors
- **Hosted API** (Render): Healthy — liveness, readiness, web root all passing
- **Hosted Web** (Vercel): Healthy at `virtual-analyst-ten.vercel.app`
- Agent SDK flags default to `true`; `claude-agent-sdk` is optional (`pip install .[agent]`)

## Backlog Summary

See `BACKLOG.md` for full details. Key items:
- **Ship blockers**: Commit test fixes (S-01), update CONTEXT.md (S-02 — this file)
- **High priority**: Backend test coverage for 18 untested routers (H-01), frontend page-level tests for 51 pages (H-02), board pack email distribution (H-03)
- **Medium**: Compare page entity scoping, budget `is_revenue` flag, nav sign-out auth migration, cursor prompt cleanup (47 files)
- **Nice to have**: Integration test Docker infra, Render cold-start mitigation, E2E Playwright tests, monitoring/alerting

## Key Files & Patterns

- `apps/api/app/core/settings.py` — all config, production validators, agent + metrics flags. Uses `alias=` (constructor requires alias names e.g. `SUPABASE_JWT_SECRET`)
- `apps/api/app/deps.py` — DI: `get_llm_router()`, `get_agent_service()`, `get_billing_service()`, `get_artifact_store()`, `require_role()`
- `apps/api/app/middleware/auth.py` — JWT verification (manual audience check for python-jose compat), tenant/role resolution, structlog rebind
- `apps/api/app/middleware/security.py` — per-tenant rate limiting, security headers, Permissions-Policy
- `apps/api/app/services/agent/service.py` — `AgentService` with billing, timeout, quota
- `apps/api/app/services/llm/provider.py` — providers with SDK-aware retry (RETRYABLE_EXCEPTIONS)
- `apps/api/app/services/llm/circuit_breaker.py` — `CircuitBreaker` + `RedisCircuitBreaker`
- `shared/fm_shared/errors.py` — error hierarchy (IntegrationError, AuthError) with context in to_dict()
- `shared/fm_shared/storage/artifact_store.py` — sync + async methods (`load()` is synchronous — mock with `MagicMock` not `AsyncMock`)
- `shared/fm_shared/model/schemas.py` — `ModelConfig`, `BlueprintNode`, `Metadata` (with HTML tag rejection on `entity_name`)
- `apps/web/lib/api.ts` — typed API client with 18+ binding groups
- `.github/workflows/ci.yml` — lint + pytest + integration tests

## Conventions

- Python 3.12+, type annotations, ruff-clean (E, F, I, N, W, UP, B, S)
- Pydantic `BaseModel` for all request bodies, `Field` with aliases for settings
- `tenant_conn(tenant_id)` async context manager for all DB access (RLS enforced)
- `structlog` for logging, domain errors (`LLMError`, `StorageError`, `IntegrationError`, `AuthError`)
- List endpoints return `{"items": [...], "total": N, "limit": N, "offset": N}`
- Tests: pytest + pytest-asyncio, mock `tenant_conn` with `_mock_tenant_conn` helper, no real API calls
- Frontend: Next.js App Router, Tailwind, Shadcn UI, `fetchApi()` wrapper, strict TypeScript
- Auth pattern: `getAuthContext()` → redirect to `/login` if null, then `api.setAccessToken(ctx.accessToken)`
- Design system: `VAButton`, `VACard`, `VAInput`, `VASelect`, `VASpinner`, `VAPagination`, `useToast` from `@/components/ui`

## Testing Notes

- Settings constructor in tests must use alias names: `Settings(SUPABASE_JWT_SECRET=..., ENVIRONMENT="test")`
- `tenant_conn` patch target: `apps.api.app.db.connection.tenant_conn` (middleware imports lazily) or `apps.api.app.routers.<router>.tenant_conn`
- Dev RBAC fallback: `ROLE_ANALYST` when no JWT secret; teams/billing routers require `OWNER_OR_ADMIN` — patch `deps.ROLE_ANALYST` to `"owner"` for validation tests
- LLM providers create real API clients in `__init__` — construct provider INSIDE `with patch` block
- Billing `get_settings` patch target: `apps.api.app.core.settings.get_settings` (lazy import in webhook handler)
