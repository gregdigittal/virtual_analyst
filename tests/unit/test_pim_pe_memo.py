"""PIM-7.2: PE investment memo generation unit tests."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException
from fastapi.testclient import TestClient

from apps.api.app.deps import get_llm_router, require_pim_access
from apps.api.app.main import app

client = TestClient(app)

TENANT = "tenant-memo-test"
ASSESSMENT_ID = "assess-memo-123"

_ASSESSMENT_ROW = {
    "assessment_id": ASSESSMENT_ID,
    "fund_name": "Acme Ventures III",
    "vintage_year": 2020,
    "currency": "USD",
    "commitment_usd": 5_000_000.0,
    "paid_in_capital": 4_000_000.0,
    "distributed": 2_000_000.0,
    "dpi": 0.5,
    "tvpi": 1.5,
    "moic": 1.5,
    "irr": 0.18,
    "irr_computed_at": "2026-01-01T00:00:00",
    "nav_usd": 4_000_000.0,
    "notes": "Performing above target",
}

_MEMO_CONTENT = {
    "title": "Acme Ventures III — Investment Memo",
    "executive_summary": "Acme Ventures III is a 2020 vintage buyout fund with strong performance.",
    "performance_analysis": "DPI of 0.50x with TVPI of 1.50x indicates solid unrealised gains.",
    "risk_factors": "1. Concentration risk 2. Exit timing 3. Macro headwinds",
    "recommendation": "Hold — maintain current exposure pending exit events.",
    "disclaimer": "This memo is for informational purposes only.",
}


def _make_cm(conn):
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _make_llm_mock(content: dict) -> MagicMock:
    llm = MagicMock()
    response = MagicMock()
    response.content = json.dumps(content)
    response.model = "claude-sonnet-4-5-20250929"
    llm.complete_with_routing = AsyncMock(return_value=response)
    return llm


@pytest.fixture(autouse=True)
def _bypass_pim_gate():
    async def _tenant_only(x_tenant_id: str = Header("", alias="X-Tenant-ID")):  # noqa: B008
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="X-Tenant-ID required")

    app.dependency_overrides[require_pim_access] = _tenant_only
    yield
    app.dependency_overrides.pop(require_pim_access, None)


@pytest.fixture(autouse=True)
def _patch_llm():
    llm = _make_llm_mock(_MEMO_CONTENT)
    app.dependency_overrides[get_llm_router] = lambda: llm
    yield llm
    app.dependency_overrides.pop(get_llm_router, None)


def test_memo_requires_tenant() -> None:
    r = client.post(f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/memo")
    assert r.status_code == 400


def test_memo_not_found() -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/memo",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 404


def test_memo_requires_computed_metrics() -> None:
    """Memo should 422 if compute hasn't been run (dpi and tvpi both None)."""
    row = dict(_ASSESSMENT_ROW)
    row["dpi"] = None
    row["tvpi"] = None
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=row)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/memo",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 422


def test_memo_happy_path(request, _patch_llm) -> None:
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_ASSESSMENT_ROW)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/memo",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 200
    data = r.json()
    assert data["assessment_id"] == ASSESSMENT_ID
    assert data["fund_name"] == "Acme Ventures III"
    assert data["title"] == _MEMO_CONTENT["title"]
    assert len(data["executive_summary"]) > 0
    assert len(data["performance_analysis"]) > 0
    assert len(data["risk_factors"]) > 0
    assert len(data["recommendation"]) > 0
    assert data["model_used"] == "claude-sonnet-4-5-20250929"


def test_memo_llm_failure_returns_502(request, _patch_llm) -> None:
    _patch_llm.complete_with_routing = AsyncMock(side_effect=RuntimeError("LLM timeout"))
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=_ASSESSMENT_ROW)
    cm = _make_cm(conn)

    with patch("apps.api.app.routers.pim_pe.tenant_conn", side_effect=lambda _t: cm):
        r = client.post(
            f"/api/v1/pim/pe/assessments/{ASSESSMENT_ID}/memo",
            headers={"X-Tenant-ID": TENANT},
        )

    assert r.status_code == 502


def test_pim_pe_memo_task_label_registered() -> None:
    """Verify pim_pe_memo is in the LLM router policy with temperature=0.4."""
    from apps.api.app.services.llm.router import DEFAULT_POLICY

    memo_rules = [r for r in DEFAULT_POLICY["rules"] if r["task_label"] == "pim_pe_memo"]
    assert len(memo_rules) >= 1
    assert memo_rules[0]["temperature"] == pytest.approx(0.4)
    assert memo_rules[0]["max_tokens"] == 4096
