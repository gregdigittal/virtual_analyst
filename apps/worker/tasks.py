"""Celery tasks with retry and DLQ on final failure."""

from __future__ import annotations

from apps.worker.celery_app import celery_app, push_to_dlq


class DLQTask(celery_app.Task):
    """Base task that pushes to DLQ when retries are exhausted."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        retries = getattr(self.request, "retries", None) or 0
        max_retries = getattr(self, "max_retries", 3)
        if retries >= max_retries:
            push_to_dlq(task_id, self.name, exc, args, kwargs)
        super().on_failure(exc, task_id, args, kwargs, einfo)


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
