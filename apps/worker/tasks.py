"""Celery tasks with retry and DLQ on final failure."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import asyncpg
import structlog
from apps.worker.celery_app import REDIS_URL, celery_app, push_to_dlq
from shared.fm_shared.analysis.monte_carlo import run_monte_carlo
from shared.fm_shared.errors import EngineError, StorageError
from shared.fm_shared.model import (
    ModelConfig,
    StatementImbalanceError,
    calculate_kpis,
    generate_statements,
    run_engine,
)
from shared.fm_shared.model.schemas import ScenarioOverride
from shared.fm_shared.storage import ArtifactStore

logger = structlog.get_logger()

MC_PROGRESS_KEY = "run:mc_progress"
MC_PROGRESS_TTL = 86400  # 24h


class DLQTask(celery_app.Task):
    """Base task that pushes to DLQ when retries are exhausted."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        retries = getattr(self.request, "retries", None) or 0
        max_retries = getattr(self, "max_retries", 3)
        if retries >= max_retries:
            push_to_dlq(task_id, self.name, exc, args, kwargs)
        super().on_failure(exc, task_id, args, kwargs, einfo)


def _artifact_store() -> ArtifactStore:
    from apps.api.app.core.settings import get_settings

    settings = get_settings()
    client: Any = None
    if settings.supabase_url and (settings.supabase_service_key or settings.supabase_anon_key):
        try:
            from supabase import create_client

            client = create_client(
                settings.supabase_url,
                settings.supabase_service_key or settings.supabase_anon_key,
            )
        except Exception:
            pass
    return ArtifactStore(supabase_client=client)


def _set_mc_progress(tenant_id: str, run_id: str, current: int, total: int) -> None:
    try:
        import redis

        r = redis.from_url(REDIS_URL)
        try:
            key = f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}"
            payload = json.dumps({"current": current, "total": total, "pct": round(current / max(total, 1) * 100, 1)})
            r.setex(key, MC_PROGRESS_TTL, payload)
        finally:
            r.close()
    except Exception:
        pass


def _clear_mc_progress(tenant_id: str, run_id: str) -> None:
    try:
        import redis

        r = redis.from_url(REDIS_URL)
        try:
            r.delete(f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}")
        finally:
            r.close()
    except Exception:
        pass


async def _run_mc_execute_async(
    tenant_id: str,
    run_id: str,
    baseline_id: str,
    baseline_version: str,
    scenario_id: str | None,
    num_simulations: int,
    seed: int,
) -> None:
    # Worker runs in a separate process without the API connection pool.
    # We use raw asyncpg.connect and manually set/clear app.tenant_id for RLS.
    from apps.api.app.core.settings import get_settings

    settings = get_settings()
    store = _artifact_store()
    artifact_id = f"{baseline_id}_{baseline_version}"
    try:
        config_dict = store.load(tenant_id, "model_config_v1", artifact_id)
    except StorageError as e:
        if e.code == "ERR_STOR_NOT_FOUND":
            raise ValueError(f"Baseline artifact not found: {artifact_id}") from e
        raise
    config = ModelConfig.model_validate(config_dict)

    scenario_overrides: list[ScenarioOverride] | None = None
    if scenario_id and config.scenarios:
        for sc in config.scenarios:
            if sc.scenario_id == scenario_id:
                scenario_overrides = list(sc.overrides)
                break

    # 1. Deterministic run → statements + KPIs
    time_series = run_engine(config, scenario_overrides)
    statements = generate_statements(config, time_series)
    kpis = calculate_kpis(statements)
    run_artifact_id = f"{run_id}_statements"
    run_results_payload = {
        "statements": {
            "income_statement": statements.income_statement,
            "balance_sheet": statements.balance_sheet,
            "cash_flow": statements.cash_flow,
            "periods": statements.periods,
        },
        "kpis": kpis,
        "time_series": time_series,
    }
    storage_path = store.save(tenant_id, "run_results", run_artifact_id, run_results_payload)

    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("SET app.tenant_id = $1", tenant_id)
        # Transition to running + store deterministic results
        async with conn.transaction():
            await conn.execute(
                "UPDATE runs SET status = 'running' WHERE tenant_id = $1 AND run_id = $2",
                tenant_id,
                run_id,
            )
            await conn.execute(
                """INSERT INTO run_artifacts (tenant_id, run_id, artifact_type, storage_path)
                   VALUES ($1, $2, 'run_results', $3)
                   ON CONFLICT (tenant_id, run_id, artifact_type, storage_path) DO NOTHING""",
                tenant_id,
                run_id,
                storage_path,
            )

        # Monte Carlo with progress (long-running, outside transaction)
        def progress_cb(current: int, total: int) -> None:
            _set_mc_progress(tenant_id, run_id, current, total)

        mc_result = run_monte_carlo(
            config,
            num_simulations,
            seed,
            scenario_id=scenario_id,
            progress_callback=progress_cb,
        )
        _clear_mc_progress(tenant_id, run_id)

        mc_payload = {
            "num_simulations": mc_result.num_simulations,
            "seed": mc_result.seed,
            "percentiles": mc_result.percentiles,
            "summary": mc_result.summary,
        }
        mc_artifact_id = f"{run_id}_mc"
        mc_path = store.save(tenant_id, "run_results", mc_artifact_id, mc_payload)

        # Atomically store MC artifact + mark succeeded
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO run_artifacts (tenant_id, run_id, artifact_type, storage_path)
                   VALUES ($1, $2, 'mc_results', $3)
                   ON CONFLICT (tenant_id, run_id, artifact_type, storage_path) DO NOTHING""",
                tenant_id,
                run_id,
                mc_path,
            )
            await conn.execute(
                "UPDATE runs SET status = 'succeeded', completed_at = now() WHERE tenant_id = $1 AND run_id = $2",
                tenant_id,
                run_id,
            )
    finally:
        try:
            await conn.execute("SET app.tenant_id = ''")
        except Exception:
            pass
        await conn.close()


@celery_app.task(
    bind=True,
    base=DLQTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def run_mc_execute(
    self,
    tenant_id: str,
    run_id: str,
    baseline_id: str,
    baseline_version: str,
    scenario_id: str | None = None,
    num_simulations: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Execute run with deterministic engine + MC; store results and update run status."""
    try:
        asyncio.run(
            _run_mc_execute_async(
                tenant_id,
                run_id,
                baseline_id,
                baseline_version,
                scenario_id,
                num_simulations,
                seed,
            )
        )
        return {"run_id": run_id, "status": "succeeded"}
    except Exception as e:
        logger.exception("mc_simulation_failed", tenant_id=tenant_id, run_id=run_id, error=str(e))
        try:
            asyncio.run(_run_mc_fail_async(tenant_id, run_id, str(e)))
        except Exception as fail_err:
            logger.error("mc_fail_update_failed", error=str(fail_err))
        raise


