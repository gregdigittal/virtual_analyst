"""VA-P6-12: Workflow engine tests — template creation, stage advancement, routing."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-p6"
USER = "user-p6"


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_list_templates_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/workflows/templates")
    assert r.status_code == 400


def test_list_templates_success() -> None:
    with patch("apps.api.app.routers.workflows.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/workflows/templates", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert "templates" in data


def test_create_instance_requires_x_tenant_id() -> None:
    r = client.post(
        "/api/v1/workflows/instances",
        json={"template_id": "t1", "entity_type": "draft", "entity_id": "d1"},
    )
    assert r.status_code == 400


def test_create_instance_requires_body() -> None:
    r = client.post(
        "/api/v1/workflows/instances",
        json={},
        headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
    )
    assert r.status_code == 422
