"""VA-P6-12: Workflow integration test — assign → submit → review → approve.

Full flow: create assignment → submit → review (approve). Requires INTEGRATION_TESTS=1
and DATABASE_URL with migrations 0020–0024 applied (workflow_templates, task_assignments,
reviews, change_summaries). Uses same tenant/user pattern as test_baseline_run_lifecycle.
"""

from __future__ import annotations

from tests.integration.conftest import integration_marker


@integration_marker
async def test_workflow_lifecycle_assign_submit_review_approve(client) -> None:
    """Create assignment → submit as assignee → review (approve) as reviewer → assert completed."""
    tenant = "t_integration"
    assignee = "u1"
    reviewer = "u2"
    headers_assigner = {"X-Tenant-ID": tenant, "X-User-ID": reviewer}
    headers_assignee = {"X-Tenant-ID": tenant, "X-User-ID": assignee}

    # Create assignment (assigner assigns to assignee)
    create = await client.post(
        "/api/v1/assignments",
        json={
            "entity_type": "draft",
            "entity_id": "d_wf_integration",
            "assignee_user_id": assignee,
            "instructions": "Integration test task",
        },
        headers=headers_assigner,
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assignment_id = body["assignment_id"]
    assert body["status"] == "assigned"
    assert body["assignee_user_id"] == assignee

    # Submit (assignee submits for review)
    submit = await client.post(
        f"/api/v1/assignments/{assignment_id}/submit",
        headers=headers_assignee,
    )
    assert submit.status_code == 200, submit.text
    assert submit.json().get("status") == "submitted"

    # Review — approve (reviewer approves)
    review = await client.post(
        f"/api/v1/assignments/{assignment_id}/review",
        json={"decision": "approved", "notes": "Integration test approve"},
        headers=headers_assigner,
    )
    assert review.status_code in (200, 201), review.text
    assert review.json().get("decision") == "approved"

    # Assignment should be completed
    get_assignment = await client.get(
        f"/api/v1/assignments/{assignment_id}",
        headers=headers_assigner,
    )
    assert get_assignment.status_code == 200, get_assignment.text
    assert get_assignment.json().get("status") == "completed"


@integration_marker
async def test_workflow_lifecycle_request_changes(client) -> None:
    """Create assignment → submit → review (request_changes) with corrections → assert returned."""
    tenant = "t_integration"
    assignee = "u1"
    reviewer = "u2"
    headers_assigner = {"X-Tenant-ID": tenant, "X-User-ID": reviewer}
    headers_assignee = {"X-Tenant-ID": tenant, "X-User-ID": assignee}

    create = await client.post(
        "/api/v1/assignments",
        json={
            "entity_type": "draft",
            "entity_id": "d_wf_return_integration",
            "assignee_user_id": assignee,
        },
        headers=headers_assigner,
    )
    assert create.status_code == 201, create.text
    assignment_id = create.json()["assignment_id"]

    await client.post(
        f"/api/v1/assignments/{assignment_id}/submit",
        headers=headers_assignee,
    )
    review_resp = await client.post(
        f"/api/v1/assignments/{assignment_id}/review",
        json={
            "decision": "request_changes",
            "notes": "Please fix assumption X",
            "corrections": [
                {"path": "assumptions.revenue.growth", "old_value": "0.05", "new_value": "0.06", "reason": "Align to plan"}
            ],
        },
        headers=headers_assigner,
    )
    assert review_resp.status_code in (200, 201)

    get_assignment = await client.get(f"/api/v1/assignments/{assignment_id}", headers=headers_assigner)
    assert get_assignment.status_code == 200
    assert get_assignment.json().get("status") == "returned"
