"""Integration tests: tenant isolation (RLS / application-level)."""

from __future__ import annotations

from tests.conftest import minimal_model_config_dict
from tests.integration.conftest import integration_marker


@integration_marker
async def test_tenant_b_cannot_see_tenant_a_baselines(client) -> None:
    """List baselines as tenant B must not return baselines created by tenant A."""
    headers_a = {"X-Tenant-ID": "t_tenant_a", "X-User-ID": "u_a"}
    create = await client.post(
        "/api/v1/baselines",
        json={
            "model_config": minimal_model_config_dict(
                tenant_id="t_tenant_a", horizon_months=6, units=50, price=20
            )
        },
        headers=headers_a,
    )
    assert create.status_code == 201
    baseline_id_a = create.json()["baseline_id"]

    headers_b = {"X-Tenant-ID": "t_tenant_b", "X-User-ID": "u_b"}
    list_b = await client.get("/api/v1/baselines", headers=headers_b)
    assert list_b.status_code == 200
    items_b = list_b.json()["items"]
    assert not any(b["baseline_id"] == baseline_id_a for b in items_b)


@integration_marker
async def test_tenant_b_cannot_get_tenant_a_baseline_by_id(client) -> None:
    """Get baseline by ID as tenant B when baseline belongs to tenant A must return 404."""
    headers_a = {"X-Tenant-ID": "t_tenant_a_rls", "X-User-ID": "u_a"}
    create = await client.post(
        "/api/v1/baselines",
        json={
            "model_config": minimal_model_config_dict(tenant_id="t_tenant_a_rls", horizon_months=6)
        },
        headers=headers_a,
    )
    assert create.status_code == 201
    baseline_id_a = create.json()["baseline_id"]

    headers_b = {"X-Tenant-ID": "t_tenant_b_rls", "X-User-ID": "u_b"}
    get_b = await client.get(f"/api/v1/baselines/{baseline_id_a}", headers=headers_b)
    assert get_b.status_code == 404
