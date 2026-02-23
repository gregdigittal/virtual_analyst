"""H-01: Integrations API tests — connections, sync, snapshots, disconnect."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_artifact_store
from apps.api.app.main import app

TENANT = "tenant-h01"
USER = "user-h01"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    conn.transaction = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=None),
    ))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _cleanup():
    app.dependency_overrides.pop(get_artifact_store, None)


def test_initiate_requires_admin() -> None:
    """Default dev role is analyst but integrations requires OWNER_OR_ADMIN → 403."""
    r = TestClient(app).post(
        "/api/v1/integrations/connections",
        json={"provider": "xero"},
        headers=HEADERS,
    )
    assert r.status_code == 403


def test_list_connections_requires_admin() -> None:
    r = TestClient(app).get("/api/v1/integrations/connections", headers=HEADERS)
    assert r.status_code == 403


def test_list_connections_success() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.integrations.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.integrations.ensure_tenant", new_callable=AsyncMock),
    ):
        r = TestClient(app).get("/api/v1/integrations/connections", headers=HEADERS)
    assert r.status_code == 200
    assert "items" in r.json()


def test_get_connection_not_found() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.integrations.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.integrations.get_connection", new_callable=AsyncMock, return_value=None),
    ):
        r = TestClient(app).get("/api/v1/integrations/connections/conn-999", headers=HEADERS)
    assert r.status_code == 404


def test_get_connection_strips_oauth() -> None:
    row = MagicMock()
    row.__iter__ = MagicMock(return_value=iter([
        ("connection_id", "conn-1"), ("provider", "xero"), ("status", "connected"), ("oauth", {"access_token": "secret"}),
    ]))
    row.__getitem__ = MagicMock(side_effect=lambda k: {"connection_id": "conn-1", "provider": "xero", "status": "connected", "oauth": {"access_token": "secret"}}[k])

    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.integrations.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.integrations.get_connection", new_callable=AsyncMock, return_value=row),
    ):
        r = TestClient(app).get("/api/v1/integrations/connections/conn-1", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "oauth" not in data


def test_disconnect_not_found() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.integrations.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.integrations.delete_connection", new_callable=AsyncMock, return_value=False),
    ):
        r = TestClient(app).delete("/api/v1/integrations/connections/conn-999", headers=HEADERS)
    assert r.status_code == 404


def test_list_snapshots_connection_not_found() -> None:
    with (
        patch("apps.api.app.deps.ROLE_ANALYST", "owner"),
        patch("apps.api.app.routers.integrations.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.integrations.get_connection", new_callable=AsyncMock, return_value=None),
    ):
        r = TestClient(app).get("/api/v1/integrations/connections/conn-999/snapshots", headers=HEADERS)
    assert r.status_code == 404
