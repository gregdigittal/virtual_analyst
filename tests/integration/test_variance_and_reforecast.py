"""VA-P7-12: Variance and reforecast API integration — variance endpoint, reforecast (LLM may be skipped)."""

from __future__ import annotations

from tests.integration.conftest import integration_marker


@integration_marker
async def test_budget_variance_404_when_no_budget(client) -> None:
    """GET variance returns 404 for non-existent budget."""
    headers = {"X-Tenant-ID": "t_integration_var", "X-User-ID": "u1"}
    resp = await client.get(
        "/api/v1/budgets/nonexistent_budget_xyz/variance",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text


@integration_marker
async def test_budget_reforecast_404_when_no_budget(client) -> None:
    """POST reforecast returns 404 for non-existent budget."""
    headers = {"X-Tenant-ID": "t_integration_var", "X-User-ID": "u1"}
    resp = await client.post(
        "/api/v1/budgets/nonexistent_budget_xyz/reforecast",
        headers=headers,
    )
    assert resp.status_code == 404, resp.text
