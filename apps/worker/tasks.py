"""Celery tasks with retry and DLQ on final failure."""

from __future__ import annotations

import asyncio
import json
from typing import Any

import asyncpg
import structlog

from apps.worker.celery_app import REDIS_URL, celery_app, push_to_dlq
from shared.fm_shared.analysis.monte_carlo import run_monte_carlo
from shared.fm_shared.errors import StorageError
from shared.fm_shared.model import (
    ModelConfig,
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


async def _set_mc_progress(tenant_id: str, run_id: str, current: int, total: int) -> None:
    """Write MC simulation progress to Redis (REM-03 / CR-S5: redis.asyncio)."""
    import redis.asyncio as aioredis

    try:
        key = f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}"
        payload = json.dumps({"current": current, "total": total, "pct": round(current / max(total, 1) * 100, 1)})
        async with aioredis.from_url(REDIS_URL) as r:
            await r.setex(key, MC_PROGRESS_TTL, payload)
    except Exception:
        pass


async def _clear_mc_progress(tenant_id: str, run_id: str) -> None:
    """Delete MC simulation progress key from Redis (REM-03 / CR-S5: redis.asyncio)."""
    import redis.asyncio as aioredis

    try:
        async with aioredis.from_url(REDIS_URL) as r:
            await r.delete(f"{MC_PROGRESS_KEY}:{tenant_id}:{run_id}")
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

        # Monte Carlo with progress (long-running, outside transaction).
        # progress_cb is sync (run_monte_carlo interface); schedule the async write
        # via ensure_future so it runs when the event loop next gets control.
        def progress_cb(current: int, total: int) -> None:
            asyncio.ensure_future(_set_mc_progress(tenant_id, run_id, current, total))

        mc_result = run_monte_carlo(
            config,
            num_simulations,
            seed,
            scenario_id=scenario_id,
            progress_callback=progress_cb,
        )
        await _clear_mc_progress(tenant_id, run_id)

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
    await _clear_mc_progress(tenant_id, run_id)
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


# ---------------------------------------------------------------------------
# PIM-2.4: Monthly FRED economic context refresh
# ---------------------------------------------------------------------------


async def _refresh_economic_context_async(tenant_id: str) -> dict[str, Any]:
    """Pull FRED indicators, classify regime, and store snapshot for one tenant."""
    import uuid

    from apps.api.app.core.settings import get_settings
    from apps.api.app.services.pim.fred import FREDError, fetch_indicators
    from apps.api.app.services.pim.regime import classify_regime

    settings = get_settings()
    if not settings.fred_api_key:
        logger.warning("fred_api_key_missing", msg="FRED_API_KEY not configured; skipping economic refresh")
        return {"tenant_id": tenant_id, "status": "skipped", "reason": "no_api_key"}

    indicators = await fetch_indicators(settings.fred_api_key)
    regime_result = classify_regime(indicators)
    snapshot_id = f"eco_{uuid.uuid4().hex[:16]}"

    pool = await asyncpg.create_pool(settings.database_url, statement_cache_size=0, min_size=1, max_size=2)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "SELECT set_config('app.tenant_id', $1, true)", tenant_id
            )
            await conn.execute(
                """INSERT INTO pim_economic_snapshots
                   (tenant_id, snapshot_id, fetched_at, gdp_growth_pct, cpi_yoy_pct,
                    unemployment_rate, yield_spread_10y2y, ism_pmi, regime, regime_confidence,
                    indicators_agreeing, indicators_total, indicators_raw)
                   VALUES ($1, $2, $3::timestamptz, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb)""",
                tenant_id,
                snapshot_id,
                indicators["fetched_at"],
                indicators.get("gdp_growth_pct"),
                indicators.get("cpi_yoy_pct"),
                indicators.get("unemployment_rate"),
                indicators.get("yield_spread_10y2y"),
                indicators.get("ism_pmi"),
                regime_result.regime,
                regime_result.regime_confidence,
                regime_result.indicators_agreeing,
                regime_result.indicators_total,
                json.dumps(indicators.get("indicators_raw", {})),
            )
    finally:
        await pool.close()

    logger.info(
        "economic_snapshot_stored",
        tenant_id=tenant_id,
        snapshot_id=snapshot_id,
        regime=regime_result.regime,
        confidence=regime_result.regime_confidence,
    )
    return {
        "tenant_id": tenant_id,
        "snapshot_id": snapshot_id,
        "regime": regime_result.regime,
        "confidence": regime_result.regime_confidence,
    }


