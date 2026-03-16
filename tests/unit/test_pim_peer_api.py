"""PIM-7.1: Peer comparison percentile ranking unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app
from apps.api.app.routers.pim_peer import _percentile_rank, _quartile, _rank_metric

client = TestClient(app)

TENANT = "tenant-peer-test"
BENCHMARK_ID = "bench-abc123"
ASSESSMENT_ID = "assess-xyz"


def _make_cm(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _simple_conn(fetch_return=None, fetchrow_return=None, execute_return=None):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.execute = AsyncMock(return_value=execute_return or "")
    return conn


@pytest.fixture(autouse=True)
def _bypass_pim_gate():
    async def _tenant_only(x_tenant_id: str = Header("", alias="X-Tenant-ID")):  # noqa: B008
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    app.dependency_overrides[require_pim_access] = _tenant_only
    yield
    app.dependency_overrides.pop(require_pim_access, None)


_BENCHMARK_ROW = {
    "benchmark_id": BENCHMARK_ID,
    "tenant_id": TENANT,
    "vintage_year": 2020,
    "strategy": "buyout",
    "geography": "global",
    "dpi_p25": 0.5,
    "dpi_p50": 1.0,
    "dpi_p75": 1.5,
    "tvpi_p25": 1.2,
    "tvpi_p50": 1.8,
    "tvpi_p75": 2.5,
    "irr_p25": 0.10,
    "irr_p50": 0.15,
    "irr_p75": 0.22,
    "fund_count": 85,
    "data_source": "Cambridge Associates",
    "as_of_date": None,
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
}

_ASSESSMENT_ROW = {
    "assessment_id": ASSESSMENT_ID,
    "vintage_year": 2020,
    "dpi": 1.2,
    "tvpi": 2.0,
    "irr": 0.18,
}


# --- percentile rank unit tests ---


class TestPercentileRank:
    def test_at_p25_is_25(self) -> None:
        assert _percentile_rank(0.5, p25=0.5, p50=1.0, p75=1.5) == pytest.approx(25.0)

    def test_at_p50_is_50(self) -> None:
        assert _percentile_rank(1.0, p25=0.5, p50=1.0, p75=1.5) == pytest.approx(50.0)

    def test_at_p75_is_75(self) -> None:
        assert _percentile_rank(1.5, p25=0.5, p50=1.0, p75=1.5) == pytest.approx(75.0)

    def test_midpoint_between_p25_and_p50(self) -> None:
        # midpoint between 0.5 and 1.0 → 37.5th percentile
        rank = _percentile_rank(0.75, p25=0.5, p50=1.0, p75=1.5)
        assert rank == pytest.approx(37.5)

    def test_below_p25_is_below_25(self) -> None:
        rank = _percentile_rank(0.0, p25=0.5, p50=1.0, p75=1.5)
        assert rank < 25.0

    def test_above_p75_is_above_75(self) -> None:
        rank = _percentile_rank(2.0, p25=0.5, p50=1.0, p75=1.5)
        assert rank > 75.0
        assert rank < 100.0

    def test_rank_never_exceeds_99(self) -> None:
        rank = _percentile_rank(1_000_000.0, p25=0.5, p50=1.0, p75=1.5)
        assert rank <= 99.0


class TestQuartile:
    def test_rank_80_is_top_quartile(self) -> None:
        assert _quartile(80.0) == 1

    def test_rank_60_is_second_quartile(self) -> None:
        assert _quartile(60.0) == 2

    def test_rank_30_is_third_quartile(self) -> None:
        assert _quartile(30.0) == 3

    def test_rank_10_is_bottom_quartile(self) -> None:
        assert _quartile(10.0) == 4


class TestRankMetric:
    def test_none_value_gives_no_rank(self) -> None:
        r = _rank_metric("dpi", None, 0.5, 1.0, 1.5)
        assert r.percentile_rank is None
        assert r.quartile is None

    def test_missing_benchmark_gives_no_rank(self) -> None:
        r = _rank_metric("tvpi", 1.5, None, None, None)
        assert r.percentile_rank is None

    def test_full_rank_computed(self) -> None:
        r = _rank_metric("irr", 0.18, 0.10, 0.15, 0.22)
        assert r.percentile_rank is not None
        assert r.quartile is not None
        assert r.quartile_label is not None


# --- POST /pim/peer/benchmarks ---


def test_create_benchmark_requires_tenant() -> None:
    r = client.post("/api/v1/pim/peer/benchmarks", json={})
    assert r.status_code == 400


def test_create_benchmark_invalid_strategy() -> None:
    body = {"vintage_year": 2020, "strategy": "hedge_fund", "geography": "global"}
    r = client.post("/api/v1/pim/peer/benchmarks", json=body, headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 422


def test_create_benchmark_happy_path() -> None:
    conn = _simple_conn(fetchrow_return=_BENCHMARK_ROW)
    cm = _make_cm(conn)

    body = {
        "vintage_year": 2020,
        "strategy": "buyout",
        "geography": "global",
        "dpi_p25": 0.5,
        "dpi_p50": 1.0,
        "dpi_p75": 1.5,
        "fund_count": 85,
        "data_source": "Cambridge Associates",
    }
    with patch("apps.api.app.routers.pim_peer.tenant_conn", side_effect=lambda _t: cm):
        r = client.post("/api/v1/pim/peer/benchmarks", json=body, headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 201
    data = r.json()
    assert data["benchmark_id"] == BENCHMARK_ID
    assert data["fund_count"] == 85


# --- GET /pim/peer/benchmarks ---


def test_list_benchmarks_empty() -> None:
    count_row = {"n": 0}
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=count_row)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_peer.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/peer/benchmarks", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    assert r.json()["total"] == 0


# --- DELETE /pim/peer/benchmarks/{id} ---


def test_delete_not_found() -> None:
    conn = _simple_conn(execute_return="DELETE 0")
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_peer.tenant_conn", side_effect=lambda _t: cm):
        r = client.delete(f"/api/v1/pim/peer/benchmarks/{BENCHMARK_ID}", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 404


def test_delete_happy_path() -> None:
    conn = _simple_conn(execute_return="DELETE 1")
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_peer.tenant_conn", side_effect=lambda _t: cm):
        r = client.delete(f"/api/v1/pim/peer/benchmarks/{BENCHMARK_ID}", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    assert r.json() == {"deleted": True}


# --- GET /pim/peer/assessments/{id}/rank ---


def test_rank_assessment_not_found() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(side_effect=[None])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_peer.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            f"/api/v1/pim/peer/assessments/{ASSESSMENT_ID}/rank",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 404


def test_rank_no_benchmark_gives_warning() -> None:
    conn = MagicMock()
    # assessment found, no benchmark found (both fetchrow calls)
    conn.fetchrow = AsyncMock(side_effect=[_ASSESSMENT_ROW, None, None])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_peer.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            f"/api/v1/pim/peer/assessments/{ASSESSMENT_ID}/rank",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["warning"] is not None
    assert data["benchmark_id"] is None
    # All rankings have no percentile
    for ranking in data["rankings"]:
        assert ranking["percentile_rank"] is None


def test_rank_happy_path() -> None:
    conn = MagicMock()
    # assessment found, then benchmark found on first try (exact match)
    conn.fetchrow = AsyncMock(side_effect=[_ASSESSMENT_ROW, _BENCHMARK_ROW])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_peer.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            f"/api/v1/pim/peer/assessments/{ASSESSMENT_ID}/rank",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["benchmark_id"] == BENCHMARK_ID
    assert data["warning"] is None
    assert data["fund_count"] == 85

    rankings = {m["metric"]: m for m in data["rankings"]}
    # DPI = 1.2; p25=0.5, p50=1.0, p75=1.5 → between p50 and p75 → rank > 50
    assert rankings["dpi"]["percentile_rank"] > 50.0
    assert rankings["dpi"]["quartile"] == 2  # second quartile (50–75)
    # IRR = 0.18; p25=0.10, p50=0.15, p75=0.22 → between p50 and p75 → rank > 50
    assert rankings["irr"]["percentile_rank"] > 50.0
