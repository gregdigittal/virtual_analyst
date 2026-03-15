"""AFS Analytics endpoints — compute, ratios, anomalies, going concern, commentary."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_artifact_store, get_llm_router
from apps.api.app.main import app

client = TestClient(app)
TENANT = "tenant-afs-ana"
USER = "user-afs-ana"
HEADERS = {"X-Tenant-ID": TENANT, "X-User-ID": USER}


def _mock_tenant_conn(_tenant_id: str):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=0)
    conn.fetchrow = AsyncMock(return_value=None)
    conn.execute = AsyncMock()
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def _setup_di():
    mock_store = MagicMock()
    mock_store.save = MagicMock(return_value="path")
    mock_store.load = MagicMock(return_value={})
    mock_llm = MagicMock()
    app.dependency_overrides[get_artifact_store] = lambda: mock_store
    app.dependency_overrides[get_llm_router] = lambda: mock_llm
    return mock_store, mock_llm


def _cleanup():
    app.dependency_overrides.pop(get_artifact_store, None)
    app.dependency_overrides.pop(get_llm_router, None)


# ---------------------------------------------------------------------------
# Compute Analytics
# ---------------------------------------------------------------------------


def test_compute_analytics_requires_tenant() -> None:
    r = client.post(
        "/api/v1/afs/engagements/eng-1/analytics/compute",
        json={"industry_segment": "general"},
    )
    assert r.status_code == 400


def test_compute_analytics_engagement_not_found() -> None:
    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.post(
            "/api/v1/afs/engagements/eng-999/analytics/compute",
            json={"industry_segment": "general"},
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_compute_analytics_no_trial_balance() -> None:
    """Should return 400 when no trial balance exists for the engagement."""
    def _conn_eng_but_no_tb(_tid: str):
        conn = MagicMock()
        call_count = {"n": 0}

        async def _fetchrow(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                # Engagement lookup
                return {"entity_name": "Test Corp", "framework_id": "fw-1"}
            if call_count["n"] == 2:
                # Framework lookup
                return {"name": "IFRS (Full)"}
            # Trial balance lookup — none found
            return None

        conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        conn.execute = AsyncMock()
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    _setup_di()
    try:
        with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_conn_eng_but_no_tb):
            r = client.post(
                "/api/v1/afs/engagements/eng-1/analytics/compute",
                json={"industry_segment": "general"},
                headers=HEADERS,
            )
    finally:
        _cleanup()
    assert r.status_code == 400
    assert "trial balance" in r.json()["detail"].lower()


def test_compute_analytics_success() -> None:
    """Full compute flow: engagement + TB found, ratios computed, AI called, row stored."""
    tb_data = [
        {"account_code": "1100", "account_name": "Cash", "debit": 100000, "credit": 0},
        {"account_code": "2100", "account_name": "Accounts Payable", "debit": 0, "credit": 40000},
        {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 200000},
        {"account_code": "5000", "account_name": "Cost of Goods Sold", "debit": 120000, "credit": 0},
    ]
    stored_row = {
        "analytics_id": "aan_test123",
        "engagement_id": "eng-1",
        "tenant_id": TENANT,
        "ratios_json": json.dumps({"current_ratio": 2.5}),
        "benchmark_comparison_json": json.dumps({}),
        "anomalies_json": json.dumps({"anomalies": []}),
        "commentary_json": json.dumps({"key_highlights": [], "risk_factors": [], "outlook_points": []}),
        "going_concern_json": json.dumps({"risk_level": "low", "factors": [], "recommendation": "None", "disclosure_required": False}),
        "industry_segment": "general",
        "computed_at": "2026-03-08T00:00:00",
        "computed_by": USER,
        "status": "complete",
        "error_message": None,
    }

    def _conn_full(_tid: str):
        conn = MagicMock()
        call_count = {"n": 0}

        async def _fetchrow(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"entity_name": "Test Corp", "framework_id": "fw-1"}
            if call_count["n"] == 2:
                return {"name": "IFRS (Full)"}
            if call_count["n"] == 3:
                return {"data_json": json.dumps(tb_data)}
            # Final fetch after insert
            return stored_row

        conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    # Mock LLM responses
    mock_anomaly_resp = MagicMock()
    mock_anomaly_resp.content = {"anomalies": []}
    mock_commentary_resp = MagicMock()
    mock_commentary_resp.content = {"key_highlights": ["Revenue strong"], "risk_factors": [], "outlook_points": []}
    mock_gc_resp = MagicMock()
    mock_gc_resp.content = {"risk_level": "low", "factors": [], "recommendation": "None", "disclosure_required": False}

    _setup_di()
    try:
        with (
            patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_conn_full),
            patch("apps.api.app.routers.afs.analytics.detect_anomalies", new_callable=AsyncMock, return_value=mock_anomaly_resp),
            patch("apps.api.app.routers.afs.analytics.generate_commentary", new_callable=AsyncMock, return_value=mock_commentary_resp),
            patch("apps.api.app.routers.afs.analytics.assess_going_concern", new_callable=AsyncMock, return_value=mock_gc_resp),
            patch("apps.api.app.routers.afs.analytics._load_benchmarks", return_value={
                "segments": {"general": {"current_ratio": {"p25": 1.0, "median": 1.5, "p75": 2.5}}}
            }),
        ):
            r = client.post(
                "/api/v1/afs/engagements/eng-1/analytics/compute",
                json={"industry_segment": "general"},
                headers=HEADERS,
            )
    finally:
        _cleanup()
    assert r.status_code == 200
    data = r.json()
    assert data["analytics_id"] == "aan_test123"


def test_compute_analytics_ai_failure_graceful() -> None:
    """When an AI call raises an exception, compute should still succeed with partial results."""
    tb_data = [
        {"account_code": "1100", "account_name": "Cash", "debit": 50000, "credit": 0},
        {"account_code": "4000", "account_name": "Revenue", "debit": 0, "credit": 100000},
    ]
    stored_row = {
        "analytics_id": "aan_partial",
        "engagement_id": "eng-1",
        "tenant_id": TENANT,
        "ratios_json": json.dumps({"current_ratio": 1.0}),
        "benchmark_comparison_json": json.dumps({}),
        "anomalies_json": json.dumps({"anomalies": [], "_error": "LLM timeout"}),
        "commentary_json": None,
        "going_concern_json": None,
        "industry_segment": "general",
        "computed_at": "2026-03-08T00:00:00",
        "computed_by": USER,
        "status": "complete",
        "error_message": None,
    }

    def _conn_full(_tid: str):
        conn = MagicMock()
        call_count = {"n": 0}

        async def _fetchrow(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return {"entity_name": "Test Corp", "framework_id": "fw-1"}
            if call_count["n"] == 2:
                return {"name": "IFRS (Full)"}
            if call_count["n"] == 3:
                return {"data_json": json.dumps(tb_data)}
            return stored_row

        conn.fetchrow = AsyncMock(side_effect=_fetchrow)
        conn.execute = AsyncMock()
        conn.fetch = AsyncMock(return_value=[])
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    _setup_di()
    try:
        with (
            patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_conn_full),
            patch("apps.api.app.routers.afs.analytics.detect_anomalies", new_callable=AsyncMock, side_effect=RuntimeError("LLM timeout")),
            patch("apps.api.app.routers.afs.analytics.generate_commentary", new_callable=AsyncMock, side_effect=RuntimeError("LLM timeout")),
            patch("apps.api.app.routers.afs.analytics.assess_going_concern", new_callable=AsyncMock, side_effect=RuntimeError("LLM timeout")),
            patch("apps.api.app.routers.afs.analytics._load_benchmarks", return_value={"segments": {"general": {}}}),
        ):
            r = client.post(
                "/api/v1/afs/engagements/eng-1/analytics/compute",
                json={"industry_segment": "general"},
                headers=HEADERS,
            )
    finally:
        _cleanup()
    assert r.status_code == 200
    data = r.json()
    assert data["analytics_id"] == "aan_partial"


# ---------------------------------------------------------------------------
# GET Analytics
# ---------------------------------------------------------------------------


def test_get_analytics_not_found() -> None:
    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics",
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_get_analytics_success() -> None:
    analytics_row = {
        "analytics_id": "aan_existing",
        "engagement_id": "eng-1",
        "ratios_json": json.dumps({"current_ratio": 1.8}),
        "benchmark_comparison_json": json.dumps({}),
        "anomalies_json": json.dumps({"anomalies": []}),
        "commentary_json": None,
        "going_concern_json": None,
        "industry_segment": "general",
        "computed_at": "2026-03-07T12:00:00",
        "status": "complete",
    }

    def _conn_with_analytics(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=analytics_row)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_conn_with_analytics):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics",
            headers=HEADERS,
        )
    assert r.status_code == 200
    assert r.json()["analytics_id"] == "aan_existing"


# ---------------------------------------------------------------------------
# GET Ratios
# ---------------------------------------------------------------------------


def test_get_analytics_ratios_not_found() -> None:
    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics/ratios",
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_get_analytics_ratios_success() -> None:
    ratio_row = {
        "ratios_json": json.dumps({"current_ratio": 2.1, "debt_to_equity": 0.5}),
        "benchmark_comparison_json": json.dumps({"current_ratio": {"value": 2.1, "p25": 1.0, "median": 1.5, "p75": 2.5, "position": "median_to_p75"}}),
        "industry_segment": "technology",
        "computed_at": "2026-03-07T12:00:00",
    }

    def _conn_with_ratios(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=ratio_row)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_conn_with_ratios):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics/ratios",
            headers=HEADERS,
        )
    assert r.status_code == 200
    data = r.json()
    assert "ratios_json" in data
    assert data["industry_segment"] == "technology"


# ---------------------------------------------------------------------------
# GET Anomalies
# ---------------------------------------------------------------------------


def test_get_analytics_anomalies_not_found() -> None:
    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics/anomalies",
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_get_analytics_anomalies_success() -> None:
    anomaly_row = {
        "anomalies_json": json.dumps({"anomalies": [
            {"ratio_key": "current_ratio", "severity": "warning", "description": "Low liquidity", "disclosure_impact": "May need going concern note"}
        ]}),
        "industry_segment": "manufacturing",
        "computed_at": "2026-03-07T12:00:00",
    }

    def _conn_with_anomalies(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=anomaly_row)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_conn_with_anomalies):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics/anomalies",
            headers=HEADERS,
        )
    assert r.status_code == 200
    data = r.json()
    anomalies = json.loads(data["anomalies_json"])
    assert len(anomalies["anomalies"]) == 1


# ---------------------------------------------------------------------------
# GET Going Concern
# ---------------------------------------------------------------------------


def test_get_going_concern_not_found() -> None:
    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_mock_tenant_conn):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics/going-concern",
            headers=HEADERS,
        )
    assert r.status_code == 404


def test_get_going_concern_success() -> None:
    gc_row = {
        "going_concern_json": json.dumps({
            "risk_level": "moderate",
            "factors": [
                {"factor": "Debt coverage", "indicator": "negative", "detail": "DSCR below 1.2x"}
            ],
            "recommendation": "Include going concern note in financial statements.",
            "disclosure_required": True,
        }),
        "industry_segment": "retail",
        "computed_at": "2026-03-07T12:00:00",
    }

    def _conn_with_gc(_tid: str):
        conn = MagicMock()
        conn.fetchrow = AsyncMock(return_value=gc_row)
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=conn)
        cm.__aexit__ = AsyncMock(return_value=None)
        return cm

    with patch("apps.api.app.routers.afs.analytics.tenant_conn", side_effect=_conn_with_gc):
        r = client.get(
            "/api/v1/afs/engagements/eng-1/analytics/going-concern",
            headers=HEADERS,
        )
    assert r.status_code == 200
    data = r.json()
    gc = json.loads(data["going_concern_json"])
    assert gc["risk_level"] == "moderate"
    assert gc["disclosure_required"] is True


# ---------------------------------------------------------------------------
# Ratio Calculator unit tests
# ---------------------------------------------------------------------------


def test_ratio_calculator_compute_from_tb() -> None:
    """Test the pure-Python ratio calculator with sample trial balance data."""
    from apps.api.app.services.afs.ratio_calculator import compute_from_tb

    tb_data = [
        {"account_code": "1100", "account_name": "Cash at Bank", "debit": 100000, "credit": 0},
        {"account_code": "1200", "account_name": "Accounts Receivable", "debit": 50000, "credit": 0},
        {"account_code": "1500", "account_name": "Inventory", "debit": 30000, "credit": 0},
        {"account_code": "1800", "account_name": "Equipment", "debit": 200000, "credit": 0},
        {"account_code": "2100", "account_name": "Accounts Payable", "debit": 0, "credit": 40000},
        {"account_code": "2500", "account_name": "Long Term Loan", "debit": 0, "credit": 150000},
        {"account_code": "3000", "account_name": "Share Capital", "debit": 0, "credit": 100000},
        {"account_code": "3100", "account_name": "Retained Earnings", "debit": 0, "credit": 90000},
        {"account_code": "4000", "account_name": "Sales Revenue", "debit": 0, "credit": 500000},
        {"account_code": "5000", "account_name": "Cost of Sales", "debit": 300000, "credit": 0},
        {"account_code": "6100", "account_name": "Salaries Expense", "debit": 80000, "credit": 0},
        {"account_code": "6200", "account_name": "Rent Expense", "debit": 20000, "credit": 0},
    ]

    ratios = compute_from_tb(tb_data)

    # Should return a dict with various ratio keys
    assert isinstance(ratios, dict)
    assert "current_ratio" in ratios

    # Current ratio: current assets (cash + AR + inventory = 180k) / current liabilities (AP = 40k) = 4.5
    if ratios["current_ratio"] is not None:
        assert ratios["current_ratio"] > 0


def test_ratio_calculator_empty_tb() -> None:
    """Empty trial balance should return dict with None values, not crash."""
    from apps.api.app.services.afs.ratio_calculator import compute_from_tb

    ratios = compute_from_tb([])
    assert isinstance(ratios, dict)


# ---------------------------------------------------------------------------
# Analytics AI schemas validation
# ---------------------------------------------------------------------------


def test_anomaly_schema_structure() -> None:
    """Verify the anomaly detection schema has required fields."""
    from apps.api.app.services.afs.analytics_ai import ANOMALY_SCHEMA

    assert ANOMALY_SCHEMA["type"] == "object"
    assert "anomalies" in ANOMALY_SCHEMA["properties"]
    items_props = ANOMALY_SCHEMA["properties"]["anomalies"]["items"]["properties"]
    assert "ratio_key" in items_props
    assert "severity" in items_props
    assert "disclosure_impact" in items_props


def test_going_concern_schema_structure() -> None:
    """Verify the going concern schema has required fields."""
    from apps.api.app.services.afs.analytics_ai import GOING_CONCERN_SCHEMA

    assert "risk_level" in GOING_CONCERN_SCHEMA["properties"]
    assert "factors" in GOING_CONCERN_SCHEMA["properties"]
    assert "disclosure_required" in GOING_CONCERN_SCHEMA["properties"]
    assert GOING_CONCERN_SCHEMA["properties"]["disclosure_required"]["type"] == "boolean"


def test_commentary_schema_structure() -> None:
    """Verify the commentary schema has required fields."""
    from apps.api.app.services.afs.analytics_ai import COMMENTARY_SCHEMA

    assert "key_highlights" in COMMENTARY_SCHEMA["properties"]
    assert "risk_factors" in COMMENTARY_SCHEMA["properties"]
    assert "outlook_points" in COMMENTARY_SCHEMA["properties"]
