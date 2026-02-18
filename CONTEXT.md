# Project Context — Virtual Analyst

> Last updated: 2026-02-18T00:00:00Z
> Commit: 919781c — Catchup commit: prior phase features, migrations, web UI, tests
> Branch: main

## Architecture

- **Backend**: Python 3.12+, FastAPI, asyncpg (Supabase Postgres with RLS), Celery + Redis
- **Frontend**: Next.js 14 App Router, TypeScript, Tailwind CSS, Shadcn UI
- **LLM**: Hybrid — `LLMRouter` for single-turn structured output, `AgentService` (Claude Agent SDK) for multi-step tasks
- **Storage**: `ArtifactStore` (Supabase Storage or in-memory), tenant-scoped via `tenant_conn()`
- **Auth**: Supabase Auth + optional SAML SSO, JWT verification, RBAC (owner/admin/analyst/investor)
- **Billing**: Stripe-backed `BillingService` with plan-aware LLM quota enforcement
- **Deployment**: Vercel (frontend), custom domain `virtual-analyst.ai` configured

## Recent Changes (this commit)

- Committed all accumulated Phase 7-9 work: routers, services, web UI pages, migrations
- DB migrations 0042-0047: SAML certificates, LLM usage log, Excel ingestion sessions, org structures, RLS fixes, indexes
- Web app: 15+ new pages (activity, benchmark, covenants, documents, excel-import, marketplace, memos, org-structures, settings suite, ventures)
- Services: circuit breaker improvements, metering enhancements, provider updates, Excel parser, board pack export, Xero integration
- Tests: billing, currency, Excel, SAML, scenarios, valuation, security (auth bypass, input validation)
- Prior commit (02abee2): Full Agent SDK integration (Phases 1-6) with rectification fixes

## Current State

- All agent feature flags default to `true` (settings.py): `agent_sdk_enabled`, `agent_excel_ingestion_enabled`, `agent_draft_chat_enabled`, `agent_budget_nl_query_enabled`, `agent_reforecast_enabled`
- `claude-agent-sdk` is an optional dependency (`pip install .[agent]`)
- AgentService integrates with BillingService for quota/metering
- 43 agent-related tests pass (unit + integration)
- Custom domain `virtual-analyst.ai` pointed to Vercel (A → 216.150.1.1, CNAME www → project-specific Vercel DNS)

## In Progress / Next Steps

- `CURSOR_PROMPT_PRODUCTION_READINESS.md` is open — likely the next work item
- No known failing tests in the agent layer
- Prompt/cursor docs (CURSOR_PROMPT_*.md) remain untracked — reference only

## Key Files & Patterns

- `apps/api/app/core/settings.py` — all config including agent flags
- `apps/api/app/deps.py` — DI: `get_llm_router()`, `get_agent_service()`, `get_billing_service()`, `get_artifact_store()`
- `apps/api/app/services/agent/service.py` — `AgentService` with billing, timeout, quota
- `apps/api/app/services/agent/tools.py` — tenant-scoped budget/model tools
- `apps/api/app/services/agent/{excel,draft,budget,reforecast}_agent.py` — task-specific agents
- `apps/api/app/services/llm/router.py` — `LLMRouter` with `DEFAULT_POLICY` and failover
- `apps/api/app/services/llm/metering.py` — fallback usage tracking
- `apps/api/app/services/billing/service.py` — Stripe billing + LLM quota
- `apps/api/app/routers/` — all FastAPI endpoints
- `shared/fm_shared/model/` — `ModelConfig`, `run_engine`, `generate_statements`, KPIs
- `tests/conftest.py` — `minimal_model_config_dict()` fixture
- `.env.example` — all env vars with defaults

## Conventions

- Python 3.12+, type annotations on all functions, ruff-clean (E, F, I, N, W, UP, B, S)
- Pydantic `BaseModel` for request/response shapes, `Field` with aliases for settings
- `tenant_conn(tenant_id)` async context manager for all DB access (RLS enforced)
- `structlog` for logging, `LLMError` / `StorageError` for domain errors
- `HTTPException` in routers, never in services
- Agent tools are read-only by default; write ops require explicit design
- Tests: pytest + pytest-asyncio, mock `tenant_conn` and SDK, no real API calls
- Frontend: Next.js App Router, Tailwind, Shadcn UI components, `fetchApi()` wrapper
