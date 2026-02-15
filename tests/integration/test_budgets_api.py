"""VA-P7-12: Budget API integration tests — list, get, dashboard, variance."""

from __future__ import annotations

from tests.integration.conftest import integration_marker


@integration_marker
async def test_budgets_list_and_dashboard(client) -> None:
    """List budgets and get dashboard (CFO view)."""
    headers = {"X-Tenant-ID": "t_integration_budgets", "X-User-ID": "u1"}
    list_resp = await client.get("/api/v1/budgets", headers=headers)
    assert list_resp.status_code == 200, list_resp.text
    data = list_resp.json()
    assert "budgets" in data
    assert isinstance(data["budgets"], list)
    assert "limit" in data
    assert "offset" in data

    dash = await client.get("/api/v1/budgets/dashboard", headers=headers)
    assert dash.status_code == 200, dash.text
    d = dash.json()
    assert "widgets" in d
    assert "cfo_view" in d
    assert d["cfo_view"] is True
    assert isinstance(d["widgets"], list)


@integration_marker
async def test_budgets_dashboard_single_budget(client) -> None:
    """Get dashboard for non-existent budget returns 404."""
    headers = {"X-Tenant-ID": "t_integration_budgets", "X-User-ID": "u1"}
    resp = await client.get("/api/v1/budgets/dashboard?budget_id=nonexistent_budget_xyz", headers=headers)
    assert resp.status_code == 404, resp.text
