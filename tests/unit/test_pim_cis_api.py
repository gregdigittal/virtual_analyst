"""PIM CIS and Economic Context API tests.

Covers:
  GET  /pim/economic/snapshots
  GET  /pim/economic/current
  POST /pim/cis/compute
  POST /pim/cis/factor-attribution
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import get_llm_router, require_pim_access
from apps.api.app.main import app
from apps.api.app.services.llm.provider import LLMResponse, TokenUsage

client = TestClient(app)

TENANT = "tenant-pim-cis"

_SNAPSHOT_ROW = {
    "snapshot_id": "snap_1",
    "fetched_at": None,
    "gdp_growth_pct": 2.5,
    "cpi_yoy_pct": 3.2,
    "unemployment_rate": 3.8,
    "yield_spread_10y2y": 0.4,
    "ism_pmi": 51.5,
    "regime": "expansion",
    "regime_confidence": 0.82,
    "indicators_agreeing": 4,
    "indicators_total": 5,
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


# ---------------------------------------------------------------------------
# GET /pim/economic/snapshots
# ---------------------------------------------------------------------------


def test_economic_snapshots_requires_tenant() -> None:
    r = client.get("/api/v1/pim/economic/snapshots")
    assert r.status_code == 400


def test_economic_snapshots_empty() -> None:
    conn = _simple_conn(fetch_return=[])
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.get("/api/v1/pim/economic/snapshots", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert data["snapshots"] == []
    assert data["limit"] == 12


def test_economic_snapshots_returns_rows() -> None:
    conn = _simple_conn(fetch_return=[_SNAPSHOT_ROW])
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.get("/api/v1/pim/economic/snapshots", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert len(data["snapshots"]) == 1
    assert data["snapshots"][0]["regime"] == "expansion"
    assert data["snapshots"][0]["gdp_growth_pct"] == 2.5


# ---------------------------------------------------------------------------
# GET /pim/economic/current
# ---------------------------------------------------------------------------


def test_economic_current_requires_tenant() -> None:
    r = client.get("/api/v1/pim/economic/current")
    assert r.status_code == 400


def test_economic_current_not_found() -> None:
    conn = _simple_conn(fetchrow_return=None)
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.get("/api/v1/pim/economic/current", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 404


def test_economic_current_returns_snapshot() -> None:
    conn = _simple_conn(fetchrow_return=_SNAPSHOT_ROW)
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.get("/api/v1/pim/economic/current", headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 200
    data = r.json()
    assert data["snapshot_id"] == "snap_1"
    assert data["regime"] == "expansion"
    assert data["regime_confidence"] == pytest.approx(0.82)


# ---------------------------------------------------------------------------
# POST /pim/cis/compute
# ---------------------------------------------------------------------------


def test_cis_compute_requires_tenant() -> None:
    r = client.post("/api/v1/pim/cis/compute", json={"companies": [{"company_id": "co-1"}]})
    assert r.status_code == 400


def test_cis_compute_empty_companies_rejected() -> None:
    r = client.post(
        "/api/v1/pim/cis/compute",
        json={"companies": []},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 422


def test_cis_compute_single_company_no_factors() -> None:
    """Company with no factor data still produces a CIS score (defaults to 50)."""
    conn = _simple_conn(fetchrow_return=None)  # no economic snapshot
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.post(
            "/api/v1/pim/cis/compute",
            json={"companies": [{"company_id": "co-1"}]},
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["companies"][0]["company_id"] == "co-1"
    assert 0.0 <= data["companies"][0]["cis_score"] <= 100.0


def test_cis_compute_with_factors() -> None:
    conn = _simple_conn(fetchrow_return={"regime": "expansion"})
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.post(
            "/api/v1/pim/cis/compute",
            json={
                "companies": [
                    {
                        "company_id": "co-strong",
                        "dcf_upside_pct": 30.0,
                        "roe": 25.0,
                        "avg_sentiment_score": 0.7,
                        "trend_direction": "improving",
                    }
                ]
            },
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 1
    assert data["current_regime"] == "expansion"
    cis = data["companies"][0]["cis_score"]
    assert cis > 50.0, f"Expected CIS > 50 with strong inputs, got {cis}"


def test_cis_compute_multiple_companies_sorted_descending() -> None:
    conn = _simple_conn(fetchrow_return=None)
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.post(
            "/api/v1/pim/cis/compute",
            json={
                "companies": [
                    {"company_id": "co-weak", "roe": 1.0},
                    {"company_id": "co-strong", "roe": 40.0, "dcf_upside_pct": 50.0},
                ]
            },
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 200
    data = r.json()
    scores = [c["cis_score"] for c in data["companies"]]
    assert scores == sorted(scores, reverse=True)


def test_cis_compute_invalid_weights_rejected() -> None:
    conn = _simple_conn(fetchrow_return=None)
    with patch("apps.api.app.routers.pim_cis.tenant_conn", side_effect=lambda _t: _make_cm(conn)):
        r = client.post(
            "/api/v1/pim/cis/compute",
            json={
                "companies": [{"company_id": "co-1"}],
                "weights": {
                    "fundamental_quality": 0.9,
                    "fundamental_momentum": 0.9,
                    "idiosyncratic_sentiment": 0.1,
                    "sentiment_momentum": 0.1,
                    "sector_positioning": 0.1,
                },
            },
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /pim/cis/factor-attribution
# ---------------------------------------------------------------------------


def _mock_llm_response(content: dict):
    mock_llm = MagicMock()
    mock_llm.complete_with_routing = AsyncMock(
        return_value=LLMResponse(
            content=content,
            raw_text="",
            tokens=TokenUsage(prompt_tokens=100, completion_tokens=100, total_tokens=200),
            latency_ms=50,
            model="claude-sonnet",
            provider="anthropic",
            cost_estimate_usd=0.001,
        )
    )
    return mock_llm


def test_factor_attribution_requires_tenant() -> None:
    r = client.post(
        "/api/v1/pim/cis/factor-attribution",
        json={"company_id": "co-1", "cis_score": 72.5},
    )
    assert r.status_code == 400


def test_factor_attribution_happy_path() -> None:
    mock_llm = _mock_llm_response({
        "narrative": "Score driven by strong quality.",
        "top_driver": "fundamental_quality",
        "risk_note": "Momentum is weak.",
    })
    app.dependency_overrides[get_llm_router] = lambda: mock_llm
    try:
        r = client.post(
            "/api/v1/pim/cis/factor-attribution",
            json={
                "company_id": "co-1",
                "cis_score": 72.5,
                "fundamental_quality": 85.0,
                "fundamental_momentum": 40.0,
                "current_regime": "expansion",
            },
            headers={"X-Tenant-ID": TENANT},
        )
    finally:
        app.dependency_overrides.pop(get_llm_router, None)

    assert r.status_code == 200
    data = r.json()
    assert data["company_id"] == "co-1"
    assert data["cis_score"] == pytest.approx(72.5)
    assert "narrative" in data
    assert data["top_driver"] == "fundamental_quality"
