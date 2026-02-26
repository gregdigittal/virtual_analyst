"""VA-P8-03: Template marketplace — list templates, get by id, use template (creates budget/baseline + audit)."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.data.budget_catalog import get_budget_template
from apps.api.app.db import tenant_conn
from apps.api.app.db.audit import create_audit_event, EVENT_MARKETPLACE_TEMPLATE_USED
from apps.api.app.deps import get_artifact_store, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.routers.budgets import create_budget_from_template_impl
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.storage import ArtifactStore

router = APIRouter(prefix="/marketplace", tags=["marketplace"], dependencies=[require_role(*ROLES_CAN_WRITE)])


class UseMarketplaceTemplateBody(BaseModel):
    """Body for use template (budget): same as create budget from template minus template_id (from path)."""
    label: str = Field(..., min_length=1, max_length=255)
    fiscal_year: str = Field(..., min_length=1, max_length=32)
    answers: dict[str, Any] = Field(default_factory=dict)
    prior_year_actuals: list[dict[str, Any]] | None = Field(default=None)
    num_periods: int = Field(default=12, ge=1, le=24)


class SaveAsTemplateBody(BaseModel):
    """Body for saving a baseline as a reusable marketplace template."""
    source_baseline_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=255)
    industry: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)


# ---------------------------------------------------------------------------
# Helpers: extract template structure from baseline assumptions
# ---------------------------------------------------------------------------

def _extract_question_plan_from_assumptions(assumptions: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract question structure (revenue stream types, funding instruments) without actual values."""
    plan: list[dict[str, Any]] = []
    for stream in assumptions.get("revenue_streams", []):
        entry: dict[str, Any] = {"section": "revenue"}
        if stream.get("stream_type"):
            entry["stream_type"] = stream["stream_type"]
        if stream.get("label"):
            entry["label"] = stream["label"]
        if stream.get("business_line"):
            entry["business_line"] = stream["business_line"]
        plan.append(entry)
    funding = assumptions.get("funding", {})
    if isinstance(funding, dict):
        for instrument, _details in funding.items():
            plan.append({"section": "funding", "instrument": instrument})
    return plan


def _extract_account_refs(assumptions: dict[str, Any]) -> list[str]:
    """Extract unique account reference names from cost_structure."""
    refs: list[str] = []
    seen: set[str] = set()
    cost_structure = assumptions.get("cost_structure", {})
    if isinstance(cost_structure, dict):
        for category_items in cost_structure.values():
            items = category_items if isinstance(category_items, list) else [category_items]
            for item in items:
                if isinstance(item, dict):
                    ref = item.get("account_ref") or item.get("label") or ""
                    if ref and ref not in seen:
                        refs.append(ref)
                        seen.add(ref)
    return refs


