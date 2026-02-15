"""Workflow template engine API (VA-P6-03): templates, instances, create from template."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn

router = APIRouter(prefix="/workflows", tags=["workflows"])


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


@router.post("/instances", status_code=201)
async def create_instance(
    body: CreateInstanceBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a workflow instance from a template (VA-P6-03)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    template_id = body.template_id
    entity_type = body.entity_type
    entity_id = body.entity_id
    instance_id = f"wf_{uuid.uuid4().hex[:14]}"
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM workflow_templates WHERE tenant_id = $1 AND template_id = $2",
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
