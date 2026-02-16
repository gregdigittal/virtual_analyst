"""Workflow template engine API (VA-P6-03): templates, instances, create from template."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn

from apps.api.app.deps import require_role, ROLES_CAN_WRITE

router = APIRouter(prefix="/workflows", tags=["workflows"], dependencies=[require_role(*ROLES_CAN_WRITE)])


@router.get("/templates")
async def list_templates(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List workflow templates for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT template_id, name, description, stages_json, created_at
               FROM workflow_templates WHERE tenant_id = $1 ORDER BY name
               LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
    templates = [
        {
            "template_id": r["template_id"],
            "name": r["name"],
            "description": r["description"],
            "stages": r["stages_json"] if isinstance(r["stages_json"], list) else json.loads(r["stages_json"] or "[]"),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"templates": templates, "limit": limit, "offset": offset}


@router.get("/templates/{template_id}")
async def get_template(
    template_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a workflow template by id."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT template_id, name, description, stages_json, created_at
               FROM workflow_templates WHERE tenant_id = $1 AND template_id = $2""",
            x_tenant_id,
            template_id,
        )
    if not row:
        raise HTTPException(404, "Template not found")
    stages = row["stages_json"]
    if not isinstance(stages, list):
        stages = json.loads(stages or "[]")
    return {
        "template_id": row["template_id"],
        "name": row["name"],
        "description": row["description"],
        "stages": stages,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


class CreateInstanceBody(BaseModel):
    template_id: str = Field(..., min_length=1)
    entity_type: str = Field(..., min_length=1)
    entity_id: str = Field(..., min_length=1)


async def _resolve_assignee_for_stage(
    conn: Any,
    tenant_id: str,
    stage: dict[str, Any],
    _entity_type: str,
    _entity_id: str,
) -> str | None:
    """Resolve assignee user_id for a stage (VA-P8-05 cross-team). Supports explicit, team_pool, team (team_id)."""
    rule = (stage.get("assignee_rule") or "").strip().lower()
    config = stage.get("assignee_config") or {}
    if rule == "explicit" and config.get("user_id"):
        return config["user_id"]
    if rule == "team" and config.get("team_id"):
        team_id = config["team_id"]
        row = await conn.fetchrow(
            """SELECT user_id FROM team_members
               WHERE tenant_id = $1 AND team_id = $2
               ORDER BY CASE WHEN reports_to IS NULL THEN 0 ELSE 1 END, user_id
               LIMIT 1""",
            tenant_id,
            team_id,
        )
        if row:
            return row["user_id"]
        return None
    if rule == "team_pool":
        # R11-08: Use config.team_id when available so the correct team's member is assigned
        team_id = config.get("team_id")
        if team_id:
            row = await conn.fetchrow(
                """SELECT user_id FROM team_members
                   WHERE tenant_id = $1 AND team_id = $2
                   ORDER BY random() LIMIT 1""",
                tenant_id,
                team_id,
            )
        else:
            row = await conn.fetchrow(
                """SELECT user_id FROM team_members
                   WHERE tenant_id = $1
                   ORDER BY random() LIMIT 1""",
                tenant_id,
            )
        if row:
            return row["user_id"]
    return None


@router.post("/instances", status_code=201)
async def create_instance(
    body: CreateInstanceBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a workflow instance from a template (VA-P6-03). VA-P8-05: cross-team stages create first assignment."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    template_id = body.template_id
    entity_type = body.entity_type
    entity_id = body.entity_id
    instance_id = f"wf_{uuid.uuid4().hex[:14]}"
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT template_id, stages_json FROM workflow_templates WHERE tenant_id = $1 AND template_id = $2",
            x_tenant_id,
            template_id,
        )
        if not row:
            raise HTTPException(404, "Template not found")
        await conn.execute(
            """INSERT INTO workflow_instances
               (tenant_id, instance_id, template_id, entity_type, entity_id, current_stage_index, status, created_by)
               VALUES ($1, $2, $3, $4, $5, 0, 'pending', $6)""",
            x_tenant_id,
            instance_id,
            template_id,
            entity_type,
            entity_id,
            x_user_id or None,
        )
        stages = row["stages_json"]
        if not isinstance(stages, list):
            stages = json.loads(stages or "[]")
        assignee_user_id: str | None = None
        if stages:
            stage0 = stages[0] if isinstance(stages[0], dict) else {}
            assignee_user_id = await _resolve_assignee_for_stage(
                conn,
                x_tenant_id,
                stage0,
                entity_type,
                entity_id,
            )
        if assignee_user_id:
            assignment_id = f"asn_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                """INSERT INTO task_assignments
                   (tenant_id, assignment_id, workflow_instance_id, entity_type, entity_id, assignee_user_id, assigned_by_user_id, status)
                   VALUES ($1, $2, $3, $4, $5, $6, $7, 'assigned')""",
                x_tenant_id,
                assignment_id,
                instance_id,
                entity_type,
                entity_id,
                assignee_user_id,
                x_user_id or None,
            )
    return {
        "instance_id": instance_id,
        "template_id": template_id,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "current_stage_index": 0,
        "status": "pending",
    }


class UpdateInstanceBody(BaseModel):
    status: str = Field(..., description="New status: in_progress, submitted, approved, returned, completed")


@router.patch("/instances/{instance_id}", status_code=200)
async def update_instance(
    instance_id: str,
    body: UpdateInstanceBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update workflow instance status (VA-P7-06). When status=completed and entity_type=budget, sets budget to active."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    valid = {"in_progress", "submitted", "approved", "returned", "completed"}
    if body.status not in valid:
        raise HTTPException(400, f"status must be one of {sorted(valid)}")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT entity_type, entity_id, status FROM workflow_instances
                   WHERE tenant_id = $1 AND instance_id = $2""",
                x_tenant_id,
                instance_id,
            )
            if not row:
                raise HTTPException(404, "Workflow instance not found")
            current_status = row["status"]
            allowed_transitions = {
                "pending": {"in_progress", "submitted"},
                "in_progress": {"submitted", "returned"},
                "submitted": {"approved", "returned"},
                "approved": {"completed"},
                "returned": {"in_progress", "submitted"},
            }
            if body.status not in allowed_transitions.get(current_status, set()):
                raise HTTPException(
                    400,
                    f"Cannot transition from '{current_status}' to '{body.status}'; "
                    f"allowed: {sorted(allowed_transitions.get(current_status, set()))}",
                )
            await conn.execute(
                """UPDATE workflow_instances SET status = $1, updated_at = now()
                   WHERE tenant_id = $2 AND instance_id = $3""",
                body.status,
                x_tenant_id,
                instance_id,
            )
            if body.status == "completed" and row["entity_type"] == "budget":
                await conn.execute(
                    """UPDATE budgets SET status = 'active', updated_at = now()
                       WHERE tenant_id = $1 AND workflow_instance_id = $2""",
                    x_tenant_id,
                    instance_id,
                )
    return {"instance_id": instance_id, "status": body.status}


