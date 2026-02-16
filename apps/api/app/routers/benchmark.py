"""VA-P8-08: Peer comparison (opt-in, anonymous). VA-P8-09: benchmark aggregates for board pack."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn
from apps.api.app.deps import require_role, ROLES_CAN_WRITE

router = APIRouter(prefix="/benchmark", tags=["benchmark"], dependencies=[require_role(*ROLES_CAN_WRITE)])


class OptInBody(BaseModel):
    industry_segment: str = Field(default="general", max_length=64)
    size_segment: str = Field(default="general", max_length=64)


@router.get("/opt-in")
async def get_benchmark_opt_in(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get tenant's benchmark opt-in status (VA-P8-08)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT industry_segment, size_segment, opted_in_at FROM tenant_benchmark_opt_in WHERE tenant_id = $1",
            x_tenant_id,
        )
    if not row:
        return {"opted_in": False}
    return {
        "opted_in": True,
        "industry_segment": row["industry_segment"],
        "size_segment": row["size_segment"],
        "opted_in_at": row["opted_in_at"].isoformat() if row["opted_in_at"] else None,
    }


@router.put("/opt-in")
async def set_benchmark_opt_in(
    body: OptInBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Opt in or update segment for anonymous peer benchmarking (VA-P8-08)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO tenant_benchmark_opt_in (tenant_id, industry_segment, size_segment)
               VALUES ($1, $2, $3)
               ON CONFLICT (tenant_id) DO UPDATE SET industry_segment = EXCLUDED.industry_segment, size_segment = EXCLUDED.size_segment""",
            x_tenant_id,
            body.industry_segment,
            body.size_segment,
        )
    return {"ok": True, "industry_segment": body.industry_segment, "size_segment": body.size_segment}


@router.delete("/opt-in")
async def delete_benchmark_opt_in(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Opt out of peer benchmarking."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute("DELETE FROM tenant_benchmark_opt_in WHERE tenant_id = $1", x_tenant_id)
    return {"ok": True}


@router.get("/summary")
async def get_benchmark_summary(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    segment_key: str | None = Query(None, description="e.g. general|general or industry|size"),
) -> dict[str, Any]:
    """Get peer benchmark summary for opted-in tenant (VA-P8-08). No tenant identity in aggregates."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            "SELECT industry_segment, size_segment FROM tenant_benchmark_opt_in WHERE tenant_id = $1",
            x_tenant_id,
        )
    if not row:
        raise HTTPException(403, "Opt in to benchmarking to view peer summary")
    key = segment_key or f"{row['industry_segment']}|{row['size_segment']}"
    async with tenant_conn(x_tenant_id) as conn:
        rows = await conn.fetch(
            "SELECT metric_name, median_value, p25_value, p75_value, sample_count, computed_at FROM benchmark_aggregates WHERE segment_key = $1 ORDER BY metric_name",
            key,
        )
    metrics = [
        {
            "metric_name": r["metric_name"],
            "median": float(r["median_value"]),
            "p25": float(r["p25_value"]) if r["p25_value"] is not None else None,
            "p75": float(r["p75_value"]) if r["p75_value"] is not None else None,
            "sample_count": r["sample_count"],
            "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
        }
        for r in rows
    ]
    return {"segment_key": key, "metrics": metrics}


@router.get("/aggregates")
async def list_benchmark_aggregates(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    segment_key: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List benchmark aggregates (for board pack benchmark section). VA-P8-09."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if segment_key:
            rows = await conn.fetch(
                "SELECT segment_key, metric_name, median_value, p25_value, p75_value, sample_count, computed_at FROM benchmark_aggregates WHERE segment_key = $1 ORDER BY metric_name LIMIT $2",
                segment_key,
                limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT segment_key, metric_name, median_value, p25_value, p75_value, sample_count, computed_at FROM benchmark_aggregates ORDER BY segment_key, metric_name LIMIT $1",
                limit,
            )
    items = [
        {
            "segment_key": r["segment_key"],
            "metric_name": r["metric_name"],
            "median": float(r["median_value"]),
            "p25": float(r["p25_value"]) if r["p25_value"] is not None else None,
            "p75": float(r["p75_value"]) if r["p75_value"] is not None else None,
            "sample_count": r["sample_count"],
            "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
        }
        for r in rows
    ]
    return {"aggregates": items}