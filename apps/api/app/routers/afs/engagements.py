"""AFS engagement lifecycle endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from apps.api.app.db import tenant_conn
from apps.api.app.routers.afs._common import (
    VALID_BASE_SOURCES,
    VALID_STATUSES,
    CreateEngagementBody,
    UpdateEngagementBody,
    _engagement_id,
)

router = APIRouter()


@router.post("/engagements", status_code=201)
async def create_engagement(
    body: CreateEngagementBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a new AFS engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Validate framework exists for this tenant
        fw = await conn.fetchrow(
            "SELECT framework_id FROM afs_frameworks WHERE tenant_id = $1 AND framework_id = $2",
            x_tenant_id,
            body.framework_id,
        )
        if not fw:
            raise HTTPException(404, "Framework not found")

        eid = _engagement_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_engagements
               (tenant_id, engagement_id, entity_name, framework_id, period_start, period_end,
                prior_engagement_id, status, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, 'setup', $8)
               RETURNING *""",
            x_tenant_id,
            eid,
            body.entity_name,
            body.framework_id,
            body.period_start,
            body.period_end,
            body.prior_engagement_id,
            x_user_id or None,
        )
        return dict(row)


@router.get("/engagements")
async def list_engagements(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(default=None, description="Filter by engagement status"),
) -> dict[str, Any]:
    """List engagements with pagination and optional status filter."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status; must be one of {sorted(VALID_STATUSES)}")

    async with tenant_conn(x_tenant_id) as conn:
        conditions = ["tenant_id = $1"]
        args: list[Any] = [x_tenant_id]
        idx = 1

        if status:
            idx += 1
            conditions.append(f"status = ${idx}")
            args.append(status)

        where = " AND ".join(conditions)

        # Total count
        total_row = await conn.fetchrow(
            f"SELECT count(*) AS cnt FROM afs_engagements WHERE {where}",
            *args,
        )
        total = total_row["cnt"] if total_row else 0

        # Paginated rows
        idx += 1
        limit_ph = idx
        idx += 1
        offset_ph = idx
        rows = await conn.fetch(
            f"SELECT * FROM afs_engagements WHERE {where} ORDER BY created_at DESC LIMIT ${limit_ph} OFFSET ${offset_ph}",
            *args,
            limit,
            offset,
        )
        return {"items": [dict(r) for r in rows], "total": total}


@router.get("/engagements/{engagement_id}")
async def get_engagement(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single engagement by ID."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id,
            engagement_id,
        )
        if not row:
            raise HTTPException(404, "Engagement not found")
        return dict(row)


@router.patch("/engagements/{engagement_id}")
async def update_engagement(
    engagement_id: str,
    body: UpdateEngagementBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update an engagement (partial). Only non-None fields are applied."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    # Validate status if provided
    if body.status is not None and body.status not in VALID_STATUSES:
        raise HTTPException(400, f"Invalid status; must be one of {sorted(VALID_STATUSES)}")

    # Validate base_source if provided
    if body.base_source is not None and body.base_source not in VALID_BASE_SOURCES:
        raise HTTPException(400, f"Invalid base_source; must be one of {sorted(VALID_BASE_SOURCES)}")

    async with tenant_conn(x_tenant_id) as conn:
        # Check existence
        existing = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id,
            engagement_id,
        )
        if not existing:
            raise HTTPException(404, "Engagement not found")

        # Build dynamic SET clause from non-None fields
        updates: list[str] = []
        args: list[Any] = [x_tenant_id, engagement_id]
        idx = 2

        if body.entity_name is not None:
            idx += 1
            updates.append(f"entity_name = ${idx}")
            args.append(body.entity_name)
        if body.status is not None:
            idx += 1
            updates.append(f"status = ${idx}")
            args.append(body.status)
        if body.base_source is not None:
            idx += 1
            updates.append(f"base_source = ${idx}")
            args.append(body.base_source)

        if not updates:
            return dict(existing)

        updates.append("updated_at = now()")
        set_clause = ", ".join(updates)

        row = await conn.fetchrow(
            f"UPDATE afs_engagements SET {set_clause} WHERE tenant_id = $1 AND engagement_id = $2 RETURNING *",
            *args,
        )
        return dict(row)


@router.delete("/engagements/{engagement_id}", status_code=204)
async def delete_engagement(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Delete an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        result = await conn.execute(
            "DELETE FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id,
            engagement_id,
        )
        if result and result.endswith("0"):
            raise HTTPException(404, "Engagement not found")


@router.post("/engagements/{engagement_id}/rollforward")
async def rollforward_engagement(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Roll forward sections and comparatives from the prior engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    from apps.api.app.services.afs.rollforward import rollforward_comparatives, rollforward_sections

    async with tenant_conn(x_tenant_id) as conn:
        # Validate engagement exists and has prior_engagement_id
        eng = await conn.fetchrow(
            "SELECT engagement_id, prior_engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        if not eng:
            raise HTTPException(404, "Engagement not found")
        if not eng["prior_engagement_id"]:
            raise HTTPException(400, "No prior engagement linked — set prior_engagement_id first")

        prior_id = eng["prior_engagement_id"]

        # Validate prior engagement exists
        prior = await conn.fetchval(
            "SELECT engagement_id FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, prior_id,
        )
        if not prior:
            raise HTTPException(404, f"Prior engagement {prior_id} not found")

        # Execute roll-forward
        sections_result = await rollforward_sections(
            conn, x_tenant_id, prior_id, engagement_id,
            created_by=x_user_id or None,
        )
        comparatives_result = await rollforward_comparatives(
            conn, x_tenant_id, prior_id, engagement_id,
        )

        return {
            "sections_copied": sections_result["sections_copied"],
            "comparatives_copied": comparatives_result["comparatives_copied"],
            "sections": sections_result["sections"],
        }
