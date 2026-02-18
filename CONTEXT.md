# Project Context — Virtual Analyst

> Last updated: 2026-02-18T12:00:00Z
> Commit: b566e3a — Production readiness: critical, high, and medium fixes (A-01 through C-11)
> Branch: main

## Architecture

- **Backend**: Python 3.12+, FastAPI, asyncpg (Supabase Postgres with RLS), Celery + Redis
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, Shadcn UI
- **LLM**: Hybrid — `LLMRouter` for single-turn structured output, `AgentService` (Claude Agent SDK) for multi-step tasks
- **Storage**: `ArtifactStore` (Supabase Storage or in-memory) with async wrappers, tenant-scoped via `tenant_conn()`
- **Auth**: Supabase Auth + optional SAML SSO (defusedxml), JWT verification, RBAC (owner/admin/analyst/investor)
- **Billing**: Stripe-backed `BillingService` with plan-aware LLM quota; usage meter uses `FOR UPDATE` for concurrency
- **Deployment**: Vercel (frontend at virtual-analyst.ai), API on Render/similar

## Recent Changes (this commit)

- CI: pytest + integration tests with Postgres service; action versions v4/v5
- Security: defusedxml for SAML, JWT startup guard, SAML assertion time/audience validation, Permissions-Policy header
- Auth: tenant_id type guard in production, role defaults to investor, /metrics protected by METRICS_SECRET
- LLM: retry catches actual SDK exceptions; agent tool kwargs whitelist with limit sanitization
- Performance: MC cap 10K, ArtifactStore async methods, 10MB body limit, per-tenant rate limiting
- Data: migration 0048 (search_path, RLS, indexes), billing FOR UPDATE, Excel binary storage
- API: 14 endpoints paginated, changeset Pydantic model, revenue/COGS classification improved
- Infra: Redis circuit breaker, SAML token via HttpOnly cookie, integration HTTP timeouts

## Current State

- All production readiness items (A-01 through C-11) are implemented
- Agent SDK flags default to `true`; `claude-agent-sdk` is optional (`pip install .[agent]`)
- Migration 0048 applied to Supabase
- 45 agent-related tests pass; CI pipeline configured to run all tests
- Custom domain `virtual-analyst.ai` active on Vercel

## In Progress / Next Steps

- Part E from CURSOR_PROMPT_PRODUCTION_READINESS.md: 17 frontend pages for backend features with no UI
- Part F: Additional test coverage (valuation, security, billing, scenarios, currency)
- Part G: Competitive features (dashboard KPIs, multi-entity comparison, report builder, scenario viz)

## Key Files & Patterns

- `apps/api/app/core/settings.py` — all config, production validators, agent + metrics flags
- `apps/api/app/deps.py` — DI: `get_llm_router()`, `get_agent_service()`, `get_billing_service()`, `get_artifact_store()`
- `apps/api/app/middleware/auth.py` — JWT verification, tenant/role resolution, structlog rebind
- `apps/api/app/middleware/security.py` — per-tenant rate limiting, security headers
- `apps/api/app/services/agent/service.py` — `AgentService` with billing, timeout, quota
- `apps/api/app/services/llm/provider.py` — `AnthropicProvider`, `OpenAIProvider` with SDK-aware retry
- `apps/api/app/services/llm/circuit_breaker.py` — `CircuitBreaker` (in-memory) + `RedisCircuitBreaker`
- `apps/api/app/services/billing/service.py` — Stripe billing + LLM quota with FOR UPDATE
- `shared/fm_shared/errors.py` — error hierarchy with context in to_dict()
- `shared/fm_shared/storage/artifact_store.py` — sync + async methods
- `shared/fm_shared/model/schemas.py` — `ModelConfig`, `BlueprintNode` (with classification field)
- `.github/workflows/ci.yml` — lint + pytest + integration tests

## Conventions

- Python 3.12+, type annotations, ruff-clean (E, F, I, N, W, UP, B, S)
- Pydantic `BaseModel` for all request bodies, `Field` with aliases for settings
- `tenant_conn(tenant_id)` async context manager for all DB access (RLS enforced)
- `structlog` for logging, domain errors (`LLMError`, `StorageError`, `IntegrationError`, `AuthError`)
- `HTTPException` in routers only, never in services
- List endpoints return `{"items": [...], "total": N, "limit": N, "offset": N}`
- Tests: pytest + pytest-asyncio, mock `tenant_conn` and SDK, no real API calls
- Frontend: Next.js App Router, Tailwind, Shadcn UI, `fetchApi()` wrapper
