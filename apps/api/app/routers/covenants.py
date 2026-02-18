"""Covenant definitions API (VA-P4-05): list, create, delete thresholds for run breach checks."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List all covenant definitions for the tenant."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        total = await conn.fetchval(
            "SELECT count(*) FROM covenant_definitions WHERE tenant_id = $1",
            x_tenant_id,
        )
        rows = await conn.fetch(
            """SELECT covenant_id, label, metric_ref, operator, threshold_value, created_at
               FROM covenant_definitions WHERE tenant_id = $1 ORDER BY created_at LIMIT $2 OFFSET $3""",
            x_tenant_id,
            limit,
            offset,
        )
        items = [
            {
                "covenant_id": r["covenant_id"],
                "label": r["label"],
                "metric_ref": r["metric_ref"],
                "operator": r["operator"],
                "threshold_value": float(r["threshold_value"]),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


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
