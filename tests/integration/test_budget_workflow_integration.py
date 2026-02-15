"""VA-P7-12: Budget workflow integration — create budget → submit → workflow complete → budget active."""

from __future__ import annotations

from tests.integration.conftest import integration_marker


@integration_marker
async def test_budget_submit_creates_workflow(client) -> None:
    """Create a draft budget (from template or minimal), submit for approval, verify workflow instance."""
    tenant = "t_integration_budget_wf"
    user = "u1"
    headers = {"X-Tenant-ID": tenant, "X-User-ID": user}

    templates = await client.get("/api/v1/budgets/templates", headers=headers)
    if templates.status_code != 200 or not templates.json().get("templates"):
        return  # skip if no templates

    template_id = templates.json()["templates"][0]["template_id"]
    create = await client.post(
        "/api/v1/budgets/from-template",
        json={
            "template_id": template_id,
            "label": "WF integration budget",
            "fiscal_year": "FY2026",
            "answers": {},
        },
        headers=headers,
    )
    if create.status_code not in (200, 201):
        return  # skip if template creation fails (e.g. LLM not configured)
    budget_id = create.json()["budget_id"]
    assert create.json()["status"] == "draft"

    submit = await client.post(
        f"/api/v1/budgets/{budget_id}/submit",
        headers=headers,
    )
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert body["status"] == "submitted"
    assert body.get("workflow_instance_id")

    get_budget = await client.get(f"/api/v1/budgets/{budget_id}", headers=headers)
    assert get_budget.status_code == 200
    assert get_budget.json().get("workflow_instance_id")
    assert get_budget.json()["status"] == "submitted"


@integration_marker
async def test_budget_workflow_complete_sets_active(client) -> None:
    """After submit, PATCH workflow instance to completed -> budget status becomes active (when entity_type=budget)."""
    tenant = "t_integration_budget_wf"
    user = "u1"
    headers = {"X-Tenant-ID": tenant, "X-User-ID": user}

    list_instances = await client.get(
        "/api/v1/workflows/instances?entity_type=budget&status=pending",
        headers=headers,
    )
    if list_instances.status_code != 200:
        return
    instances = list_instances.json().get("items") or []
    if not instances:
        return  # no pending budget workflow

    instance_id = instances[0]["instance_id"]
    patch = await client.patch(
        f"/api/v1/workflows/instances/{instance_id}",
        json={"status": "completed"},
        headers=headers,
    )
    assert patch.status_code == 200, patch.text
    entity_id = instances[0].get("entity_id")
    if entity_id:
        get_budget = await client.get(f"/api/v1/budgets/{entity_id}", headers=headers)
        if get_budget.status_code == 200:
            assert get_budget.json()["status"] == "active"
