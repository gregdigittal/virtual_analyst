"""Integration tests: create baseline -> list -> get -> create run -> get run -> get statements/KPIs."""

from __future__ import annotations

from tests.conftest import minimal_model_config_dict
from tests.integration.conftest import integration_marker


@integration_marker
async def test_baseline_create_list_get(client) -> None:
    """Create baseline via API, list baselines, get by id."""
    headers = {"X-Tenant-ID": "t_integration", "X-User-ID": "u1"}
    create = await client.post(
        "/api/v1/baselines",
        json={"model_config": minimal_model_config_dict(tenant_id="t_integration")},
        headers=headers,
    )
    assert create.status_code == 201
    body = create.json()
    assert "baseline_id" in body
    assert body["status"] == "active"
    baseline_id = body["baseline_id"]

    list_resp = await client.get("/api/v1/baselines", headers=headers)
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert len(items) >= 1
    assert any(b["baseline_id"] == baseline_id for b in items)

    get_resp = await client.get(f"/api/v1/baselines/{baseline_id}", headers=headers)
    assert get_resp.status_code == 200
    got = get_resp.json()
    assert got["baseline_id"] == baseline_id
    assert "model_config" in got
    assert got["model_config"]["metadata"]["horizon_months"] == 12


@integration_marker
async def test_run_lifecycle(client) -> None:
    """Create baseline, create run, get run, get statements and KPIs."""
    headers = {"X-Tenant-ID": "t_integration_run", "X-User-ID": "u1"}
    create_bl = await client.post(
        "/api/v1/baselines",
        json={"model_config": minimal_model_config_dict(tenant_id="t_integration_run")},
        headers=headers,
    )
    assert create_bl.status_code == 201
    baseline_id = create_bl.json()["baseline_id"]

    create_run = await client.post(
        "/api/v1/runs",
        json={"baseline_id": baseline_id},
        headers=headers,
    )
    assert create_run.status_code == 201
    run_body = create_run.json()
    assert run_body["status"] == "succeeded"
    run_id = run_body["run_id"]

    get_run = await client.get(f"/api/v1/runs/{run_id}", headers=headers)
    assert get_run.status_code == 200
    assert get_run.json()["run_id"] == run_id
    assert get_run.json()["status"] == "succeeded"

    statements = await client.get(f"/api/v1/runs/{run_id}/statements", headers=headers)
    assert statements.status_code == 200
    data = statements.json()
    assert "income_statement" in data
    assert "balance_sheet" in data
    assert "cash_flow" in data
    assert len(data["income_statement"]) == 12

    kpis = await client.get(f"/api/v1/runs/{run_id}/kpis", headers=headers)
    assert kpis.status_code == 200
    kpi_list = kpis.json()
    assert isinstance(kpi_list, list)
    assert len(kpi_list) == 12
    assert "gross_margin_pct" in kpi_list[0]