@router.get("/templates")
async def list_marketplace_templates(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    industry: str | None = None,
    template_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List marketplace templates (VA-P8-03). Optional filter by industry or template_type (budget, model)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    conditions = ["1=1"]
    params: list[Any] = []
    idx = 1
    if industry:
        conditions.append(f"industry = ${idx}")
        params.append(industry)
        idx += 1
    if template_type:
        conditions.append(f"template_type = ${idx}")
        params.append(template_type)
        idx += 1
    where_clause = " AND ".join(conditions)
    async with tenant_conn(x_tenant_id) as conn:
        total = await conn.fetchval(
            f"SELECT count(*) FROM marketplace_templates WHERE {where_clause}",
            *params,
        )
        params_fetch = list(params) + [limit, offset]
        limit_ph, offset_ph = idx, idx + 1
        rows = await conn.fetch(
            f"""SELECT template_id, name, industry, template_type, description, created_at
                FROM marketplace_templates WHERE {where_clause}
                ORDER BY name
                LIMIT ${limit_ph} OFFSET ${offset_ph}""",
            *params_fetch,
        )
    items = [
        {
            "template_id": r["template_id"],
            "name": r["name"],
            "industry": r["industry"],
            "template_type": r["template_type"],
            "description": r["description"] or "",
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/templates/{template_id}")
async def get_marketplace_template(
    template_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single marketplace template by id (VA-P8-03)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT template_id, name, industry, template_type, description, created_at
               FROM marketplace_templates WHERE template_id = $1""",
            template_id,
        )
    if not row:
        raise HTTPException(404, "Template not found")
    return {
        "template_id": row["template_id"],
        "name": row["name"],
        "industry": row["industry"],
        "template_type": row["template_type"],
        "description": row["description"] or "",
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.post("/templates/{template_id}/use", status_code=201)
async def use_marketplace_template(
    template_id: str,
    body: UseMarketplaceTemplateBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Use a marketplace template: creates budget (or baseline) and records audit (VA-P8-03)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT template_id, name, template_type FROM marketplace_templates WHERE template_id = $1""",
            template_id,
        )
    if not row:
        raise HTTPException(404, "Template not found")
    if row["template_type"] == "budget":
        if not get_budget_template(template_id):
            raise HTTPException(404, "Budget template definition not found")
        result = await create_budget_from_template_impl(
            tenant_id=x_tenant_id,
            user_id=x_user_id or None,
            template_id=template_id,
            label=body.label,
            fiscal_year=body.fiscal_year,
            answers=body.answers,
            prior_year_actuals=body.prior_year_actuals,
            num_periods=body.num_periods,
            llm=llm,
        )
        async with tenant_conn(x_tenant_id) as conn:
            await create_audit_event(
                conn,
                x_tenant_id,
                EVENT_MARKETPLACE_TEMPLATE_USED,
                "marketplace",
                "budget",
                result["budget_id"],
                user_id=x_user_id or None,
                event_data={"template_id": template_id, "template_name": row["name"], "created_budget_id": result["budget_id"]},
            )
        return {"ok": True, "template_id": template_id, "created": {"type": "budget", "budget_id": result["budget_id"], **result}}
    if row["template_type"] == "model":
        raise HTTPException(501, "Model template use not yet implemented")
    raise HTTPException(400, "Unknown template type")


@router.post("/templates/from-baseline", status_code=201)
async def save_baseline_as_template(
    body: SaveAsTemplateBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    store: ArtifactStore = Depends(get_artifact_store),
) -> dict[str, Any]:
    """Save a completed baseline as a reusable marketplace template."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")

    # 1. Load baseline row from DB
    async with tenant_conn(x_tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT baseline_id, baseline_version, storage_path, is_active
               FROM model_baselines
               WHERE tenant_id = $1 AND baseline_id = $2 AND is_active = true""",
            x_tenant_id,
            body.source_baseline_id,
        )
    if not row:
        raise HTTPException(404, "Baseline not found")

    # 2. Load the baseline config from artifact store
    artifact_id = f"{row['baseline_id']}_{row['baseline_version']}"
    config = store.load(x_tenant_id, "model_config_v1", artifact_id)
    if not config:
        raise HTTPException(404, "Baseline config artifact not found")

    # 3. Extract assumption structure without actual values
    assumptions = config.get("assumptions", {}) if isinstance(config, dict) else {}
    question_plan = _extract_question_plan_from_assumptions(assumptions)
    account_refs = _extract_account_refs(assumptions)

    # 4. Generate unique template_id
    template_id = f"user-{uuid.uuid4().hex[:12]}"

    # 5. Insert into marketplace_templates
    async with tenant_conn(x_tenant_id) as conn:
        await conn.execute(
            """INSERT INTO marketplace_templates (template_id, name, industry, template_type, description)
               VALUES ($1, $2, $3, 'model', $4)""",
            template_id,
            body.name,
            body.industry,
            body.description,
        )

    return {
        "template_id": template_id,
        "name": body.name,
        "industry": body.industry,
        "template_type": "model",
        "description": body.description,
        "question_plan": question_plan,
        "account_refs": account_refs,
    }
