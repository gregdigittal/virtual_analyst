"""PIM-6.2: PE assessment CRUD endpoint unit tests."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-pim-pe"
ASSESSMENT_ID = "assess-abc123"

_PE_ROW = {
    "assessment_id": ASSESSMENT_ID,
    "tenant_id": TENANT,
    "fund_name": "Acme Ventures III",
    "vintage_year": 2020,
    "currency": "USD",
    "commitment_usd": 5_000_000.0,
    "cash_flows": json.dumps([
        {"date": "2020-06-30", "amount_usd": 500_000, "cf_type": "drawdown"},
        {"date": "2021-06-30", "amount_usd": 750_000, "cf_type": "distribution"},
    ]),
    "nav_usd": 4_000_000.0,
    "nav_date": None,
    "paid_in_capital": 500_000.0,
    "distributed": 750_000.0,
    "dpi": 1.5,
    "tvpi": 2.0,
    "moic": 2.0,
    "irr": 0.18,
    "irr_computed_at": None,
    "j_curve_json": None,
    "notes": "Test fund",
    "created_at": "2026-01-01T00:00:00",
    "updated_at": "2026-01-01T00:00:00",
}


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


# --- POST /pim/pe/assessments ---


def test_create_requires_tenant() -> None:
    r = client.post("/api/v1/pim/pe/assessments", json={})
    assert r.status_code == 400


def test_create_happy_path() -> None:
    conn = _simple_conn(fetchrow_return=_PE_ROW)
    cm = _make_cm(conn)

    body = {
        "fund_name": "Acme Ventures III",
        "vintage_year": 2020,
        "commitment_usd": 5_000_000,
        "cash_flows": [
            {"date": "2020-06-30", "amount_usd": 500_000, "cf_type": "drawdown"},
        ],
    }
    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            "/api/v1/pim/pe/assessments",
            json=body,
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 201
    data = r.json()
    assert data["fund_name"] == "Acme Ventures III"
    assert data["assessment_id"] == ASSESSMENT_ID


def test_create_invalid_cf_type() -> None:
    body = {
        "fund_name": "Bad Fund",
        "vintage_year": 2021,
        "commitment_usd": 1_000_000,
        "cash_flows": [{"date": "2021-01-01", "amount_usd": 100_000, "cf_type": "dividend"}],
    }
    r = client.post("/api/v1/pim/pe/assessments", json=body, headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 422


def test_create_invalid_vintage_year() -> None:
    body = {"fund_name": "Old Fund", "vintage_year": 1900, "commitment_usd": 1_000_000}
    r = client.post("/api/v1/pim/pe/assessments", json=body, headers={"X-Tenant-ID": TENANT})
    assert r.status_code == 422


# --- GET /pim/pe/assessments ---


def test_list_requires_tenant() -> None:
    r = client.get("/api/v1/pim/pe/assessments")
    assert r.status_code == 400


def test_list_empty() -> None:
    count_row = {"n": 0}
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=count_row)
    conn.fetch = AsyncMock(return_value=[])
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/pe/assessments", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["total"] == 0


def test_list_happy_path() -> None:
    count_row = {"n": 1}
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=count_row)
    conn.fetch = AsyncMock(return_value=[_PE_ROW])
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/pe/assessments", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["fund_name"] == "Acme Ventures III"


# --- GET /pim/pe/assessments/{id} ---


def test_get_not_found() -> None:
    conn = _simple_conn(fetchrow_return=None)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 404


def test_get_happy_path() -> None:
    conn = _simple_conn(fetchrow_return=_PE_ROW)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.get(f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["assessment_id"] == ASSESSMENT_ID
    assert data["irr"] == pytest.approx(0.18)
    assert len(data["cash_flows"]) == 2


# --- PUT /pim/pe/assessments/{id} ---


def test_update_not_found() -> None:
    conn = _simple_conn(fetchrow_return=None)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.put(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}",
            json={"fund_name": "New Name"},
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 404


def test_update_happy_path() -> None:
    updated = dict(_PE_ROW)
    updated["fund_name"] = "Acme Ventures III (Renamed)"
    conn = _simple_conn(fetchrow_return=updated)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.put(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}",
            json={"fund_name": "Acme Ventures III (Renamed)"},
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    assert r.json()["fund_name"] == "Acme Ventures III (Renamed)"


def test_update_no_fields_422() -> None:
    r = client.put(
        f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}",
        json={},
        headers={"X-Tenant-ID": TENANT},
    )
    assert r.status_code == 422


# --- DELETE /pim/pe/assessments/{id} ---


def test_delete_not_found() -> None:
    conn = _simple_conn(execute_return="DELETE 0")
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.delete(f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 404


def test_delete_happy_path() -> None:
    conn = _simple_conn(execute_return="DELETE 1")
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.delete(f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    assert r.json() == {"deleted": True}


# --- POST /pim/pe/assessments/{id}/compute ---


def test_compute_requires_tenant() -> None:
    r = client.post(f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/compute")
    assert r.status_code == 400


def test_compute_not_found() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/compute",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 404


def test_compute_happy_path() -> None:
    compute_row = {
        "assessment_id": ASSESSMENT_ID,
        "cash_flows": json.dumps([
            {"date": "2020-01-01", "amount_usd": 1_000_000, "cf_type": "drawdown"},
            {"date": "2021-06-30", "amount_usd": 700_000, "cf_type": "distribution"},
        ]),
        "nav_usd": 400_000.0,
        "commitment_usd": 1_000_000.0,
    }
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=compute_row)
    conn.execute = AsyncMock(return_value="UPDATE 1")
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/compute",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["assessment_id"] == ASSESSMENT_ID
    assert data["paid_in_capital"] == pytest.approx(1_000_000.0)
    assert data["distributed"] == pytest.approx(700_000.0)
    assert data["dpi"] == pytest.approx(0.7)
    # tvpi = (700k + 400k) / 1000k = 1.1
    assert data["tvpi"] == pytest.approx(1.1)
    assert isinstance(data["j_curve"], list)
    assert len(data["j_curve"]) == 2
    assert "limitations" in data


# --- GET /pim/pe/summary ---


def test_pe_summary_requires_tenant() -> None:
    r = client.get("/api/v1/pim/pe/summary")
    assert r.status_code == 400


def test_pe_summary_empty_portfolio() -> None:
    """No assessments → zero counts, null averages."""
    conn = _simple_conn(
        fetchrow_return={
            "total": 0, "with_irr": 0,
            "avg_dpi": None, "avg_tvpi": None, "avg_irr": None,
        },
    )
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/pe/summary", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total_assessments"] == 0
    assert data["assessments_with_irr"] == 0
    assert data["avg_dpi"] is None
    assert data["avg_tvpi"] is None
    assert data["avg_irr"] is None


def test_pe_summary_with_computed_assessments() -> None:
    """Returns correct aggregated metrics when assessments have been computed."""
    conn = _simple_conn(
        fetchrow_return={
            "total": 3, "with_irr": 2,
            "avg_dpi": 1.25, "avg_tvpi": 1.80, "avg_irr": 0.15,
        },
    )
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.get("/api/v1/pim/pe/summary", headers={"X-Tenant-ID": TENANT})

    assert r.status_code == 200
    data = r.json()
    assert data["total_assessments"] == 3
    assert data["assessments_with_irr"] == 2
    assert data["avg_dpi"] == pytest.approx(1.25)
    assert data["avg_tvpi"] == pytest.approx(1.80)
    assert data["avg_irr"] == pytest.approx(0.15)
