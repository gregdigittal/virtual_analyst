"""PIM-1.1: Company universe API unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-pim-universe"
USER = "user-pim-test"

_COMPANY_DICT = {
    "company_id": "pco_abc123",
    "ticker": "AAPL",
    "company_name": "Apple Inc",
    "sector": "Technology",
    "sub_sector": None,
    "country_iso": "US",
    "market_cap_usd": 3000000.0,
    "currency": "USD",
    "exchange": "NASDAQ",
    "is_active": True,
    "tags": [],
    "notes": None,
    "created_at": None,
    "updated_at": None,
}


def _mock_conn(fetchrow_return=None, fetch_return=None, fetchval_return=None, execute_return=None):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetchval = AsyncMock(return_value=fetchval_return)
    conn.execute = AsyncMock(return_value=execute_return)
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _mock_tenant_conn_factory(fetchrow_return=None, fetch_return=None, fetchval_return=None, execute_return=None):
    def _make(_tenant_id):
        return _mock_conn(
            fetchrow_return=fetchrow_return,
            fetch_return=fetch_return,
            fetchval_return=fetchval_return,
            execute_return=execute_return,
        )
    return _make


@pytest.fixture(autouse=True)
def _bypass_pim_gate():
    """Bypass the DB subscription check but keep the tenant-ID validation."""
    async def _tenant_only(x_tenant_id: str = Header("", alias="X-Tenant-ID")):  # noqa: B008
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    app.dependency_overrides[require_pim_access] = _tenant_only
    yield
    app.dependency_overrides.pop(require_pim_access, None)


# --- Tests ---


def test_add_company_requires_tenant() -> None:
    r = client.post(
        "/api/v1/pim/universe",
        json={"ticker": "AAPL", "company_name": "Apple Inc"},
    )
    assert r.status_code == 400


def test_add_company_happy_path() -> None:
    make_conn = _mock_tenant_conn_factory(fetchrow_return=_COMPANY_DICT)
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.post(
            "/api/v1/pim/universe",
            json={"ticker": "AAPL", "company_name": "Apple Inc"},
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == "AAPL"
    assert data["company_name"] == "Apple Inc"
    assert data["company_id"] == "pco_abc123"


def test_add_company_pim_access_denied() -> None:
    async def _deny():
        raise HTTPException(403, "PIM is not enabled for this tenant's subscription")

    app.dependency_overrides[require_pim_access] = _deny
    make_conn = _mock_tenant_conn_factory(fetchrow_return=_COMPANY_DICT)
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.post(
            "/api/v1/pim/universe",
            json={"ticker": "AAPL", "company_name": "Apple Inc"},
            headers={"X-Tenant-ID": TENANT, "X-User-ID": USER},
        )
    # autouse fixture restores _tenant_only override after test
    assert r.status_code == 403


def test_list_companies_happy_path() -> None:
    row1 = dict(_COMPANY_DICT)
    row2 = dict(_COMPANY_DICT, company_id="pco_xyz456", ticker="MSFT", company_name="Microsoft Corp")

    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[row1, row2])
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=2)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)

    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/universe", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 2
    assert data["total"] == 2


def test_get_company_not_found() -> None:
    make_conn = _mock_tenant_conn_factory(fetchrow_return=None)
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.get(
            "/api/v1/pim/universe/pco_notexist",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 404


def test_get_company_happy_path() -> None:
    make_conn = _mock_tenant_conn_factory(fetchrow_return=_COMPANY_DICT)
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.get(
            "/api/v1/pim/universe/pco_abc123",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == "pco_abc123"
    assert data["ticker"] == "AAPL"


def test_update_company_not_found() -> None:
    # First fetchrow (existence check) returns None → 404
    make_conn = _mock_tenant_conn_factory(fetchrow_return=None)
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.patch(
            "/api/v1/pim/universe/pco_notexist",
            json={"company_name": "Updated Name"},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 404


def test_remove_company_not_found() -> None:
    make_conn = _mock_tenant_conn_factory(execute_return="DELETE 0")
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.delete(
            "/api/v1/pim/universe/pco_notexist",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 404


def test_remove_company_happy_path() -> None:
    make_conn = _mock_tenant_conn_factory(execute_return="DELETE 1")
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.delete(
            "/api/v1/pim/universe/pco_abc123",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 204


def test_list_sectors() -> None:
    sector_rows = [
        {"sector": "Technology", "count": 5},
        {"sector": "Fintech", "count": 3},
    ]
    make_conn = _mock_tenant_conn_factory(fetch_return=sector_rows)
    with patch("apps.api.app.routers.pim_universe.tenant_conn", side_effect=make_conn):
        r = client.get(
            "/api/v1/pim/universe/sectors/list",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert "sectors" in data
    assert len(data["sectors"]) == 2
    assert data["sectors"][0]["sector"] == "Technology"
    assert data["sectors"][0]["count"] == 5
