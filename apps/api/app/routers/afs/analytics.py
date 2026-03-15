"""AFS analytics and benchmarking endpoints."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router
from apps.api.app.routers.afs._common import (
    ComputeAnalyticsBody,
    _analytics_id,
    _load_benchmarks,
)
from apps.api.app.services.afs.analytics_ai import (
    assess_going_concern,
    detect_anomalies,
    generate_commentary,
)
from apps.api.app.services.afs.ratio_calculator import compute_from_tb
from apps.api.app.services.llm.router import LLMRouter

router = APIRouter()


@router.post("/engagements/{engagement_id}/analytics/compute")
async def compute_analytics(
    engagement_id: str,
    body: ComputeAnalyticsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Compute financial ratios and run AI analysis (anomalies, commentary, going concern)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Verify engagement exists
        eng = await conn.fetchrow(
            "SELECT entity_name, framework_id FROM afs_engagements WHERE tenant_id=$1 AND engagement_id=$2",
            x_tenant_id, engagement_id,
        )
        if not eng:
            raise HTTPException(404, "Engagement not found")

        # Get framework name
        fw = await conn.fetchrow(
            "SELECT name FROM afs_frameworks WHERE tenant_id=$1 AND framework_id=$2",
            x_tenant_id, eng["framework_id"],
        )
        framework_name = fw["name"] if fw else "IFRS"

        # Load latest trial balance
        tb = await conn.fetchrow(
            "SELECT data_json FROM afs_trial_balances WHERE tenant_id=$1 AND engagement_id=$2 ORDER BY uploaded_at DESC LIMIT 1",
            x_tenant_id, engagement_id,
        )
        if not tb or not tb["data_json"]:
            raise HTTPException(400, "No trial balance found. Upload one via the Setup page first.")

        data_json = tb["data_json"] if isinstance(tb["data_json"], list) else json.loads(tb["data_json"])

        # Compute ratios
        ratios = compute_from_tb(data_json)

        # Load benchmarks
        benchmarks_data = _load_benchmarks()
        segment = body.industry_segment
        segment_benchmarks = benchmarks_data.get("segments", {}).get(
            segment, benchmarks_data["segments"]["general"],
        )

        # Benchmark comparison: for each ratio, determine percentile position
        benchmark_comparison: dict[str, Any] = {}
        for key, value in ratios.items():
            if key.startswith("_") or value is None or key not in segment_benchmarks:
                continue
            b = segment_benchmarks[key]
            if value < b["p25"]:
                position = "below_p25"
            elif value < b["median"]:
                position = "p25_to_median"
            elif value < b["p75"]:
                position = "median_to_p75"
            else:
                position = "above_p75"
            benchmark_comparison[key] = {
                "value": value,
                "p25": b["p25"],
                "median": b["median"],
                "p75": b["p75"],
                "position": position,
            }

        # Run AI analysis in parallel
        entity_name = eng["entity_name"]
        anomalies_resp, commentary_resp, gc_resp = await asyncio.gather(
            detect_anomalies(
                llm, x_tenant_id,
                entity_name=entity_name, ratios=ratios, benchmarks=segment_benchmarks,
            ),
            generate_commentary(
                llm, x_tenant_id,
                entity_name=entity_name, framework_name=framework_name,
                ratios=ratios, benchmarks=segment_benchmarks,
            ),
            assess_going_concern(
                llm, x_tenant_id,
                entity_name=entity_name, framework_name=framework_name, ratios=ratios,
            ),
            return_exceptions=True,
        )

        anomalies = (
            anomalies_resp.content
            if not isinstance(anomalies_resp, Exception)
            else {"anomalies": [], "_error": str(anomalies_resp)}
        )
        commentary = (
            commentary_resp.content
            if not isinstance(commentary_resp, Exception)
            else None
        )
        going_concern = (
            gc_resp.content
            if not isinstance(gc_resp, Exception)
            else None
        )

        # Store
        aid = _analytics_id()
        await conn.execute(
            """INSERT INTO afs_analytics
               (tenant_id, analytics_id, engagement_id, ratios_json,
                benchmark_comparison_json, anomalies_json, commentary_json,
                going_concern_json, industry_segment, computed_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)""",
            x_tenant_id, aid, engagement_id,
            json.dumps(ratios), json.dumps(benchmark_comparison),
            json.dumps(anomalies),
            json.dumps(commentary) if commentary else None,
            json.dumps(going_concern) if going_concern else None,
            segment, x_user_id or None,
        )

        row = await conn.fetchrow(
            "SELECT * FROM afs_analytics WHERE tenant_id=$1 AND analytics_id=$2",
            x_tenant_id, aid,
        )

    return dict(row)


@router.get("/engagements/{engagement_id}/analytics")
async def get_analytics(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get the latest analytics result for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT * FROM afs_analytics
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY computed_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "No analytics found for this engagement")
        return dict(row)


@router.get("/engagements/{engagement_id}/analytics/ratios")
async def get_analytics_ratios(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get just the computed ratios from the latest analytics."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT ratios_json, benchmark_comparison_json, industry_segment, computed_at
               FROM afs_analytics
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY computed_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "No analytics found for this engagement")
        return dict(row)


@router.get("/engagements/{engagement_id}/analytics/anomalies")
async def get_analytics_anomalies(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get just the anomaly detection results from the latest analytics."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT anomalies_json, industry_segment, computed_at
               FROM afs_analytics
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY computed_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "No analytics found for this engagement")
        return dict(row)


@router.get("/engagements/{engagement_id}/analytics/going-concern")
async def get_going_concern(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get the going concern assessment from the latest analytics."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT going_concern_json, industry_segment, computed_at
               FROM afs_analytics
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY computed_at DESC LIMIT 1""",
            x_tenant_id, engagement_id,
        )
        if not row:
            raise HTTPException(404, "No analytics found for this engagement")
        return dict(row)
