"""PIM-1.7: Sentiment API unit tests."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-pim-sentiment"
USER = "user-pim-sentiment"

_SIGNAL_ROW = {
    "signal_id": "sig_1",
    "company_id": "pco_1",
    "source_type": "polygon_news",
    "source_ref": "ref1",
    "headline": "Apple reports record earnings",
    "published_at": None,
    "sentiment_score": 0.5,
    "confidence": 0.8,
    "llm_model": "claude-3",
    "created_at": None,
}

_AGG_ROW = {
    "company_id": "pco_1",
    "period_type": "weekly",
    "period_start": None,
    "period_end": None,
    "avg_sentiment": 0.4,
    "median_sentiment": None,
    "min_sentiment": None,
    "max_sentiment": None,
    "std_sentiment": None,
    "signal_count": 3,
    "avg_confidence": 0.75,
    "source_breakdown": {},
    "trend_direction": "up",
    "updated_at": None,
}

_COMPANY_ROW = {
    "company_id": "pco_1",
    "ticker": "AAPL",
    "company_name": "Apple Inc",
    "sector": "Technology",
    "sub_sector": None,
}


def _make_cm(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _simple_conn(fetchrow_return=None, fetch_return=None, fetchval_return=None):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=fetch_return or [])
    conn.fetchrow = AsyncMock(return_value=fetchrow_return)
    conn.fetchval = AsyncMock(return_value=fetchval_return)
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


# --- /scores ---


def test_scores_requires_tenant() -> None:
    r = client.get("/api/v1/pim/sentiment/scores")
    assert r.status_code == 400


def test_scores_happy_path() -> None:
    count_row = {"cnt": 1}
    conn = _simple_conn(fetchrow_return=count_row, fetch_return=[_SIGNAL_ROW])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_sentiment.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/sentiment/scores", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["signal_id"] == "sig_1"


# --- /aggregates ---


def test_aggregates_requires_tenant() -> None:
    r = client.get("/api/v1/pim/sentiment/aggregates")
    assert r.status_code == 400


def test_aggregates_invalid_period_type() -> None:
    with patch(
        "apps.api.app.routers.pim_sentiment.tenant_conn",
        side_effect=lambda _t: _make_cm(_simple_conn()),
    ):
        r = client.get(
            "/api/v1/pim/sentiment/aggregates?period_type=bad",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 400


def test_aggregates_happy_path() -> None:
    count_row = {"cnt": 1}
    conn = _simple_conn(fetchrow_return=count_row, fetch_return=[_AGG_ROW])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_sentiment.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/sentiment/aggregates", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


# --- /dashboard ---


def test_dashboard_no_companies() -> None:
    conn = _simple_conn(fetch_return=[])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_sentiment.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/sentiment/dashboard", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_dashboard_with_companies() -> None:
    company_row = {"company_id": "pco_1", "ticker": "AAPL", "company_name": "Apple", "sector": "Tech"}

    conn = MagicMock()
    conn.fetch = AsyncMock(
        side_effect=[
            [company_row],  # companies query
            [],             # agg DISTINCT ON query
            [],             # sig DISTINCT ON query
            [],             # count GROUP BY query
        ]
    )
    conn.fetchrow = AsyncMock(return_value=None)
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_sentiment.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/sentiment/dashboard", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["company_id"] == "pco_1"
    assert item["ticker"] == "AAPL"
    assert item["latest_avg_sentiment"] is None
    assert item["latest_signal"] is None


# --- /company/{id} ---


def test_company_detail_not_found() -> None:
    conn = _simple_conn(fetchrow_return=None, fetch_return=[])
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_sentiment.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/sentiment/company/pco_notexist",
            headers={"X-Tenant-ID": TENANT},
        )
    assert r.status_code == 404


def test_company_detail_happy_path() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_COMPANY_ROW)
    conn.fetch = AsyncMock(side_effect=[
        [_AGG_ROW],      # aggregates time-series
        [_SIGNAL_ROW],   # recent signals
    ])
    conn.fetchval = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_sentiment.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(
            "/api/v1/pim/sentiment/company/pco_1",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["company"]["company_id"] == "pco_1"
    assert data["company"]["ticker"] == "AAPL"
    assert len(data["aggregates"]) == 1
    assert len(data["recent_signals"]) == 1
    assert data["recent_signals"][0]["signal_id"] == "sig_1"
