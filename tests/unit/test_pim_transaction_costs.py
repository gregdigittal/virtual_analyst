"""PIM-5.5: Transaction cost reporting (SR-7) unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app
from apps.api.app.services.pim.transaction_costs import (
    TransactionCostRecord,
    compute_net_return,
)

client = TestClient(app)

TENANT = "tenant-pim-txcost"

_COST_ROW = {
    "cost_id": "tc_1",
    "backtest_id": "bt_1",
    "cost_type": "commission",
    "estimated_bps": 5.0,
    "actual_bps": None,
    "n_rebalances": 12,
    "description": "Round-trip commission at 5 bps per rebalance",
    "created_at": None,
}


def _make_cm(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _simple_conn(fetchrow_return=None, fetch_return=None):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    return conn


@pytest.fixture(autouse=True)
def _bypass_pim_gate():
    async def _tenant_only(x_tenant_id: str = Header("", alias="X-Tenant-ID")):  # noqa: B008
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    app.dependency_overrides[require_pim_access] = _tenant_only
    yield
    app.dependency_overrides.pop(require_pim_access, None)


# --- Service unit tests ---


class TestComputeNetReturn:
    def test_subtracts_total_cost_from_gross_return(self):
        # 12 rebalances × 5 bps = 60 bps = 0.006 total cost
        net = compute_net_return(
            gross_return=0.15,
            estimated_bps=5.0,
            n_rebalances=12,
        )
        assert abs(net - (0.15 - 0.006)) < 1e-9

    def test_zero_rebalances_returns_gross(self):
        net = compute_net_return(gross_return=0.10, estimated_bps=10.0, n_rebalances=0)
        assert net == 0.10

    def test_actual_bps_used_when_provided(self):
        # actual_bps takes precedence over estimated_bps
        net = compute_net_return(
            gross_return=0.10,
            estimated_bps=5.0,
            n_rebalances=10,
            actual_bps=3.0,
        )
        # 10 × 3 bps = 30 bps = 0.003
        assert abs(net - (0.10 - 0.003)) < 1e-9

    def test_high_cost_can_produce_negative_net(self):
        net = compute_net_return(gross_return=0.01, estimated_bps=100.0, n_rebalances=20)
        # 20 × 100 bps = 2000 bps = 0.20 total cost → net = 0.01 - 0.20 = -0.19
        assert net < 0.0


# --- API endpoint tests ---


def test_add_cost_requires_tenant() -> None:
    r = client.post(
        "/api/v1/pim/backtest/bt_1/costs",
        json={"cost_type": "commission", "estimated_bps": 5.0, "n_rebalances": 12},
    )
    assert r.status_code == 400


def test_add_cost_backtest_not_found() -> None:
    conn = _simple_conn(fetchrow_return=None)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            "/api/v1/pim/backtest/bt_notexist/costs",
            json={"cost_type": "commission", "estimated_bps": 5.0, "n_rebalances": 12},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 404


def test_add_cost_happy_path() -> None:
    backtest_row = {"backtest_id": "bt_1", "n_periods": 12}
    cost_row = dict(_COST_ROW)
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=[backtest_row, cost_row])
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            "/api/v1/pim/backtest/bt_1/costs",
            json={"cost_type": "commission", "estimated_bps": 5.0, "n_rebalances": 12},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 201
    data = r.json()
    assert data["cost_type"] == "commission"
    assert data["estimated_bps"] == 5.0
    assert data["backtest_id"] == "bt_1"


def test_list_costs_happy_path() -> None:
    conn = _simple_conn(fetch_return=[_COST_ROW])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/backtest/bt_1/costs",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["cost_type"] == "commission"


def test_list_costs_returns_empty() -> None:
    conn = _simple_conn(fetch_return=[])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/backtest/bt_1/costs",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_add_cost_invalid_cost_type() -> None:
    conn = _simple_conn(fetchrow_return={"backtest_id": "bt_1", "n_periods": 12})
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            "/api/v1/pim/backtest/bt_1/costs",
            json={"cost_type": "invalid_type", "estimated_bps": 5.0, "n_rebalances": 12},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 422
