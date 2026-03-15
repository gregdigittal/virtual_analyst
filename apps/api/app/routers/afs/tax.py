"""AFS tax computation endpoints."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException

from apps.api.app.db import tenant_conn
from apps.api.app.deps import get_llm_router
from apps.api.app.routers.afs._common import (
    VALID_DIFF_TYPES,
    GenerateTaxNoteBody,
    TaxComputationBody,
    TemporaryDifferenceBody,
    _tax_computation_id,
    _temp_difference_id,
    _validate_engagement,
)
from apps.api.app.services.llm.router import LLMRouter

router = APIRouter()


@router.post("/engagements/{engagement_id}/tax/compute", status_code=201)
async def compute_tax(
    engagement_id: str,
    body: TaxComputationBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a tax computation for an engagement."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        eng = await conn.fetchrow(
            "SELECT * FROM afs_engagements WHERE tenant_id = $1 AND engagement_id = $2",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        current_tax = round(body.taxable_income * body.statutory_rate, 2)

        # Build reconciliation from adjustments
        reconciliation = []
        if body.adjustments:
            for adj in body.adjustments:
                desc = adj.get("description", "")
                amount = adj.get("amount", 0)
                effect = round(amount * body.statutory_rate, 2)
                reconciliation.append({"description": desc, "amount": amount, "tax_effect": effect})

        cid = _tax_computation_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_tax_computations
               (tenant_id, computation_id, engagement_id, entity_id, jurisdiction,
                statutory_rate, taxable_income, current_tax, reconciliation_json, created_by)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::jsonb, $10)
               RETURNING *""",
            x_tenant_id, cid, engagement_id, body.entity_id, body.jurisdiction,
            body.statutory_rate, body.taxable_income, current_tax,
            json.dumps(reconciliation), x_user_id or None,
        )
        result = dict(row)
        result["temporary_differences"] = []
        return result


@router.get("/engagements/{engagement_id}/tax")
async def list_tax_computations(
    engagement_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List all tax computations for an engagement with their temporary differences."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        comp_rows = await conn.fetch(
            """SELECT * FROM afs_tax_computations
               WHERE tenant_id = $1 AND engagement_id = $2
               ORDER BY created_at DESC""",
            x_tenant_id, engagement_id,
        )
        items = []
        for comp in comp_rows:
            item = dict(comp)
            diff_rows = await conn.fetch(
                """SELECT * FROM afs_temporary_differences
                   WHERE tenant_id = $1 AND computation_id = $2
                   ORDER BY description""",
                x_tenant_id, comp["computation_id"],
            )
            item["temporary_differences"] = [dict(d) for d in diff_rows]
            items.append(item)
        return {"items": items}


@router.post("/engagements/{engagement_id}/tax/{computation_id}/differences", status_code=201)
async def add_temporary_difference(
    engagement_id: str,
    computation_id: str,
    body: TemporaryDifferenceBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Add a temporary difference to a tax computation."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.diff_type not in VALID_DIFF_TYPES:
        raise HTTPException(400, f"Invalid diff_type '{body.diff_type}'. Must be 'asset' or 'liability'")

    async with tenant_conn(x_tenant_id) as conn:
        comp = await conn.fetchrow(
            "SELECT * FROM afs_tax_computations WHERE tenant_id = $1 AND computation_id = $2 AND engagement_id = $3",
            x_tenant_id, computation_id, engagement_id,
        )
        if not comp:
            raise HTTPException(404, f"Tax computation {computation_id} not found")

        difference = round(body.carrying_amount - body.tax_base, 2)
        deferred_tax_effect = round(difference * float(comp["statutory_rate"]), 2)

        did = _temp_difference_id()
        row = await conn.fetchrow(
            """INSERT INTO afs_temporary_differences
               (tenant_id, difference_id, computation_id, description,
                carrying_amount, tax_base, difference, deferred_tax_effect, diff_type)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
               RETURNING *""",
            x_tenant_id, did, computation_id, body.description,
            body.carrying_amount, body.tax_base, difference, deferred_tax_effect, body.diff_type,
        )

        # Update deferred_tax_json totals on the computation
        all_diffs = await conn.fetch(
            "SELECT * FROM afs_temporary_differences WHERE tenant_id = $1 AND computation_id = $2",
            x_tenant_id, computation_id,
        )
        total_assets = sum(float(d["deferred_tax_effect"]) for d in all_diffs if d["diff_type"] == "asset")
        total_liabilities = sum(float(d["deferred_tax_effect"]) for d in all_diffs if d["diff_type"] == "liability")
        deferred_json = {
            "total_deferred_tax_asset": round(total_assets, 2),
            "total_deferred_tax_liability": round(total_liabilities, 2),
            "net_deferred_tax": round(total_assets - total_liabilities, 2),
        }
        await conn.execute(
            "UPDATE afs_tax_computations SET deferred_tax_json = $1::jsonb, updated_at = now() WHERE tenant_id = $2 AND computation_id = $3",
            json.dumps(deferred_json), x_tenant_id, computation_id,
        )

        return dict(row)


@router.post("/engagements/{engagement_id}/tax/{computation_id}/generate-note")
async def generate_tax_note(
    engagement_id: str,
    computation_id: str,
    body: GenerateTaxNoteBody | None = None,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Generate an AI-drafted tax note for a computation."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    async with tenant_conn(x_tenant_id) as conn:
        # Load computation
        comp = await conn.fetchrow(
            "SELECT * FROM afs_tax_computations WHERE tenant_id = $1 AND computation_id = $2 AND engagement_id = $3",
            x_tenant_id, computation_id, engagement_id,
        )
        if not comp:
            raise HTTPException(404, f"Tax computation {computation_id} not found")

        # Load engagement + framework
        eng = await conn.fetchrow(
            """SELECT e.*, f.name AS framework_name, f.standard
               FROM afs_engagements e
               JOIN afs_frameworks f ON e.tenant_id = f.tenant_id AND e.framework_id = f.framework_id
               WHERE e.tenant_id = $1 AND e.engagement_id = $2""",
            x_tenant_id, engagement_id,
        )
        _validate_engagement(eng, engagement_id)

        # Load temporary differences
        diff_rows = await conn.fetch(
            "SELECT * FROM afs_temporary_differences WHERE tenant_id = $1 AND computation_id = $2 ORDER BY description",
            x_tenant_id, computation_id,
        )
        differences = [dict(d) for d in diff_rows]

        # Import and call AI drafter
        from apps.api.app.services.afs.tax_note_drafter import draft_tax_note

        nl_instruction = body.nl_instruction if body else None
        llm_result = await draft_tax_note(
            llm_router=llm,
            tenant_id=x_tenant_id,
            framework_name=eng["framework_name"],
            standard=eng["standard"],
            computation=dict(comp),
            differences=differences,
            nl_instruction=nl_instruction,
        )

        tax_note = {**llm_result.content}

        # Save to computation
        row = await conn.fetchrow(
            """UPDATE afs_tax_computations
               SET tax_note_json = $1::jsonb, updated_at = now()
               WHERE tenant_id = $2 AND computation_id = $3
               RETURNING *""",
            json.dumps(tax_note), x_tenant_id, computation_id,
        )
        result = dict(row)
        result["temporary_differences"] = differences
        result["llm_cost_usd"] = llm_result.cost_estimate_usd
        result["llm_tokens"] = llm_result.tokens.total_tokens
        return result
