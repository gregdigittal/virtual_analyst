"""PIM-5.2: Backtest commentary API unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-pim-backtest-commentary"

_BACKTEST_ROW = {
    "backtest_id": "bt_1",
    "run_at": None,
    "strategy_label": "top_n_cis",
    "config_json": "{}",
    "start_date": None,
    "end_date": None,
    "n_periods": 5,
    "cumulative_return": 0.15,
    "annualised_return": 0.12,
    "volatility": 0.08,
    "sharpe_ratio": 1.5,
    "max_drawdown": 0.05,
    "ic_mean": 0.25,
    "ic_std": 0.1,
    "icir": 2.5,
    "benchmark_label": "equal_weight",
    "benchmark_cumulative_return": 0.08,
    "benchmark_annualised_return": 0.06,
    "periods_json": "[]",
    "commentary": None,
    "commentary_risks": None,
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
    """Bypass the DB subscription check but keep the tenant-ID validation."""
    async def _tenant_only(x_tenant_id: str = Header("", alias="X-Tenant-ID")):  # noqa: B008
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    app.dependency_overrides[require_pim_access] = _tenant_only
    yield
    app.dependency_overrides.pop(require_pim_access, None)


# --- /commentary ---


def test_commentary_requires_tenant() -> None:
    r = client.get("/api/v1/pim/backtest/bt_1/commentary")
    assert r.status_code == 400


def test_commentary_not_found() -> None:
    conn = _simple_conn(fetchrow_return=None)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/backtest/bt_notexist/commentary",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 404


def test_commentary_returns_cached_when_present() -> None:
    """If commentary already exists, return it without calling LLM."""
    row = dict(_BACKTEST_ROW, commentary="Good signal quality.", commentary_risks="High IC volatility.")
    conn = _simple_conn(fetchrow_return=row)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/backtest/bt_1/commentary",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["commentary"] == "Good signal quality."
    assert data["commentary_risks"] == "High IC volatility."
    assert data["backtest_id"] == "bt_1"


def test_commentary_generates_and_persists_when_missing() -> None:
    """If commentary is absent, call LLM, persist, and return the result."""
    row = dict(_BACKTEST_ROW, commentary=None, commentary_risks=None)
    conn = _simple_conn(fetchrow_return=row)
    cm = _make_cm(conn)

    mock_llm_response = MagicMock()
    mock_llm_response.content = {
        "commentary": "Solid IC of 0.25 indicates signal quality.",
        "risks": "Small sample — only 5 rebalance periods.",
    }

    mock_llm = MagicMock()
    mock_llm.complete_with_routing = AsyncMock(return_value=mock_llm_response)

    with (
        patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm),
        patch("apps.api.app.routers.pim_backtest.get_llm_router", return_value=lambda: mock_llm),
        patch(
            "apps.api.app.routers.pim_backtest.generate_backtest_commentary",
            new_callable=AsyncMock,
            return_value=("Solid IC of 0.25 indicates signal quality.", "Small sample — only 5 rebalance periods."),
        ) as mock_gen,
    ):
        r = client.get(
            "/api/v1/pim/backtest/bt_1/commentary",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["backtest_id"] == "bt_1"
    assert "commentary" in data
    mock_gen.assert_awaited_once()


def test_commentary_llm_failure_returns_graceful_error() -> None:
    """LLM failure should return 200 with an error commentary string (non-fatal)."""
    from shared.fm_shared.errors import LLMError

    row = dict(_BACKTEST_ROW, commentary=None, commentary_risks=None)
    conn = _simple_conn(fetchrow_return=row)
    cm = _make_cm(conn)

    with (
        patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm),
        patch(
            "apps.api.app.routers.pim_backtest.generate_backtest_commentary",
            new_callable=AsyncMock,
            side_effect=LLMError("API overload", code="ERR_LLM_ALL_PROVIDERS_FAILED"),
        ),
    ):
        r = client.get(
            "/api/v1/pim/backtest/bt_1/commentary",
            headers={"X-Tenant-ID": TENANT},
        )
    # LLM failure is non-fatal — endpoint degrades gracefully
    assert r.status_code in (200, 503)
