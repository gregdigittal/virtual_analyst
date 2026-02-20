"""Unit tests for jobs API (enqueue, status)."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from apps.worker.celery_app import celery_app

# Force eager mode before importing app (which imports jobs router)
celery_app.conf.update(
    task_always_eager=True,
    task_eager_propagates=True,
)

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-1"


def test_enqueue_requires_x_tenant_id() -> None:
    """Enqueue returns 400 without X-Tenant-ID."""
    r = client.post("/api/v1/jobs/enqueue", json={"task": "add", "args": [1, 2]})
    assert r.status_code == 400


def test_enqueue_unknown_task_returns_400() -> None:
    """Enqueue returns 400 for unknown task name."""
    r = client.post(
        "/api/v1/jobs/enqueue",
        json={"task": "nonexistent", "args": []},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 400


def test_enqueue_returns_task_id() -> None:
    """Enqueue returns 202 with task_id; apply_async mocked to avoid broker."""
    from apps.api.app.routers.jobs import add as add_task

    mock_result = type("Result", (), {"id": "mock-task-id"})()
    with patch.object(add_task, "apply_async", return_value=mock_result):
        r = client.post(
            "/api/v1/jobs/enqueue",
            json={"task": "add", "args": [10, 20]},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 202
    data = r.json()
    assert data["task_id"] == "mock-task-id"


def test_get_job_status_returns_state_from_backend() -> None:
    """GET /jobs/{id} returns task state (mocked)."""
    with patch("apps.api.app.routers.jobs._task_tenant_get", return_value=TENANT):
        with patch("apps.api.app.routers.jobs._get_task_status") as m:
            m.return_value = {
                "task_id": "fake-id",
                "state": "SUCCESS",
                "result": 42,
            }
            r = client.get(
                "/api/v1/jobs/fake-id",
                headers={"X-Tenant-ID": TENANT},
            )
    assert r.status_code == 200
    body = r.json()
    assert body["task_id"] == "fake-id"
    assert body["state"] == "SUCCESS"
    assert body.get("result") == 42


def test_get_job_status_requires_x_tenant_id() -> None:
    """GET /jobs/{id} returns 400 without X-Tenant-ID."""
    r = client.get("/api/v1/jobs/some-id", headers={})
    assert r.status_code == 400
