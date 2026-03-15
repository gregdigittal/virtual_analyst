"""Celery application: Redis broker/backend, retries, DLQ."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime

import structlog
from celery import Celery
from celery.schedules import crontab

logger = structlog.get_logger()

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")
BROKER_URL = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)
DLQ_REDIS_KEY = "celery:dlq"
DLQ_MAX_ENTRIES = 10_000

celery_app = Celery(
    "virtual_analyst",
    broker=BROKER_URL,
    backend=RESULT_BACKEND,
    include=["apps.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_default_retry_delivery_mode="transient",
    beat_schedule={
        "refresh-sentiment-every-6h": {
            "task": "apps.worker.tasks.refresh_sentiment",
            "schedule": 21600.0,  # 6 hours
        },
        "refresh-economic-context-monthly": {
            "task": "apps.worker.tasks.refresh_economic_context",
            # First day of each month at 02:00 UTC — well before market open
            "schedule": crontab(hour=2, minute=0, day_of_month=1),
        },
        # PIM-5.3: Backtest summary materialised view — every 30 minutes (UTC)
        "refresh-pim-backtest-summary-mv-every-30m": {
            "task": "apps.worker.tasks.refresh_pim_backtest_summary_mv",
            "schedule": 1800.0,  # 30 minutes
        },
    },
)

def push_to_dlq(
    task_id: str,
    task_name: str,
    exception: BaseException,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    """Append failed job to DLQ Redis list (call only after retries exhausted).

    Uses redis.asyncio (REM-03 / CR-S5). Called from Celery on_failure which runs
    after asyncio.run() has returned, so a fresh asyncio.run() is safe here.
    """
    import redis.asyncio as aioredis

    async def _write() -> None:
        entry = {
            "task_id": task_id,
            "task_name": task_name,
            "exception": str(exception),
            "args": list(args),
            "kwargs": kwargs,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        async with aioredis.from_url(REDIS_URL) as r:
            await r.lpush(DLQ_REDIS_KEY, json.dumps(entry))  # type: ignore[misc]
            await r.ltrim(DLQ_REDIS_KEY, 0, DLQ_MAX_ENTRIES - 1)  # type: ignore[misc]

    try:
        asyncio.run(_write())
    except Exception:
        logger.error("Failed to push task %s to DLQ", task_id, exc_info=True)