@router.get("/instances/{instance_id}")
async def get_instance(
    instance_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a workflow instance."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT wi.instance_id, wi.template_id, wi.entity_type, wi.entity_id,
                      wi.current_stage_index, wi.status, wi.created_at, wi.created_by, wi.updated_at
               FROM workflow_instances wi
               WHERE wi.tenant_id = $1 AND wi.instance_id = $2""",
            x_tenant_id,
            instance_id,
        )
    if not row:
        raise HTTPException(404, "Workflow instance not found")
    return {
        "instance_id": row["instance_id"],
        "template_id": row["template_id"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "current_stage_index": row["current_stage_index"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "created_by": row["created_by"],
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


@router.get("/instances")
async def list_instances(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    entity_type: str | None = Query(None),
    entity_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List workflow instances for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        conditions = ["tenant_id = $1"]
        params: list[Any] = [x_tenant_id]
        idx = 2
        if entity_type:
            conditions.append(f"entity_type = ${idx}")
            params.append(entity_type)
            idx += 1
        if entity_id:
            conditions.append(f"entity_id = ${idx}")
            params.append(entity_id)
            idx += 1
        if status:
            conditions.append(f"status = ${idx}")
            params.append(status)
            idx += 1
        params.append(limit)
        params.append(offset)
        limit_off = f"LIMIT ${idx} OFFSET ${idx + 1}"
        rows = await conn.fetch(
            f"""SELECT instance_id, template_id, entity_type, entity_id, current_stage_index, status, created_at
                FROM workflow_instances WHERE {" AND ".join(conditions)}
                ORDER BY created_at DESC {limit_off}""",
            *params,
        )
    items = [
        {
            "instance_id": r["instance_id"],
            "template_id": r["template_id"],
            "entity_type": r["entity_type"],
            "entity_id": r["entity_id"],
            "current_stage_index": r["current_stage_index"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"instances": items, "limit": limit, "offset": offset}


# --- VA-P8-06: Workflow analytics ---


@router.get("/analytics")
async def get_workflow_analytics(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    template_id: str | None = Query(None),
    start_date: str | None = Query(None, description="YYYY-MM-DD"),
    end_date: str | None = Query(None, description="YYYY-MM-DD"),
) -> dict[str, Any]:
    """Workflow analytics (VA-P8-06): cycle time (created → completed), time per stage, review rate, bottlenecks."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conditions = ["tenant_id = $1"]
    params: list[Any] = [x_tenant_id]
    idx = 2
    if template_id:
        conditions.append(f"template_id = ${idx}")
        params.append(template_id)
        idx += 1
    if start_date:
        conditions.append(f"created_at >= ${idx}::date")
        params.append(start_date)
        idx += 1
    if end_date:
        conditions.append(f"created_at <= ${idx}::date + interval '1 day'")
        params.append(end_date)
        idx += 1
    where = " AND ".join(conditions)
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            f"""SELECT instance_id, template_id, status, created_at, updated_at
                FROM workflow_instances WHERE {where}""",
            *params,
        )
        # Stage-level timing from workflow_events if present
        ev_conditions = ["we.tenant_id = $1", "we.exited_at IS NOT NULL"]
        ev_params: list[Any] = [x_tenant_id]
        ev_idx = 2
        if template_id:
            ev_conditions.append("wi.template_id = $" + str(ev_idx))
            ev_params.append(template_id)
            ev_idx += 1
        if start_date:
            ev_conditions.append("we.entered_at >= $" + str(ev_idx) + "::date")
            ev_params.append(start_date)
            ev_idx += 1
        if end_date:
            ev_conditions.append("we.entered_at <= $" + str(ev_idx) + "::date + interval '1 day'")
            ev_params.append(end_date)
        ev_where = " AND ".join(ev_conditions)
        stage_rows = await conn.fetch(
            f"""SELECT we.instance_id, we.stage_index, we.entered_at, we.exited_at, we.outcome
                FROM workflow_events we
                JOIN workflow_instances wi ON wi.tenant_id = we.tenant_id AND wi.instance_id = we.instance_id
                WHERE {ev_where}""",
            *ev_params,
        )
    # Cycle time: completed instances only (created_at -> updated_at)
    cycle_times: list[float] = []
    for r in rows:
        if r["status"] == "completed" and r["created_at"] and r["updated_at"]:
            delta = (r["updated_at"] - r["created_at"]).total_seconds()
            cycle_times.append(delta)
    avg_cycle_seconds = sum(cycle_times) / len(cycle_times) if cycle_times else None
    # Review rate: of instances that reached submitted, proportion approved vs returned
    submitted_count = sum(1 for r in rows if r["status"] in ("approved", "returned", "completed"))
    approved_count = sum(1 for r in rows if r["status"] in ("approved", "completed"))
    review_rate = (approved_count / submitted_count) if submitted_count else None
    # Stage breakdown (from workflow_events)
    stage_durations: dict[int, list[float]] = {}
    for r in stage_rows:
        if r["exited_at"] and r["entered_at"]:
            dur = (r["exited_at"] - r["entered_at"]).total_seconds()
            stage_durations.setdefault(r["stage_index"], []).append(dur)
    stage_breakdown = [
        {"stage_index": i, "avg_seconds": sum(durs) / len(durs), "count": len(durs)}
        for i, durs in sorted(stage_durations.items())
    ]
    # Bottleneck: stage with longest average time
    bottleneck = None
    if stage_breakdown:
        slowest = max(stage_breakdown, key=lambda s: s["avg_seconds"])
        bottleneck = {"stage_index": slowest["stage_index"], "avg_seconds": slowest["avg_seconds"]}
    # Count by status
    count_by_status: dict[str, int] = {}
    for r in rows:
        count_by_status[r["status"]] = count_by_status.get(r["status"], 0) + 1
    return {
        "cycle_time_seconds": {"avg": avg_cycle_seconds, "sample_count": len(cycle_times)},
        "review_rate": review_rate,
        "stage_breakdown": stage_breakdown,
        "bottleneck": bottleneck,
        "count_by_status": count_by_status,
        "total_instances": len(rows),
    }
