# Virtual Analyst — Claude Code Project Context

> Last updated: 2026-03-13
> Stack: Python 3.12 + FastAPI (backend) · Next.js 14 App Router + TypeScript (frontend)
> Hosted: Vercel (web) + Render (API) · DB: Supabase PostgreSQL (RLS + pgbouncer)

---

## Project Overview

**As-Is:** AI-powered financial modeling platform combining deterministic engines (DCF, Monte Carlo, budgeting, AFS) with LLM-assisted analysis for accountants and financial analysts.

**To-Be (with PIM):** AI-powered financial modeling and portfolio intelligence platform combining deterministic engines with LLM-assisted analysis, real-time sentiment ingestion, Markov-chain portfolio scoring, and PE benchmarking for institutional-grade investment decision-making.

Production URLs:
- Frontend: `https://www.virtual-analyst.ai` (Vercel)
- Backend API: `https://virtual-analyst-api.onrender.com/api/v1` (Render, free tier — cold starts ~3–5 min, mitigated by keepalive cron)
- Test user: `greg@disruptiveconsult.com` / `Test1234`
- Test tenant: `f004fe0c-da81-49ab-afab-9a9a8286211e`

---

## Repository Layout

```
virtual_analyst/
├── apps/
│   ├── api/app/
│   │   ├── core/           settings.py (all config, alias= required in tests)
│   │   ├── db/             connection.py, migrations/ (55+ versioned .sql files)
│   │   ├── middleware/     auth.py (ES256 JWKS JWT, RBAC), security.py (rate limiting)
│   │   ├── routers/        35 routers (all covered by tests)
│   │   └── services/       afs/, agent/, billing/, email, excel*, board_pack_export
│   ├── web/
│   │   ├── app/(app)/      58 authenticated pages (Next.js App Router)
│   │   ├── components/     ui/ (VA design system), InstructionsDrawer, VASidebar
│   │   ├── e2e/            68 Playwright spec files
│   │   ├── lib/            api.ts (~1850 lines), auth.ts, supabase/, instructions-config.ts
│   │   └── tests/          components/, hooks/, lib/, pages/ (Vitest)
│   ├── worker/             Celery worker (sync redis.Redis — REM-03 pending migration)
│   └── excel-addin/        Excel add-in
└── shared/
    └── fm_shared/
        ├── analysis/       valuation.py (DCF), monte_carlo.py, consolidation.py, sensitivity.py
        ├── model/          engine.py, schemas.py, statements.py, evaluator.py, kpis.py
        └── storage/        artifact_store.py (load() is sync — mock with MagicMock not AsyncMock)
```

---

## Tech Stack

### Backend (Python 3.12+)
- **Framework**: FastAPI (async-first), Uvicorn
- **Database**: asyncpg → Supabase PostgreSQL (pgbouncer, `statement_cache_size=0` required)
- **ORM/Queries**: Raw asyncpg with `tenant_conn(tenant_id)` context manager (RLS enforced)
- **Auth**: ES256 JWKS JWT verification, RBAC (owner/admin/analyst/investor), Supabase Auth, optional SAML SSO (defusedxml)
- **Workers**: Celery + Redis (currently sync `redis.Redis` — REM-03: migrate to `redis.asyncio`)
- **LLM**: Anthropic Claude (`LLMRouter` for structured single-turn, `AgentService` for multi-step via Claude Agent SDK)
- **Financial Engine**: `shared/fm_shared/` — DCF, Monte Carlo, AFS, consolidation (deterministic, no LLM)
- **Observability**: structlog, sentry-sdk[fastapi], prometheus-client, opentelemetry
- **Migrations**: Custom SQL at `apps/api/app/db/migrations/` (no Alembic)

### Frontend (TypeScript, strict mode)
- **Framework**: Next.js 14 App Router, React 18
- **Styling**: Tailwind CSS, VA design system tokens (va-midnight, va-blue, va-panel, va-border)
- **Charts**: Recharts (current) — D3.js planned for PIM Markov visualisations
- **Auth**: `@supabase/ssr`, `@supabase/supabase-js`, `getAuthContext()` → redirect to `/login`
- **API client**: `apps/web/lib/api.ts` (~1850 lines, typed bindings, `fetchApi()` wrapper)
- **Error tracking**: `@sentry/nextjs` (sentry.server/client/edge.config.ts, DSN-gated)
- **Testing**: Vitest (159 tests, jsdom), Playwright (68 E2E specs)