async def _run_mc_fail_async(tenant_id: str, run_id: str, error_message: str) -> None:
    from apps.api.app.core.settings import get_settings

    settings = get_settings()
    _clear_mc_progress(tenant_id, run_id)
    conn = await asyncpg.connect(settings.database_url)
    try:
        await conn.execute("SET app.tenant_id = $1", tenant_id)
        await conn.execute(
            "UPDATE runs SET status = 'failed', error_message = $3, completed_at = now() WHERE tenant_id = $1 AND run_id = $2",
            tenant_id,
            run_id,
            error_message[:2000] if error_message else None,
        )
    finally:
        try:
            await conn.execute("SET app.tenant_id = ''")
        except Exception:
            pass
        await conn.close()


@celery_app.task(
    bind=True,
    base=DLQTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def add(self, x: int, y: int) -> int:
    """Example task: add two numbers. Succeeds immediately."""
    return x + y


@celery_app.task(
    bind=True,
    base=DLQTask,
    autoretry_for=(ValueError,),
    retry_backoff=True,
    retry_backoff_max=60,
    retry_jitter=True,
    max_retries=3,
)
def fail_then_dlq(self, message: str) -> str:
    """Example task: always raises; after 3 retries goes to DLQ."""
    raise ValueError(message)


# ---------------------------------------------------------------------------
# PIM-1.6: Sentiment refresh task
# ---------------------------------------------------------------------------

async def _refresh_sentiment_async(tenant_id: str) -> dict[str, Any]:
    """Refresh sentiment signals for all companies in a tenant's universe."""
    from apps.api.app.core.settings import get_settings
    from apps.api.app.services.llm.router import LLMRouter
    from apps.api.app.services.pim.sentiment_ingestor import SentimentIngestor

    settings = get_settings()
    pool = await asyncpg.create_pool(settings.database_url, min_size=1, max_size=5, statement_cache_size=0)
    try:
        llm_router = LLMRouter()
        ingestor = SentimentIngestor(
            polygon_api_key=settings.polygon_api_key,
            llm_router=llm_router,
            db_pool=pool,
        )
        results = await ingestor.refresh_all(tenant_id)
        return {"tenant_id": tenant_id, "results": results}
    finally:
        await pool.close()


async def _refresh_sentiment_all_tenants_async() -> dict[str, Any]:
    """Refresh sentiment for all tenants that have active PIM universes."""
    from apps.api.app.core.settings import get_settings

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        tenant_rows = await conn.fetch(
            "SELECT DISTINCT tenant_id FROM pim_universes WHERE is_active = true"
        )
    finally:
        await conn.close()

    all_results: dict[str, Any] = {}
    for row in tenant_rows:
        tid = row["tenant_id"]
        try:
            result = await _refresh_sentiment_async(tid)
            all_results[tid] = result.get("results", {})
        except Exception:
            logger.warning("sentiment_refresh_tenant_failed", tenant_id=tid, exc_info=True)
            all_results[tid] = {"error": "failed"}
    return all_results


@celery_app.task(
    bind=True,
    base=DLQTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=2,
)
def refresh_sentiment(self, tenant_id: str | None = None) -> dict[str, Any]:
    """PIM-1.6: Refresh sentiment signals from Polygon.io + LLM extraction.

    If tenant_id is provided, refreshes only that tenant.
    If None, refreshes all tenants with active PIM universes.
    """
    try:
        if tenant_id:
            result = asyncio.run(_refresh_sentiment_async(tenant_id))
        else:
            result = asyncio.run(_refresh_sentiment_all_tenants_async())
        return result
    except Exception as e:
        logger.exception("refresh_sentiment_failed", tenant_id=tenant_id, error=str(e))
        raise
