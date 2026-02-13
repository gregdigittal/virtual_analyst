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


def _set_mc_progress(tenant_id: str, run_id: str, sims_completed: int, total: int) -> None:
    try:
        import redis

        r = redis.from_url(REDIS_URL)
        key = f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}"
        pct = round(100.0 * sims_completed / total, 1) if total else 0.0
        r.setex(
            key,
            MC_PROGRESS_TTL,
            json.dumps({"sims_completed": sims_completed, "total": total, "pct": pct}),
        )
        r.close()
    except Exception as e:
        logger.warning("mc_progress_redis_failed", error=str(e))


def _clear_mc_progress(tenant_id: str, run_id: str) -> None:
    try:
        import redis

        r = redis.from_url(REDIS_URL)
        r.delete(f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}")
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
        def progress_cb(sims_done: int, total: int) -> None:
            _set_mc_progress(tenant_id, run_id, sims_done, total)

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
        await conn.execute("SET app.tenant_id = ''")
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
    except (EngineError, StatementImbalanceError, ValueError) as e:
        logger.exception("run_mc_execute_failed", run_id=run_id, error=str(e))
        asyncio.run(_run_mc_fail_async(tenant_id, run_id, str(e)))
        raise
    except Exception as e:
        logger.exception("run_mc_execute_failed", run_id=run_id, error=str(e))
        asyncio.run(_run_mc_fail_async(tenant_id, run_id, str(e)))
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