async def _refresh_economic_all_tenants_async() -> dict[str, Any]:
    """Refresh economic context for all PIM-enabled tenants."""
    from apps.api.app.core.settings import get_settings

    settings = get_settings()
    conn = await asyncpg.connect(settings.database_url, statement_cache_size=0)
    try:
        tenant_rows = await conn.fetch(
            """SELECT DISTINCT bs.tenant_id
               FROM billing_subscriptions bs
               JOIN billing_plans bp ON bp.plan_id = bs.plan_id
               WHERE bs.status IN ('active', 'trialing')
                 AND (bp.features_json->>'pim')::boolean = true"""
        )
    finally:
        await conn.close()

    all_results: dict[str, Any] = {}
    for row in tenant_rows:
        tid = row["tenant_id"]
        try:
            result = await _refresh_economic_context_async(tid)
            all_results[tid] = result
        except Exception:
            logger.warning("economic_refresh_tenant_failed", tenant_id=tid, exc_info=True)
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
def refresh_economic_context(self, tenant_id: str | None = None) -> dict[str, Any]:
    """PIM-2.4: Monthly FRED economic context refresh.

    Pulls GDP, CPI, unemployment, yield spread, and PMI from FRED.
    Classifies economic regime and stores snapshot in pim_economic_snapshots.

    Scheduled monthly (see celery_app beat schedule).
    If tenant_id is provided, refreshes only that tenant.
    If None, refreshes all PIM-enabled tenants.
    """
    try:
        if tenant_id:
            result = asyncio.run(_refresh_economic_context_async(tenant_id))
        else:
            result = asyncio.run(_refresh_economic_all_tenants_async())
        return result
    except Exception as e:
        logger.exception("refresh_economic_context_failed", tenant_id=tenant_id, error=str(e))
        raise


# ---------------------------------------------------------------------------
# PIM-5.3: Backtest summary materialised view refresh (every 30 minutes)
# ---------------------------------------------------------------------------


async def _refresh_backtest_summary_mv_async() -> dict[str, Any]:
    """Execute REFRESH MATERIALIZED VIEW CONCURRENTLY on pim_backtest_summary_mv.

    CONCURRENTLY allows reads during refresh (requires the unique index on
    (tenant_id, strategy_label) created in migration 0069).
    """
    from apps.api.app.core.settings import get_settings

    settings = get_settings()
    conn = await asyncpg.connect(
        settings.database_url,
        statement_cache_size=0,
    )
    try:
        await conn.execute(
            "REFRESH MATERIALIZED VIEW CONCURRENTLY pim_backtest_summary_mv"
        )
        logger.info("pim_backtest_summary_mv_refreshed")
        return {"status": "ok", "view": "pim_backtest_summary_mv"}
    finally:
        await conn.close()


@celery_app.task(
    bind=True,
    base=DLQTask,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def refresh_pim_backtest_summary_mv(self) -> dict[str, Any]:  # type: ignore[override]
    """PIM-5.3: Refresh pim_backtest_summary_mv materialised view.

    Scheduled every 30 minutes via celery beat (see celery_app.py).
    Uses CONCURRENTLY to allow reads during refresh.
    """
    try:
        return asyncio.run(_refresh_backtest_summary_mv_async())
    except Exception as e:
        logger.exception("refresh_backtest_summary_mv_failed", error=str(e))
        raise
