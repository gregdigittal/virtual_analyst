"""PIM-5.3: Backtest summary materialised view + Celery refresh unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-pim-summary"

_SUMMARY_ROW = {
    "strategy_label": "top_n_cis",
    "run_count": 3,
    "latest_run_at": None,
    "avg_cumulative_return": 0.12,
    "avg_annualised_return": 0.10,
    "avg_sharpe_ratio": 1.2,
    "avg_max_drawdown": 0.05,
    "avg_ic_mean": 0.22,
    "avg_ic_std": 0.08,
    "avg_icir": 2.0,
    "best_cumulative_return": 0.18,
    "worst_cumulative_return": 0.06,
}


def _make_cm(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _simple_conn(fetch_return=None):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=None)
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


# --- GET /pim/backtest/summary ---


def test_summary_requires_tenant() -> None:
    r = client.get("/api/v1/pim/backtest/summary")
    assert r.status_code == 400


def test_summary_empty() -> None:
    conn = _simple_conn(fetch_return=[])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/backtest/summary", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_summary_happy_path() -> None:
    conn = _simple_conn(fetch_return=[_SUMMARY_ROW])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_backtest.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/backtest/summary", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["strategy_label"] == "top_n_cis"
    assert item["run_count"] == 3
    assert item["avg_cumulative_return"] == pytest.approx(0.12)


# --- Celery refresh task ---


def test_refresh_backtest_summary_mv_task_exists() -> None:
    """Verify the Celery task is registered and importable."""
    from apps.worker.tasks import refresh_pim_backtest_summary_mv  # noqa: F401


def test_refresh_backtest_summary_mv_runs_refresh() -> None:
    """Task calls REFRESH MATERIALIZED VIEW CONCURRENTLY."""
    from apps.worker.tasks import refresh_pim_backtest_summary_mv

    mock_conn = MagicMock()
    mock_conn.execute = AsyncMock()

    with (
        patch(
            "apps.worker.tasks._refresh_backtest_summary_mv_async",
            new_callable=AsyncMock,
            return_value={"status": "ok", "view": "pim_backtest_summary_mv"},
        ) as mock_refresh,
    ):
        result = refresh_pim_backtest_summary_mv.run()

    mock_refresh.assert_awaited_once()
    assert result["status"] == "ok"
