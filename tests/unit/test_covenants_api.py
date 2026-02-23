"""H-01: Covenants API tests — metric-refs, list, create, delete."""
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
    conn.transaction = MagicMock(return_value=MagicMock(
        __aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=None),
    ))
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_list_metric_refs() -> None:
    r = client.get("/api/v1/covenants/metric-refs", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert "metric_refs" in data
    assert "operators" in data


def test_list_covenants_requires_tenant() -> None:
    r = client.get("/api/v1/covenants")
    assert r.status_code == 400


def test_list_covenants_success() -> None:
    with patch("apps.api.app.routers.covenants.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get("/api/v1/covenants", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    assert "items" in r.json()


def test_create_covenant_invalid_metric_ref() -> None:
    with patch("apps.api.app.routers.covenants.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/covenants",
            json={"label": "Test", "metric_ref": "bogus_ref", "operator": ">", "threshold_value": 1.5},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 400


def test_create_covenant_invalid_operator() -> None:
    from apps.api.app.db.covenants import COVENANT_METRIC_REFS

    ref = sorted(COVENANT_METRIC_REFS)[0] if COVENANT_METRIC_REFS else "revenue_growth"
    with patch("apps.api.app.routers.covenants.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/covenants",
            json={"label": "Test", "metric_ref": ref, "operator": "==", "threshold_value": 1.5},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 400


def test_create_covenant_success() -> None:
    from apps.api.app.db.covenants import COVENANT_METRIC_REFS

    ref = sorted(COVENANT_METRIC_REFS)[0] if COVENANT_METRIC_REFS else "revenue_growth"
    with (
        patch("apps.api.app.routers.covenants.tenant_conn", side_effect=_mock_tenant_conn),
        patch("apps.api.app.routers.covenants.create_audit_event", new_callable=AsyncMock),
    ):
        r = client.post(
            "/api/v1/covenants",
            json={"label": "Debt ratio", "metric_ref": ref, "operator": "<", "threshold_value": 3.0},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 201
    assert "covenant_id" in r.json()


def test_delete_covenant_not_found() -> None:
    def _conn_delete_0(_tid: str):
        conn = MagicMock()
        conn.execute = AsyncMock(return_value="DELETE 0")
        conn.transaction = MagicMock(return_value=MagicMock(
            __aenter__=AsyncMock(), __aexit__=AsyncMock(return_value=None),
        ))
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.covenants.tenant_conn", side_effect=_conn_delete_0):
        r = client.delete("/api/v1/covenants/cv-999", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 404
