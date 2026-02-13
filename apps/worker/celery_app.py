"""Celery application: Redis broker/backend, retries, DLQ."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime

import structlog
from celery import Celery

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
)

def push_to_dlq(
    task_id: str,
    task_name: str,
    exception: BaseException,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    """Append failed job to DLQ Redis list (call only after retries exhausted)."""
    try:
        import redis

        r = redis.from_url(REDIS_URL)
        try:
            entry = {
                "task_id": task_id,
                "task_name": task_name,
                "exception": str(exception),
                "args": list(args),
                "kwargs": kwargs,
                "timestamp": datetime.now(UTC).isoformat(),
            }
            r.lpush(DLQ_REDIS_KEY, json.dumps(entry))
            r.ltrim(DLQ_REDIS_KEY, 0, DLQ_MAX_ENTRIES - 1)
        finally:
            r.close()
    except Exception:
        logger.error("Failed to push task %s to DLQ", task_id, exc_info=True)
