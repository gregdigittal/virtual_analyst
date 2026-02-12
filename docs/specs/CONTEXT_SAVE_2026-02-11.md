# Context Save — 2026-02-11

## Repo state
- **Branch:** main
- **Last push:** 694f16d — Metrics: exclude /api/v1/metrics from latency; require X-Tenant-ID on summary; dashboard auth headers
- **Remote:** https://github.com/gregdigittal/virtual_analyst.git

### Incremental (2026-02-11)
- **Metrics middleware:** Requests to `/api/v1/metrics` are excluded from latency recording to avoid self-pollution of the ring buffer.
- **Metrics summary auth:** `GET /api/v1/metrics/summary` now requires `X-Tenant-ID` header; returns 400 if missing. Dashboard `fetchSummary` sends `X-Tenant-ID` (from `user_metadata.tenant_id` or `user.id`) and `Authorization: Bearer <access_token>`.

## Completed (Phase 1 core)

### Backend
- **Model layer** (`shared/fm_shared/model/`): Pydantic `model_config_v1` schemas; `CalcGraph.from_blueprint` with topo_sort and cycle detection (`GraphCycleError`); safe AST evaluator (`evaluate`, `EvalError`); `run_engine(config, scenario_overrides)` → time_series; `generate_statements` → IS/BS/CF + periods; `calculate_kpis` (margins, ratios, FCF, CCC from BS/IS).
- **Storage:** `ArtifactStore` (Supabase or in-memory), path `{tenant_id}/{artifact_type}/{id}.json`; used for `model_config_v1` and `run_results`.
- **API:** `POST/GET/PATCH /api/v1/baselines`, `POST/GET /api/v1/runs`, `GET /api/v1/runs/{id}/statements`, `GET /api/v1/runs/{id}/kpis`. Transactions on create_baseline, patch_baseline, create_run; `X-Tenant-ID` and `X-User-ID`; `CreateBaselineBody.model_config_payload` (alias `model_config`); `PatchBaselineBody.status` Literal.
- **Audit:** Migration `0006_audit_log.sql` (append-only, RLS); `create_audit_event(conn, tenant_id, ..., user_id=...)` for baseline.created/accessed, run.created/accessed.
- **Deps:** `get_artifact_store()` with Supabase when configured; `get_settings()` cached with `@lru_cache`; `datetime.now(timezone.utc)` (no `utcnow`); `StrEnum` for error enums; `drv:` prefix fixed to `[4:]` in engine.

### Frontend
- **Auth:** Supabase SSR (client + server + middleware); login page; protected `/baselines`, `/runs`; home redirects to `/baselines` when logged in.
- **Pages:** Baselines list, baseline detail + “Run model”, runs list, run detail (Statements tab: IS/BS/CF tables; KPIs tab).
- **API client:** `lib/api.ts` with `NEXT_PUBLIC_API_URL`, `X-Tenant-ID` from session user id.

### Tests
- **Unit:** `tests/unit/test_graph.py` (topo_sort, cycle detection), `tests/unit/test_evaluator.py` (arithmetic, variables, min/max/clamp/if_else, unsafe rejected). 11 tests, all passing.
- **E2E:** `tests/e2e/test_hosted_health.py` for hosted API/web (optional in CI).

### Build / CI
- Ruff and black pass (after fixes). Next.js `npm run build` passes. Python 3.12 required; mypy still has existing errors (asyncpg stubs, some annotations).

## Environment
- **API:** Render (`virtual-analyst-api`); start `uvicorn apps.api.app.main:app --host 0.0.0.0 --port $PORT`. Env: `DATABASE_URL`, `REDIS_URL`, `SUPABASE_*`, `CORS_ALLOWED_ORIGINS`.
- **Web:** Vercel; root `apps/web`; env: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_API_URL`.
- **DB:** Supabase Postgres; run migrations 0001, 0002, 0006 in SQL Editor. RLS uses `current_setting('app.tenant_id', true)` where applicable.

## Next build tasks (from backlog)
- **Phase 1:** Complete (VA-P1-01 through VA-P1-23, including unit/integration/perf/golden tests, indexing, pooling, query optimization, performance dashboard).
- **Phase 2 (next):** VA-P2-01 Background job queue (M) — Celery + Redis, retries, DLQ. Then VA-P2-02 Draft session CRUD, VA-P2-03 LLM provider abstraction, etc.
- **CI:** Run integration tests with `INTEGRATION_TESTS=1` and `DATABASE_URL` set.

## Notes
- Frontend uses session `user.id` as tenant; no multi-tenant UI yet.
- ArtifactStore Supabase upload uses `bucket.upload(path, body, file_options=...)` (storage3 API).
- Run artifact stores `run_results` with key `{run_id}_statements`; `run_artifacts` table row links run to storage_path.
