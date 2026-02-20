from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from apps.api.app.deps import get_artifact_store
from apps.api.app.main import app
from tests.conftest import minimal_model_config_dict

client = TestClient(app)


def _async_cm(conn: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=conn)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def test_list_scenarios_requires_x_tenant_id() -> None:
    r = client.get("/api/v1/scenarios")
    assert r.status_code == 400


def test_compare_scenarios_requires_baseline_id() -> None:
    r = client.post(
        "/api/v1/scenarios/compare",
        json={},
        headers={"X-Tenant-ID": "t1"},
    )
    assert r.status_code == 400


def test_compare_scenarios_rejects_too_many() -> None:
    r = client.post(
        "/api/v1/scenarios/compare",
        json={"baseline_id": "bl_1", "scenario_ids": [f"sc_{i}" for i in range(11)]},
        headers={"X-Tenant-ID": "t1"},
    )
    assert r.status_code == 400


def test_compare_scenarios_returns_base_and_scenario() -> None:
    baseline_id = "bl_1"
    store = MagicMock()
    store.load = MagicMock(return_value=minimal_model_config_dict(tenant_id="t1"))
    app.dependency_overrides[get_artifact_store] = lambda: store

    base_conn = MagicMock()
    base_conn.fetchrow = AsyncMock(return_value={"baseline_id": baseline_id, "baseline_version": "v1"})
    scenario_conn = MagicMock()
    scenario_conn.fetch = AsyncMock(
        return_value=[{"scenario_id": "sc_1", "label": "Downside", "overrides_json": [{"ref": "drv:units", "value": 80}]}]
    )
    tenant_conn_side_effect = [_async_cm(base_conn), _async_cm(scenario_conn)]

    statements = MagicMock()
    statements.income_statement = [{"revenue": 100.0, "ebitda": 20.0, "net_income": 10.0}]
    kpis = [{"fcf": 5.0, "gross_margin_pct": 0.5, "ebitda_margin_pct": 0.2}]

    try:
        with patch("apps.api.app.routers.scenarios.tenant_conn", side_effect=tenant_conn_side_effect):
            with patch("apps.api.app.routers.scenarios.run_engine", return_value={"ts": []}) as mock_run:
                with patch("apps.api.app.routers.scenarios.generate_statements", return_value=statements):
                    with patch("apps.api.app.routers.scenarios.calculate_kpis", return_value=kpis):
                        r = client.post(
                            "/api/v1/scenarios/compare",
                            json={"baseline_id": baseline_id, "scenario_ids": ["sc_1"]},
                            headers={"X-Tenant-ID": "t1"},
                        )
        assert r.status_code == 200
        data = r.json()
        assert data["baseline_id"] == baseline_id
        assert len(data["scenarios"]) == 2
        labels = [row["label"] for row in data["scenarios"]]
        assert "Base" in labels
        assert "Downside" in labels
        assert mock_run.call_count == 2
    finally:
        app.dependency_overrides.pop(get_artifact_store, None)