### Design System
- Dark theme: `bg-va-midnight`, `text-va-text`, accent `va-blue`
- Fonts: Sora (brand), Inter (sans), JetBrains Mono (mono)
- Components: VAButton, VACard, VATabs, VABadge, VAInput, VASelect, VASpinner, VAPagination
- Glow shadows: `va-glow-blue`, `va-glow-violet`

---

## Key Files & Patterns

### Backend
| File | Purpose |
|---|---|
| `apps/api/app/core/settings.py` | All config. **Tests must use alias names**: `Settings(SUPABASE_JWT_SECRET=..., ENVIRONMENT="test")` |
| `apps/api/app/deps.py` | DI: `get_llm_router()`, `get_agent_service()`, `get_billing_service()`, `require_role()` |
| `apps/api/app/middleware/auth.py` | ES256 JWKS JWT, tenant/role resolution, auto-provisioning, structlog rebind |
| `apps/api/app/middleware/security.py` | Per-tenant rate limiting, security headers, Permissions-Policy |
| `apps/api/app/services/agent/service.py` | `AgentService` — billing, timeout, quota enforcement |
| `apps/api/app/services/llm/provider.py` | LLM providers with SDK-aware retry (RETRYABLE_EXCEPTIONS) |
| `shared/fm_shared/errors.py` | Error hierarchy: `LLMError`, `StorageError`, `IntegrationError`, `AuthError` |
| `shared/fm_shared/model/schemas.py` | `ModelConfig`, `BlueprintNode`, `Metadata` (HTML tag rejection on `entity_name`) |

### Frontend
| File | Purpose |
|---|---|
| `apps/web/lib/api.ts` | Typed API client (~1850 lines, 18+ binding groups) |
| `apps/web/lib/auth.ts` | `getAuthContext()`, `signOut()` — shared auth utilities |
| `apps/web/components/VASidebar.tsx` | Nav sidebar (SETUP / CONFIGURE / ANALYZE / REPORT) |
| `apps/web/components/InstructionsDrawer.tsx` | Floating help + route-aware manual content |

---

## Conventions

### Python
- PEP 8 via ruff (`select = ["E","F","I","N","W","UP","B","S"]`)
- Type annotations required on all public functions (`disallow_untyped_defs = true`)
- Async-first: all route handlers are `async def`; no sync blocking in async context
- Pydantic `BaseModel` for all request/response bodies; `Field` with `alias=` for settings
- `tenant_conn(tenant_id)` async context manager for all DB access (RLS enforced)
- structlog for all logging; domain errors from `shared/fm_shared/errors.py`
- List endpoints return `{"items": [...], "total": N, "limit": N, "offset": N}`
- SQL: parameterised queries only — never f-string SQL, never string concatenation
- All financial calcs: reference CFA/IAS/ISA standard in docstrings

### TypeScript
- Strict mode enabled (`strict: true` in tsconfig); no `any` in financial data types
- Next.js App Router patterns: `app/(app)/` for authenticated pages
- Auth pattern: `getAuthContext()` → redirect to `/login` if null, then `api.setAccessToken(ctx.accessToken)`
- `fetchApi()` wrapper for all API calls (handles auth headers, error normalisation)
- VA design system components only — no ad-hoc Tailwind without VA tokens
- All financial figures: thousands separators, decimal places, currency symbols

### Financial
- Monetary values: use `Decimal` types or explicit rounding — never raw `float` for money
- Monte Carlo: reproducible seeding — seed must be logged for audit trail
- Budget models: validate sum of line items == reported total
- AFS outputs: must balance (assets == liabilities + equity) or flag discrepancy
- All percentage calculations: handle division by zero
- Currency values: always include currency code — no naked numbers

---

## Testing

