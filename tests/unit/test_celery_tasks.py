"""Unit tests for Celery tasks and job queue (VA-P2-01)."""

from __future__ import annotations

import pytest

from apps.worker.celery_app import celery_app

# Force eager mode on the already-constructed Celery instance
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
)

from apps.worker.tasks import add, fail_then_dlq


def test_add_task_executes_eagerly() -> None:
    """Task 'add' computes correctly via apply (eager, no broker)."""
    result = add.apply(args=[2, 3])
    assert result.get() == 5


def test_add_task_retry_config() -> None:
    """Task 'add' has retry and DLQ base configured."""
    assert add.max_retries == 3
    assert add.autoretry_for == (Exception,)
    assert add.retry_backoff is True


def test_fail_then_dlq_raises() -> None:
    """Task 'fail_then_dlq' raises ValueError when called."""
    with pytest.raises(ValueError, match="expected failure"):
        fail_then_dlq("expected failure")
