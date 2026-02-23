"""H-01: Audit API tests — catalog, list events, export."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-h01"


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


def test_audit_requires_admin_role() -> None:
    """Default dev role is analyst, but audit requires OWNER_OR_ADMIN → 403."""
    r = client.get("/api/v1/audit/events", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 403


def test_catalog() -> None:
    with patch("apps.api.app.deps.ROLE_ANALYST", "owner"):
        r = client.get("/api/v1/audit/events/catalog", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert "events" in r.json()


def test_list_events_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.audit.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.audit.list_audit_events", new_callable=AsyncMock, return_value=[]),
    ):
        r = client.get("/api/v1/audit/events", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert r.json()["events"] == []


def test_export_json() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.audit.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.audit.list_audit_events", new_callable=AsyncMock, return_value=[]),
    ):
        r = client.get("/api/v1/audit/events/export?format=json", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert "content-disposition" in r.headers


def test_export_csv() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.audit.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.audit.list_audit_events", new_callable=AsyncMock, return_value=[]),
    ):
        r = client.get("/api/v1/audit/events/export?format=csv", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "audit_export.csv" in r.headers["content-disposition"]