### Backend
- `pytest tests/unit/ tests/golden/ -v --tb=short` — unit + golden (fast, no DB)
- `INTEGRATION_TESTS=1 pytest tests/integration/ -v --tb=short` — needs PostgreSQL
- `asyncio_mode = "auto"` — all async tests work without `@pytest.mark.asyncio`
- `tenant_conn` patch target: `apps.api.app.db.connection.tenant_conn` or `apps.api.app.routers.<router>.tenant_conn`
- Dev RBAC fallback: `ROLE_ANALYST` when no JWT secret; patch `deps.ROLE_ANALYST` to `"owner"` for validation tests
- LLM providers create real API clients in `__init__` — construct provider INSIDE `with patch` block
- `ArtifactStore.load()` is synchronous — mock with `MagicMock`, not `AsyncMock`

### Frontend
- `cd apps/web && npm run test` — Vitest (159 tests, jsdom)
- Stable router refs in `tests/pages/setup.tsx` to prevent `useEffect` infinite loops

### E2E
- `cd apps/web && npm run e2e` — Playwright (68 specs, chromium)
- Seeded IDs in `apps/web/e2e/functional/fixtures/seeded-ids.json`
- Needs running backend + frontend; CI uses `E2E_BASE_URL`

---

## Current Backlog State

| Tier | Status | Key Items |
|---|---|---|
| Tier 1–3 (Ship / High / Medium) | ✅ Done | All resolved |
| Tier 4 AFS | ✅ Done (2026-03-15) | All P1–P6 complete |
| Tier 5 Nice-to-Have | 7 open | Integration tests (N-01), E2E gaps (N-03), rate-limit tests (N-04), OpenAPI codegen (N-05), load tests (N-06), monitoring (N-07), CI enhancements (N-08) |
| Tier 6 PIM Gates | ✅ Done (2026-03-15) | All 7 gates closed — GATE-1–7 verified and GATE-3 implemented |
| Tier 7 PIM Sprint 0 | ✅ Done (2026-03-15) | All 23 REM items closed — REM-12 (split afs.py) done last |
| Tier 8 PIM Module | **7 sprints, 71 items** | Sprints 0–6 (~22 weeks) |

Full backlog: `BACKLOG.md` · Full context: `CONTEXT.md` · PIM build plan: `docs/plans/2026-03-09-pim-v2-build-plan.md`

---

## PIM Transition — To-Be Stack Delta

When working on PIM Sprint 0+ items, be aware of these additions:

| Addition | Detail |
|---|---|
| `redis.asyncio` | Replace sync `redis.Redis` everywhere (REM-03) |
| `asyncio.Lock` + TTL on JWKS | Cache JWKS — eliminate per-request fetch race (REM-02) |
| `ProcessPoolExecutor` | Parallelise Monte Carlo per-sim loop (REM-07) |
| Numba `@njit` | JIT-accelerated Markov loops — functions must be pure (no Python objects in hot path) |
| QuantEcon `MarkovChain` | 81-state Markov transition matrix; rows must sum to 1.0 |
| pg_partman | Time-series partitioning on PIM tables; queries must include partition key |
| Materialised views | PIM analytics — document refresh schedule, flag stale data risk |
| Polygon.io / FRED / EDGAR | External APIs — rate limiting, caching, graceful degradation required |
| D3.js | Interactive Markov state-transition diagrams (frontend) |
| 13 new DB tables | 9 PIM + 4 DTF — see `docs/plans/2026-03-09-pim-v2-build-plan.md` |

---

## Sub-agents

See `.claude/agents/` for detailed prompts. Quick reference:

| Agent | Use for |
|---|---|
| `platform-remediator` | Fix REM-XX sprint 0 backlog items |
| `security-auditor` | Read-only security review |
| `financial-engine` | DCF, Monte Carlo, shared/fm_shared work |
| `supabase-schema-agent` | RLS policies, migrations, type generation |
| `llm-integration-agent` | LLMRouter and AgentService patterns |
| `pim-architect` | PIM module architecture and design |
| `pim-builder` | PIM module implementation |
| `dtf-engineer` | DTF calibration/validation CLI |
| `frontend-builder` | Next.js pages, Tailwind, VA design system |
| `financial-reviewer` | Read-only financial/statistical validation |
