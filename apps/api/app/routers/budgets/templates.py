"""Budget templates and LLM-assisted seeding (VA-P7-03)."""

from __future__ import annotations

import calendar
import json
from datetime import date
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.data.budget_catalog import get_budget_template, load_budget_catalog
from apps.api.app.deps import get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.routers.budgets._common import (
    _budget_id,
    _line_item_id,
    _period_id,
    _version_id,
    ensure_budget_version,
    logger,
    tenant_conn,
)
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import LLMError

router = APIRouter(tags=["budgets"], dependencies=[require_role(*ROLES_CAN_WRITE)])


# --- LLM response schema ---
BUDGET_INITIALIZATION_SCHEMA = {
    "type": "object",
    "properties": {
        "line_items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "account_ref": {"type": "string"},
                    "notes": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "amounts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"period_ordinal": {"type": "integer"}, "amount": {"type": "number"}},
                            "required": ["period_ordinal", "amount"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["account_ref", "notes", "confidence", "amounts"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["line_items"],
    "additionalProperties": False,
}


def _build_budget_initialization_prompt(
    template_label: str,
    fiscal_year: str,
    question_plan: list[dict[str, Any]],
    answers: dict[str, Any],
    prior_year_actuals: list[dict[str, Any]] | None,
    num_periods: int,
    account_refs: list[str],
) -> str:
    parts = [
        "You are a financial analyst. Propose initial budget line-item amounts (monthly) based on the following.",
        f"Template: {template_label}. Fiscal year: {fiscal_year}. Number of periods: {num_periods}.",
        "Output only valid JSON matching the schema. Do not fabricate data; base amounts on the context.",
        "",
        "Questionnaire answers:",
        json.dumps(answers, indent=2),
    ]
    if prior_year_actuals:
        parts.extend(["", "Prior-year actuals (for reference):", json.dumps(prior_year_actuals, indent=2)])
    parts.extend([
        "",
        "Suggested account line items (use these account_ref values):",
        json.dumps(account_refs),
        "",
        "Return one amount per period_ordinal (1 to num_periods) for each line item. Use confidence 0.0-1.0.",
    ])
    return "\n".join(parts)


class CreateBudgetFromTemplateBody(BaseModel):
    template_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1, max_length=255)
    fiscal_year: str = Field(..., min_length=1, max_length=32)
    answers: dict[str, Any] = Field(default_factory=dict, description="Questionnaire answers")
    prior_year_actuals: list[dict[str, Any]] | None = Field(default=None, description="Optional prior-year actuals for context")
    num_periods: int = Field(default=12, ge=1, le=24)


@router.get("/templates")
async def list_budget_templates() -> dict[str, Any]:
    """List budget templates (manufacturing, SaaS, services, wholesale)."""
    catalog = load_budget_catalog()
    templates = [
        {"template_id": t["template_id"], "label": t["label"], "industry": t.get("industry", "")}
        for t in catalog.get("templates", [])
    ]
    return {"templates": templates}


async def create_budget_from_template_impl(
    tenant_id: str,
    user_id: str | None,
    template_id: str,
    label: str,
    fiscal_year: str,
    answers: dict[str, Any],
    prior_year_actuals: list[dict[str, Any]] | None,
    num_periods: int,
    llm: LLMRouter,
) -> dict[str, Any]:
    """Shared implementation: create budget from template (VA-P7-03, VA-P8-03 marketplace)."""
    template = get_budget_template(template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {template_id}")
    question_plan = template.get("question_plan", [])
    account_refs = template.get("default_account_refs", ["Revenue", "COGS", "OpEx", "EBITDA"])
    system_text = _build_budget_initialization_prompt(
        template.get("label", ""),
        fiscal_year,
        question_plan,
        answers,
        prior_year_actuals,
        num_periods,
        account_refs,
    )
    messages = [{"role": "user", "content": "Generate initial budget line items with monthly amounts and confidence scores."}]
    try:
        response = await llm.complete_with_routing(
            tenant_id,
            [{"role": "system", "content": system_text}, *messages],
            BUDGET_INITIALIZATION_SCHEMA,
            "budget_initialization",
        )
    except LLMError as e:
        raise HTTPException(
            503 if e.code == "ERR_LLM_ALL_PROVIDERS_FAILED" else 429,
            detail=f"{e.message}: {e.details}" if e.details else e.message,
        ) from e
    content = response.content or {}
    if not isinstance(content, dict):
        logger.warning("llm_response_not_dict", content_type=type(content).__name__, raw_text=response.raw_text[:500])
        content = {}
    line_items_payload = content.get("line_items") or []
    if not isinstance(line_items_payload, list):
        logger.warning("llm_line_items_not_list", payload_type=type(line_items_payload).__name__)
        line_items_payload = []
    budget_id = _budget_id()
    version_id = _version_id()
    async with tenant_conn(tenant_id) as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO budgets (tenant_id, budget_id, label, fiscal_year, status, created_by)
                   VALUES ($1, $2, $3, $4, 'draft', $5)""",
                tenant_id,
                budget_id,
                label,
                fiscal_year,
                user_id or None,
            )
            await ensure_budget_version(
                conn, tenant_id, budget_id, version_id, 1, user_id or None
            )
            fy_str = fiscal_year.replace("FY", "").strip()
            try:
                year = int(fy_str) if len(fy_str) == 4 else 2000 + int(fy_str[-2:]) if len(fy_str) >= 2 else 2026
            except ValueError:
                year = 2026
            for ord in range(1, num_periods + 1):
                month = ((ord - 1) % 12) + 1
                year_offset = (ord - 1) // 12
                period_year = year + year_offset
                _, last_day = calendar.monthrange(period_year, month)
                period_id = _period_id()
                start = date(period_year, month, 1)
                end = date(period_year, month, last_day)
                await conn.execute(
                    """INSERT INTO budget_periods (tenant_id, budget_id, period_id, period_ordinal, period_start, period_end, label)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (tenant_id, budget_id, period_ordinal) DO NOTHING""",
                    tenant_id,
                    budget_id,
                    period_id,
                    ord,
                    start,
                    end,
                    f"P{ord}",
                )
            created_lines: list[dict[str, Any]] = []
            for li in line_items_payload:
                if not isinstance(li, dict):
                    logger.warning("llm_line_item_not_dict", item_type=type(li).__name__, item_value=str(li)[:200])
                    continue
                line_item_id = _line_item_id()
                confidence = li.get("confidence")
                if confidence is not None:
                    try:
                        confidence = max(0.0, min(1.0, float(confidence)))
                    except (TypeError, ValueError):
                        confidence = None
                await conn.execute(
                    """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes, confidence_score, is_revenue)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    tenant_id,
                    line_item_id,
                    budget_id,
                    version_id,
                    li.get("account_ref", ""),
                    li.get("notes"),
                    confidence,
                    bool(li.get("is_revenue", False)),
                )
                amounts_list = li.get("amounts") or []
                if not isinstance(amounts_list, list):
                    amounts_list = []
                for amt in amounts_list:
                    if not isinstance(amt, dict):
                        continue
                    await conn.execute(
                        """INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount)
                           VALUES ($1, $2, $3, $4)
                           ON CONFLICT (tenant_id, line_item_id, period_ordinal) DO UPDATE SET amount = $4""",
                        tenant_id,
                        line_item_id,
                        amt.get("period_ordinal", 0),
                        amt.get("amount", 0),
                    )
                created_lines.append({
                    "line_item_id": line_item_id,
                    "account_ref": li.get("account_ref", ""),
                    "notes": li.get("notes"),
                    "confidence_score": confidence,
                    "is_revenue": bool(li.get("is_revenue", False)),
                    "amounts": li.get("amounts", []),
                })
    return {
        "budget_id": budget_id,
        "label": label,
        "fiscal_year": fiscal_year,
        "status": "draft",
        "current_version_id": version_id,
        "line_items": created_lines,
    }


@router.post("/from-template", status_code=201)
async def create_budget_from_template(
    body: CreateBudgetFromTemplateBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Create a budget from a template; LLM proposes initial line-item amounts with confidence (VA-P7-03)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return await create_budget_from_template_impl(
        tenant_id=x_tenant_id,
        user_id=x_user_id or None,
        template_id=body.template_id,
        label=body.label,
        fiscal_year=body.fiscal_year,
        answers=body.answers,
        prior_year_actuals=body.prior_year_actuals,
        num_periods=body.num_periods,
        llm=llm,
    )
