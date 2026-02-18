"""Covenant definitions API (VA-P4-05): list, create, delete thresholds for run breach checks."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.db.audit import create_audit_event
from apps.api.app.db.covenants import COVENANT_METRIC_REFS, list_covenant_definitions
from apps.api.app.deps import require_role, ROLES_CAN_WRITE

router = APIRouter(prefix="/covenants", tags=["covenants"], dependencies=[require_role(*ROLES_CAN_WRITE)])

OPERATORS = frozenset({"<", ">", "<=", ">="})


class CreateCovenantBody(BaseModel):
    """Body for creating a covenant definition."""

    label: str = Field(..., min_length=1, max_length=200, description="Human-readable label")
    metric_ref: str = Field(..., description="KPI key from run output")
    operator: str = Field(..., description="Comparison operator: <, >, <=, >=")
    threshold_value: float = Field(..., description="Threshold value")


@router.get("/metric-refs")
async def list_metric_refs() -> dict[str, Any]:
    """Return allowed metric_ref values for covenant definitions (KPI keys from run)."""
    return {"metric_refs": sorted(COVENANT_METRIC_REFS), "operators": sorted(OPERATORS)}


@router.get("")
async def list_covenants(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all covenant definitions for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        items = await list_covenant_definitions(conn, x_tenant_id)
    return {"items": items}


@router.post("", status_code=201)
async def create_covenant(
    body: CreateCovenantBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Create a covenant definition. metric_ref must be a KPI key from run output."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.metric_ref not in COVENANT_METRIC_REFS:
        raise HTTPException(
            400,
            f"metric_ref must be one of: {sorted(COVENANT_METRIC_REFS)}",
        )
    if body.operator not in OPERATORS:
        raise HTTPException(400, f"operator must be one of: {sorted(OPERATORS)}")
    covenant_id = f"cv_{uuid.uuid4().hex[:12]}"
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO covenant_definitions (tenant_id, covenant_id, label, metric_ref, operator, threshold_value)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            x_tenant_id,
            covenant_id,
            body.label,
            body.metric_ref,
            body.operator,
            body.threshold_value,
        )
        await create_audit_event(
            conn,
            x_tenant_id,
            "covenant.created",
            "covenant",
            "covenant_definition",
            covenant_id,
            event_data={
                "metric_ref": body.metric_ref,
                "operator": body.operator,
                "threshold": body.threshold_value,
            },
        )
    return {
        "covenant_id": covenant_id,
        "label": body.label,
        "metric_ref": body.metric_ref,
        "operator": body.operator,
        "threshold_value": body.threshold_value,
    }


@router.delete("/{covenant_id}", status_code=204)
async def delete_covenant(
    covenant_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Delete a covenant definition."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            result = await conn.execute(
                "DELETE FROM covenant_definitions WHERE tenant_id = $1 AND covenant_id = $2",
                x_tenant_id,
                covenant_id,
            )
            if result == "DELETE 0":
                raise HTTPException(404, "Covenant not found")
            await create_audit_event(
                conn,
                x_tenant_id,
                "covenant.deleted",
                "covenant",
                "covenant_definition",
                covenant_id,
            )
