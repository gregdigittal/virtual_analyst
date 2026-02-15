"""Budget CRUD & department allocation API (VA-P7-02). VA-P7-03/04/05: templates, actuals, variance, reforecast."""

from __future__ import annotations

import calendar
import json
import uuid
from collections import OrderedDict
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.data.budget_catalog import get_budget_template, load_budget_catalog
from apps.api.app.db import tenant_conn
from apps.api.app.db.budgets import (
    BUDGET_STATUSES,
    ensure_budget_version,
    get_budget,
    get_version_line_item_totals,
)
from apps.api.app.deps import get_llm_router
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import LLMError

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _budget_id() -> str:
    return f"bud_{uuid.uuid4().hex[:14]}"


def _version_id() -> str:
    return f"bver_{uuid.uuid4().hex[:14]}"


def _period_id() -> str:
    return f"bper_{uuid.uuid4().hex[:14]}"


def _line_item_id() -> str:
    return f"bli_{uuid.uuid4().hex[:14]}"


def _allocation_id() -> str:
    return f"ball_{uuid.uuid4().hex[:14]}"


# --- Request/response models ---


class CreateBudgetBody(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    fiscal_year: str = Field(..., min_length=1, max_length=32)


class UpdateBudgetBody(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=255)
    fiscal_year: str | None = Field(default=None, min_length=1, max_length=32)
    status: str | None = Field(default=None)


class LineItemAmount(BaseModel):
    period_ordinal: int = Field(..., ge=1)
    amount: float = Field(..., ge=0)


class AddLineItemBody(BaseModel):
    account_ref: str = Field(..., min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=2000)
    amounts: list[LineItemAmount] = Field(default_factory=list)


class UpdateLineItemBody(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    amounts: list[LineItemAmount] | None = Field(default=None)


class DepartmentAllocationItem(BaseModel):
    department_ref: str = Field(..., min_length=1, max_length=255)
    amount_limit: float = Field(..., ge=0)


class SetDepartmentsBody(BaseModel):
    allocations: list[DepartmentAllocationItem] = Field(..., min_length=0)


class CloneBudgetBody(BaseModel):
    label: str = Field(..., min_length=1, max_length=255)
    fiscal_year: str = Field(..., min_length=1, max_length=32)


class PeriodItem(BaseModel):
    period_ordinal: int = Field(..., ge=1)
    period_start: str = Field(..., description="YYYY-MM-DD")
    period_end: str = Field(..., description="YYYY-MM-DD")
    label: str | None = Field(default=None, max_length=64)


# --- Budget CRUD ---


@router.post("", status_code=201)
async def create_budget(
    body: CreateBudgetBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Create a budget (draft) with an initial empty version."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    budget_id = _budget_id()
    version_id = _version_id()
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO budgets (tenant_id, budget_id, label, fiscal_year, status, created_by)
                   VALUES ($1, $2, $3, $4, 'draft', $5)""",
                x_tenant_id,
                budget_id,
                body.label,
                body.fiscal_year,
                x_user_id or None,
            )
            await ensure_budget_version(
                conn, x_tenant_id, budget_id, version_id, 1, x_user_id or None
            )
    return {
        "budget_id": budget_id,
        "label": body.label,
        "fiscal_year": body.fiscal_year,
        "status": "draft",
        "current_version_id": version_id,
    }


@router.get("")
async def list_budgets(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    status: str | None = Query(default=None, description="Filter by status"),
    fiscal_year: str | None = Query(default=None, description="Filter by fiscal year"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    """List budgets with optional filters."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if status is not None and status not in BUDGET_STATUSES:
        raise HTTPException(400, f"Invalid status; must be one of {sorted(BUDGET_STATUSES)}")
    async with tenant_conn(x_tenant_id) as conn:
        conditions = ["tenant_id = $1"]
        args: list[Any] = [x_tenant_id]
        idx = 1
        if status:
            idx += 1
            conditions.append(f"status = ${idx}")
            args.append(status)
        if fiscal_year:
            idx += 1
            conditions.append(f"fiscal_year = ${idx}")
            args.append(fiscal_year)
        idx += 1
        limit_ph = idx
        idx += 1
        offset_ph = idx
        args.extend([limit, offset])
        rows = await conn.fetch(
            f"""SELECT budget_id, label, fiscal_year, status, current_version_id, workflow_instance_id, created_at, updated_at
                FROM budgets WHERE {" AND ".join(conditions)}
                ORDER BY created_at DESC LIMIT ${limit_ph} OFFSET ${offset_ph}""",
            *args,
        )
    return {
        "budgets": [
            {
                "budget_id": r["budget_id"],
                "label": r["label"],
                "fiscal_year": r["fiscal_year"],
                "status": r["status"],
                "current_version_id": r["current_version_id"],
                "workflow_instance_id": r.get("workflow_instance_id"),
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None,
            }
            for r in rows
        ],
        "limit": limit,
        "offset": offset,
    }


# --- VA-P7-03: Budget templates & LLM-assisted seeding ---


@router.get("/templates")
async def list_budget_templates() -> dict[str, Any]:
    """List budget templates (manufacturing, SaaS, services, wholesale)."""
    catalog = load_budget_catalog()
    templates = [
        {"template_id": t["template_id"], "label": t["label"], "industry": t.get("industry", "")}
        for t in catalog.get("templates", [])
    ]
    return {"templates": templates}


class CreateBudgetFromTemplateBody(BaseModel):
    template_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1, max_length=255)
    fiscal_year: str = Field(..., min_length=1, max_length=32)
    answers: dict[str, Any] = Field(default_factory=dict, description="Questionnaire answers")
    prior_year_actuals: list[dict[str, Any]] | None = Field(default=None, description="Optional prior-year actuals for context")
    num_periods: int = Field(default=12, ge=1, le=24)


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
    template = get_budget_template(body.template_id)
    if not template:
        raise HTTPException(404, f"Template not found: {body.template_id}")
    question_plan = template.get("question_plan", [])
    account_refs = template.get("default_account_refs", ["Revenue", "COGS", "OpEx", "EBITDA"])
    system_text = _build_budget_initialization_prompt(
        template.get("label", ""),
        body.fiscal_year,
        question_plan,
        body.answers,
        body.prior_year_actuals,
        body.num_periods,
        account_refs,
    )
    messages = [{"role": "user", "content": "Generate initial budget line items with monthly amounts and confidence scores."}]
    try:
        response = await llm.complete_with_routing(
            x_tenant_id,
            [{"role": "system", "content": system_text}, *messages],
            BUDGET_INITIALIZATION_SCHEMA,
            "budget_initialization",
        )
    except LLMError as e:
        raise HTTPException(
            503 if e.code == "ERR_LLM_ALL_PROVIDERS_FAILED" else 429,
            detail=e.message,
        ) from e
    content = response.content or {}
    line_items_payload = content.get("line_items") or []
    budget_id = _budget_id()
    version_id = _version_id()
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO budgets (tenant_id, budget_id, label, fiscal_year, status, created_by)
                   VALUES ($1, $2, $3, $4, 'draft', $5)""",
                x_tenant_id,
                budget_id,
                body.label,
                body.fiscal_year,
                x_user_id or None,
            )
            await ensure_budget_version(
                conn, x_tenant_id, budget_id, version_id, 1, x_user_id or None
            )
            # Derive year from fiscal_year (e.g. FY2026 -> 2026)
            fy_str = body.fiscal_year.replace("FY", "").strip()
            try:
                year = int(fy_str) if len(fy_str) == 4 else 2000 + int(fy_str[-2:]) if len(fy_str) >= 2 else 2026
            except ValueError:
                year = 2026
            for ord in range(1, body.num_periods + 1):
                month = ((ord - 1) % 12) + 1
                year_offset = (ord - 1) // 12
                period_year = year + year_offset
                _, last_day = calendar.monthrange(period_year, month)
                period_id = _period_id()
                start = f"{period_year}-{month:02d}-01"
                end = f"{period_year}-{month:02d}-{last_day:02d}"
                await conn.execute(
                    """INSERT INTO budget_periods (tenant_id, budget_id, period_id, period_ordinal, period_start, period_end, label)
                       VALUES ($1, $2, $3, $4, $5::date, $6::date, $7)
                       ON CONFLICT (tenant_id, budget_id, period_ordinal) DO NOTHING""",
                    x_tenant_id,
                    budget_id,
                    period_id,
                    ord,
                    start,
                    end,
                    f"P{ord}",
                )
            created_lines: list[dict[str, Any]] = []
            for li in line_items_payload:
                line_item_id = _line_item_id()
                confidence = li.get("confidence")
                if confidence is not None:
                    confidence = max(0.0, min(1.0, float(confidence)))
                await conn.execute(
                    """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes, confidence_score)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    x_tenant_id,
                    line_item_id,
                    budget_id,
                    version_id,
                    li.get("account_ref", ""),
                    li.get("notes"),
                    confidence,
                )
                for amt in li.get("amounts") or []:
                    await conn.execute(
                        """INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount)
                           VALUES ($1, $2, $3, $4)
                           ON CONFLICT (tenant_id, line_item_id, period_ordinal) DO UPDATE SET amount = $4""",
                        x_tenant_id,
                        line_item_id,
                        amt.get("period_ordinal", 0),
                        amt.get("amount", 0),
                    )
                created_lines.append({
                    "line_item_id": line_item_id,
                    "account_ref": li.get("account_ref", ""),
                    "notes": li.get("notes"),
                    "confidence_score": confidence,
                    "amounts": li.get("amounts", []),
                })
    return {
        "budget_id": budget_id,
        "label": body.label,
        "fiscal_year": body.fiscal_year,
        "status": "draft",
        "current_version_id": version_id,
        "line_items": created_lines,
    }


@router.get("/dashboard")
async def get_budget_dashboard(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    budget_id: str | None = None,
) -> dict[str, Any]:
    """Budget KPI dashboard (VA-P7-11): burn rate, runway, utilisation %, variance trend, department ranking. CFO view when budget_id omitted."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if budget_id:
            budget_ids = [budget_id]
            rows = await conn.fetch(
                "SELECT budget_id, label, status, current_version_id FROM budgets WHERE tenant_id = $1 AND budget_id = $2",
                x_tenant_id,
                budget_id,
            )
            if not rows:
                raise HTTPException(404, "Budget not found")
        else:
            rows = await conn.fetch(
                "SELECT budget_id, label, status, current_version_id FROM budgets WHERE tenant_id = $1 ORDER BY created_at DESC",
                x_tenant_id,
            )
            budget_ids = [r["budget_id"] for r in rows]
        widgets: list[dict[str, Any]] = []
        for b in rows:
            vid = b["current_version_id"]
            bid = b["budget_id"]
            if not vid:
                widgets.append({
                    "budget_id": bid,
                    "label": b["label"],
                    "burn_rate": None,
                    "runway_months": None,
                    "utilisation_pct": None,
                    "variance_trend": [],
                    "department_ranking": [],
                    "alerts": [],
                })
                continue
            total_budget = await conn.fetchval(
                """SELECT COALESCE(SUM(blia.amount), 0) FROM budget_line_items bli
                   JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
                   WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3""",
                x_tenant_id,
                bid,
                vid,
            )
            total_budget = float(total_budget or 0)
            actual_rows = await conn.fetch(
                """SELECT period_ordinal, COALESCE(SUM(amount), 0) AS total FROM budget_actuals
                   WHERE tenant_id = $1 AND budget_id = $2 GROUP BY period_ordinal ORDER BY period_ordinal""",
                x_tenant_id,
                bid,
            )
            total_actual = sum(float(r["total"]) for r in actual_rows)
            utilisation_pct = round((total_actual / total_budget * 100.0), 2) if total_budget else None
            period_totals_budget = await conn.fetch(
                """SELECT blia.period_ordinal, SUM(blia.amount) AS total FROM budget_line_items bli
                   JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
                   WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3 GROUP BY blia.period_ordinal ORDER BY blia.period_ordinal""",
                x_tenant_id,
                bid,
                vid,
            )
            budget_by_period = {r["period_ordinal"]: float(r["total"]) for r in period_totals_budget}
            actual_by_period = {r["period_ordinal"]: float(r["total"]) for r in actual_rows}
            variance_trend = []
            for per in sorted(set(budget_by_period.keys()) | set(actual_by_period.keys())):
                bval = budget_by_period.get(per, 0)
                aval = actual_by_period.get(per, 0)
                var_pct = (aval - bval) / bval * 100.0 if bval else (100.0 if aval else 0.0)
                variance_trend.append({"period_ordinal": per, "budget_total": bval, "actual_total": aval, "variance_pct": round(var_pct, 2)})
            dept_rows = await conn.fetch(
                """SELECT department_ref, SUM(amount) AS total FROM budget_actuals
                   WHERE tenant_id = $1 AND budget_id = $2 GROUP BY department_ref ORDER BY total DESC""",
                x_tenant_id,
                bid,
            )
            department_ranking = [{"department_ref": r["department_ref"] or "(none)", "actual_total": float(r["total"])} for r in dept_rows]
            n_actual_periods = len(actual_by_period) or 0
            burn_rate = (total_actual / n_actual_periods) if n_actual_periods > 0 else None
            runway_months = (total_budget - total_actual) / (burn_rate or 1) if (total_budget and burn_rate and total_actual < total_budget) else None
            alerts: list[dict[str, Any]] = []
            if utilisation_pct is not None and utilisation_pct >= 90:
                alerts.append({"type": "utilisation", "message": f"Budget utilisation at {utilisation_pct}%", "threshold_pct": 90})
            for v in variance_trend:
                if v["variance_pct"] and v["variance_pct"] < -10:
                    alerts.append({"type": "unfavourable_variance", "period_ordinal": v["period_ordinal"], "message": f"Variance {v['variance_pct']}% in period {v['period_ordinal']}", "threshold_pct": 10})
            widgets.append({
                "budget_id": bid,
                "label": b["label"],
                "burn_rate": round(burn_rate, 2) if burn_rate is not None else None,
                "runway_months": round(runway_months, 1) if runway_months is not None else None,
                "utilisation_pct": utilisation_pct,
                "variance_trend": variance_trend,
                "department_ranking": department_ranking,
                "alerts": alerts,
            })
    return {"widgets": widgets, "cfo_view": not budget_id}


@router.get("/{budget_id}")
async def get_budget_by_id(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get a single budget by id."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
    if not row:
        raise HTTPException(404, "Budget not found")
    return {
        "budget_id": row["budget_id"],
        "label": row["label"],
        "fiscal_year": row["fiscal_year"],
        "status": row["status"],
        "current_version_id": row["current_version_id"],
        "workflow_instance_id": row.get("workflow_instance_id"),
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        "created_by": row["created_by"],
    }


BUDGET_APPROVAL_TEMPLATE_ID = "tpl_budget_approval"


@router.post("/{budget_id}/submit", status_code=200)
async def submit_budget(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Submit budget for approval (VA-P7-06). Creates workflow instance and sets status to submitted."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        if row["status"] != "draft":
            raise HTTPException(400, "Only draft budgets can be submitted for approval")
        if row.get("workflow_instance_id"):
            raise HTTPException(400, "Budget already submitted (workflow exists)")
        instance_id = f"wf_{uuid.uuid4().hex[:14]}"
        try:
            async with conn.transaction():
                await conn.execute(
                    """INSERT INTO workflow_instances
                       (tenant_id, instance_id, template_id, entity_type, entity_id, current_stage_index, status, created_by)
                       VALUES ($1, $2, $3, 'budget', $4, 0, 'pending', $5)""",
                    x_tenant_id,
                    instance_id,
                    BUDGET_APPROVAL_TEMPLATE_ID,
                    budget_id,
                    x_user_id or None,
                )
                await conn.execute(
                    """UPDATE budgets SET status = 'submitted', workflow_instance_id = $1, updated_at = now()
                       WHERE tenant_id = $2 AND budget_id = $3""",
                    instance_id,
                    x_tenant_id,
                    budget_id,
                )
                row = await get_budget(conn, x_tenant_id, budget_id)
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(
                500,
                "Budget approval workflow template not found; run migration 0032",
            )
    return {
        "budget_id": row["budget_id"],
        "status": row["status"],
        "workflow_instance_id": row.get("workflow_instance_id"),
    }


@router.patch("/{budget_id}")
async def update_budget(
    budget_id: str,
    body: UpdateBudgetBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update budget metadata (label, fiscal_year, status)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    if body.status is not None and body.status not in BUDGET_STATUSES:
        raise HTTPException(400, f"Invalid status; must be one of {sorted(BUDGET_STATUSES)}")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        updates: list[str] = []
        args: list[Any] = []
        n = 0
        if body.label is not None:
            n += 1
            updates.append(f"label = ${n}")
            args.append(body.label)
        if body.fiscal_year is not None:
            n += 1
            updates.append(f"fiscal_year = ${n}")
            args.append(body.fiscal_year)
        if body.status is not None:
            n += 1
            updates.append(f"status = ${n}")
            args.append(body.status)
        if not updates:
            return {
                "budget_id": row["budget_id"],
                "label": row["label"],
                "fiscal_year": row["fiscal_year"],
                "status": row["status"],
                "current_version_id": row["current_version_id"],
                "workflow_instance_id": row.get("workflow_instance_id"),
            }
        updates.append("updated_at = now()")
        n += 1
        args.append(x_tenant_id)
        n += 1
        args.append(budget_id)
        await conn.execute(
            f"UPDATE budgets SET {', '.join(updates)} WHERE tenant_id = ${n - 1} AND budget_id = ${n}",
            *args,
        )
        row = await get_budget(conn, x_tenant_id, budget_id)
    return {
        "budget_id": row["budget_id"],
        "label": row["label"],
        "fiscal_year": row["fiscal_year"],
        "status": row["status"],
        "current_version_id": row["current_version_id"],
        "workflow_instance_id": row.get("workflow_instance_id"),
    }


# --- Budget periods ---


@router.get("/{budget_id}/periods")
async def list_budget_periods(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List periods for the budget (e.g. monthly buckets)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        rows = await conn.fetch(
            """SELECT period_id, period_ordinal, period_start, period_end, label
               FROM budget_periods WHERE tenant_id = $1 AND budget_id = $2 ORDER BY period_ordinal""",
            x_tenant_id,
            budget_id,
        )
    return {
        "periods": [
            {
                "period_id": r["period_id"],
                "period_ordinal": r["period_ordinal"],
                "period_start": r["period_start"].isoformat() if r["period_start"] else None,
                "period_end": r["period_end"].isoformat() if r["period_end"] else None,
                "label": r["label"],
            }
            for r in rows
        ],
    }


class AddPeriodsBody(BaseModel):
    periods: list[PeriodItem] = Field(..., min_length=1)


# --- VA-P7-03: LLM response schemas ---
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
                "required": ["account_ref", "amounts"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["line_items"],
    "additionalProperties": False,
}

BUDGET_REFORECAST_SCHEMA = {
    "type": "object",
    "properties": {
        "revisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "account_ref": {"type": "string"},
                    "amounts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"period_ordinal": {"type": "integer"}, "amount": {"type": "number"}},
                            "required": ["period_ordinal", "amount"],
                            "additionalProperties": False,
                        },
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "variance_note": {"type": "string"},
                },
                "required": ["account_ref", "amounts"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["revisions"],
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


@router.post("/{budget_id}/periods", status_code=201)
async def add_budget_periods(
    budget_id: str,
    body: AddPeriodsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Add one or more periods (e.g. monthly buckets)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    added: list[dict[str, Any]] = []
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await get_budget(conn, x_tenant_id, budget_id)
            if not row:
                raise HTTPException(404, "Budget not found")
            for item in body.periods:
                period_id = _period_id()
                await conn.execute(
                    """INSERT INTO budget_periods (tenant_id, budget_id, period_id, period_ordinal, period_start, period_end, label)
                       VALUES ($1, $2, $3, $4, $5::date, $6::date, $7)
                       ON CONFLICT (tenant_id, budget_id, period_ordinal) DO UPDATE SET period_start = $5::date, period_end = $6::date, label = $7""",
                    x_tenant_id,
                    budget_id,
                    period_id,
                    item.period_ordinal,
                    item.period_start,
                    item.period_end,
                    item.label,
                )
                added.append({
                    "period_id": period_id,
                    "period_ordinal": item.period_ordinal,
                    "period_start": item.period_start,
                    "period_end": item.period_end,
                    "label": item.label,
                })
    return {"periods": added}


# --- Line items (operate on current version) ---


@router.get("/{budget_id}/line-items")
async def list_line_items(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List line items for the budget's current version."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
        rows = await conn.fetch(
            """SELECT bli.line_item_id, bli.account_ref, bli.notes, bli.confidence_score,
                      blia.period_ordinal, blia.amount
               FROM budget_line_items bli
               LEFT JOIN budget_line_item_amounts blia
                 ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
               WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3
               ORDER BY bli.account_ref, blia.period_ordinal""",
            x_tenant_id,
            budget_id,
            version_id,
        )
        grouped: OrderedDict[str, dict[str, Any]] = OrderedDict()
        for r in rows:
            lid = r["line_item_id"]
            if lid not in grouped:
                grouped[lid] = {
                    "line_item_id": lid,
                    "account_ref": r["account_ref"],
                    "notes": r["notes"],
                    "confidence_score": float(r["confidence_score"]) if r.get("confidence_score") is not None else None,
                    "amounts": [],
                }
            if r["period_ordinal"] is not None:
                grouped[lid]["amounts"].append({
                    "period_ordinal": r["period_ordinal"],
                    "amount": float(r["amount"]),
                })
    return {"line_items": list(grouped.values())}


async def _resolve_current_version(
    conn: asyncpg.Connection, tenant_id: str, budget_id: str
) -> tuple[str, str]:
    """Return (budget_id, version_id) for current version; 404 if no version."""
    row = await get_budget(conn, tenant_id, budget_id)
    if not row:
        raise HTTPException(404, "Budget not found")
    vid = row.get("current_version_id")
    if not vid:
        raise HTTPException(409, "Budget has no version; create one first")
    return budget_id, vid


@router.post("/{budget_id}/line-items", status_code=201)
async def add_line_item(
    budget_id: str,
    body: AddLineItemBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Add a line item to the budget's current version (account_ref, notes, monthly amounts)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    line_item_id = _line_item_id()
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
            await conn.execute(
                """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                x_tenant_id,
                line_item_id,
                budget_id,
                version_id,
                body.account_ref,
                body.notes,
            )
            for a in body.amounts:
                await conn.execute(
                    """INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (tenant_id, line_item_id, period_ordinal) DO UPDATE SET amount = $4""",
                    x_tenant_id,
                    line_item_id,
                    a.period_ordinal,
                    a.amount,
                )
    return {
        "line_item_id": line_item_id,
        "account_ref": body.account_ref,
        "notes": body.notes,
        "amounts": [{"period_ordinal": a.period_ordinal, "amount": a.amount} for a in body.amounts],
    }


@router.patch("/{budget_id}/line-items/{line_item_id}")
async def update_line_item(
    budget_id: str,
    line_item_id: str,
    body: UpdateLineItemBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Update a line item (notes and/or amounts)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
        row = await conn.fetchrow(
            """SELECT line_item_id, account_ref, notes FROM budget_line_items
               WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3 AND line_item_id = $4""",
            x_tenant_id,
            budget_id,
            version_id,
            line_item_id,
        )
        if not row:
            raise HTTPException(404, "Line item not found")
        if body.notes is not None:
            await conn.execute(
                "UPDATE budget_line_items SET notes = $1 WHERE tenant_id = $2 AND line_item_id = $3",
                body.notes,
                x_tenant_id,
                line_item_id,
            )
        if body.amounts is not None:
            for a in body.amounts:
                await conn.execute(
                    """INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (tenant_id, line_item_id, period_ordinal) DO UPDATE SET amount = $4""",
                    x_tenant_id,
                    line_item_id,
                    a.period_ordinal,
                    a.amount,
                )
        row = await conn.fetchrow(
            "SELECT account_ref, notes FROM budget_line_items WHERE tenant_id = $1 AND line_item_id = $2",
            x_tenant_id,
            line_item_id,
        )
        amounts_rows = await conn.fetch(
            "SELECT period_ordinal, amount FROM budget_line_item_amounts WHERE tenant_id = $1 AND line_item_id = $2",
            x_tenant_id,
            line_item_id,
        )
    return {
        "line_item_id": line_item_id,
        "account_ref": row["account_ref"],
        "notes": row["notes"],
        "amounts": [{"period_ordinal": r["period_ordinal"], "amount": float(r["amount"])} for r in amounts_rows],
    }


@router.delete("/{budget_id}/line-items/{line_item_id}", status_code=204)
async def remove_line_item(
    budget_id: str,
    line_item_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> None:
    """Remove a line item from the current version."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
        res = await conn.execute(
            """DELETE FROM budget_line_items
               WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3 AND line_item_id = $4""",
            x_tenant_id,
            budget_id,
            version_id,
            line_item_id,
        )
    if res == "DELETE 0":
        raise HTTPException(404, "Line item not found")


# --- Department allocations ---


@router.get("/{budget_id}/departments")
async def list_department_allocations(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List department allocations for the budget's current version."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
        rows = await conn.fetch(
            """SELECT allocation_id, department_ref, amount_limit FROM budget_department_allocations
               WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3 ORDER BY department_ref""",
            x_tenant_id,
            budget_id,
            version_id,
        )
    return {
        "allocations": [
            {"allocation_id": r["allocation_id"], "department_ref": r["department_ref"], "amount_limit": float(r["amount_limit"])}
            for r in rows
        ],
    }


@router.post("/{budget_id}/departments", status_code=200)
async def set_department_allocations(
    budget_id: str,
    body: SetDepartmentsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Set department allocations for the current version. Sum of amount_limit is checked against total line-item totals (optional; can allow <= total)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
            totals = await get_version_line_item_totals(conn, x_tenant_id, budget_id, version_id)
            total_budget = sum(totals.values())
            sum_allocations = sum(a.amount_limit for a in body.allocations)
            if total_budget > 0 and sum_allocations > total_budget:
                raise HTTPException(
                    400,
                    f"Sum of department allocations ({sum_allocations}) exceeds total budget ({total_budget})",
                )
            await conn.execute(
                """DELETE FROM budget_department_allocations
                   WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3""",
                x_tenant_id,
                budget_id,
                version_id,
            )
            for a in body.allocations:
                aid = _allocation_id()
                await conn.execute(
                    """INSERT INTO budget_department_allocations (tenant_id, allocation_id, budget_id, version_id, department_ref, amount_limit)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    x_tenant_id,
                    aid,
                    budget_id,
                    version_id,
                    a.department_ref,
                    a.amount_limit,
                )
    return {
        "allocations": [
            {"department_ref": a.department_ref, "amount_limit": a.amount_limit}
            for a in body.allocations
        ],
    }


# --- Clone ---


@router.post("/{budget_id}/clone", status_code=201)
async def clone_budget(
    budget_id: str,
    body: CloneBudgetBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
) -> dict[str, Any]:
    """Clone a budget: new budget with new first version, copying line items and amounts and department allocations from current version."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    new_budget_id = _budget_id()
    new_version_id = _version_id()
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            _, version_id = await _resolve_current_version(conn, x_tenant_id, budget_id)
            await conn.execute(
                """INSERT INTO budgets (tenant_id, budget_id, label, fiscal_year, status, created_by)
                   VALUES ($1, $2, $3, $4, 'draft', $5)""",
                x_tenant_id,
                new_budget_id,
                body.label,
                body.fiscal_year,
                x_user_id or None,
            )
            await ensure_budget_version(
                conn, x_tenant_id, new_budget_id, new_version_id, 1, x_user_id or None
            )
            # Copy budget_periods from source to clone (R8-02)
            period_rows = await conn.fetch(
                """SELECT period_ordinal, period_start, period_end, label
                   FROM budget_periods WHERE tenant_id = $1 AND budget_id = $2
                   ORDER BY period_ordinal""",
                x_tenant_id,
                budget_id,
            )
            for pr in period_rows:
                await conn.execute(
                    """INSERT INTO budget_periods (tenant_id, budget_id, period_id, period_ordinal, period_start, period_end, label)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (tenant_id, budget_id, period_ordinal) DO NOTHING""",
                    x_tenant_id,
                    new_budget_id,
                    _period_id(),
                    pr["period_ordinal"],
                    pr["period_start"],
                    pr["period_end"],
                    pr["label"],
                )
            rows = await conn.fetch(
                """SELECT line_item_id, account_ref, notes FROM budget_line_items
                   WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3""",
                x_tenant_id,
                budget_id,
                version_id,
            )
            all_amounts = await conn.fetch(
                """SELECT bli.line_item_id, blia.period_ordinal, blia.amount
                   FROM budget_line_items bli
                   JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
                   WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3""",
                x_tenant_id,
                budget_id,
                version_id,
            )
            amounts_by_item: dict[str, list[tuple[int, float]]] = {}
            for ar in all_amounts:
                amounts_by_item.setdefault(ar["line_item_id"], []).append(
                    (ar["period_ordinal"], float(ar["amount"]))
                )
            for r in rows:
                new_li_id = _line_item_id()
                await conn.execute(
                    """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    x_tenant_id,
                    new_li_id,
                    new_budget_id,
                    new_version_id,
                    r["account_ref"],
                    r["notes"],
                )
                for period_ordinal, amount in amounts_by_item.get(r["line_item_id"], []):
                    await conn.execute(
                        """INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount)
                           VALUES ($1, $2, $3, $4)""",
                        x_tenant_id,
                        new_li_id,
                        period_ordinal,
                        amount,
                    )
            alloc_rows = await conn.fetch(
                """SELECT department_ref, amount_limit FROM budget_department_allocations
                   WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3""",
                x_tenant_id,
                budget_id,
                version_id,
            )
            for ar in alloc_rows:
                await conn.execute(
                    """INSERT INTO budget_department_allocations (tenant_id, allocation_id, budget_id, version_id, department_ref, amount_limit)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    x_tenant_id,
                    _allocation_id(),
                    new_budget_id,
                    new_version_id,
                    ar["department_ref"],
                    ar["amount_limit"],
                )
    return {
        "budget_id": new_budget_id,
        "label": body.label,
        "fiscal_year": body.fiscal_year,
        "status": "draft",
        "current_version_id": new_version_id,
    }


# --- VA-P7-04: Actuals import & variance ---


class ActualItem(BaseModel):
    period_ordinal: int = Field(..., ge=1)
    account_ref: str = Field(..., min_length=1)
    amount: float = Field(...)
    department_ref: str = Field(default="", max_length=255)


class ImportActualsBody(BaseModel):
    actuals: list[ActualItem] = Field(..., min_length=1)
    source: str = Field(default="csv", pattern="^(csv|erp)$")


@router.post("/{budget_id}/actuals/import", status_code=200)
async def import_actuals(
    budget_id: str,
    body: ImportActualsBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Import actuals (CSV or ERP source) for variance analysis (VA-P7-04)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        for a in body.actuals:
            await conn.execute(
                """INSERT INTO budget_actuals (tenant_id, budget_id, period_ordinal, account_ref, amount, department_ref, source)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (tenant_id, budget_id, period_ordinal, account_ref, department_ref) DO UPDATE SET amount = $5, source = $7""",
                x_tenant_id,
                budget_id,
                a.period_ordinal,
                a.account_ref,
                a.amount,
                a.department_ref or "",
                body.source,
            )
    return {"imported": len(body.actuals), "source": body.source}


@router.get("/{budget_id}/variance")
async def get_budget_variance(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    period: int | None = Query(default=None, description="Filter by period_ordinal"),
    department: str | None = Query(default=None, description="Filter by department_ref"),
    materiality_pct: float = Query(default=5.0, ge=0, le=100, description="Materiality threshold % for classification"),
) -> dict[str, Any]:
    """Variance analysis: budget vs actual (absolute, %, favourable/unfavourable). VA-P7-04."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        row = await get_budget(conn, x_tenant_id, budget_id)
        if not row:
            raise HTTPException(404, "Budget not found")
        vid = row.get("current_version_id")
        if not vid:
            raise HTTPException(409, "Budget has no current version")
        # Fetch budget amounts per (line_item, period)
        budget_rows = await conn.fetch(
            """SELECT bli.account_ref, blia.period_ordinal, blia.amount AS budget_amount
               FROM budget_line_items bli
               JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
               WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3""",
            x_tenant_id,
            budget_id,
            vid,
        )
        if department:
            actual_rows = await conn.fetch(
                """SELECT period_ordinal, account_ref, SUM(amount) AS actual_amount
                   FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2 AND department_ref = $3
                   GROUP BY period_ordinal, account_ref""",
                x_tenant_id,
                budget_id,
                department,
            )
        else:
            actual_rows = await conn.fetch(
                """SELECT period_ordinal, account_ref, SUM(amount) AS actual_amount
                   FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2
                   GROUP BY period_ordinal, account_ref""",
                x_tenant_id,
                budget_id,
            )
        budget_by_key: dict[tuple[str, int], float] = {}
        for r in budget_rows:
            key = (r["account_ref"], r["period_ordinal"])
            budget_by_key[key] = float(r["budget_amount"])
        actual_by_key: dict[tuple[str, int], float] = {}
        for r in actual_rows:
            key = (r["account_ref"], r["period_ordinal"])
            actual_by_key[key] = float(r["actual_amount"])
        all_keys = sorted(set(budget_by_key.keys()) | set(actual_by_key.keys()))
        variances: list[dict[str, Any]] = []
        for (acc, per) in all_keys:
            if period is not None and per != period:
                continue
            bud = budget_by_key.get((acc, per), 0.0)
            act = actual_by_key.get((acc, per), 0.0)
            var_abs = act - bud
            var_pct = (var_abs / bud * 100.0) if bud != 0 else (100.0 if var_abs != 0 else 0.0)
            is_material = abs(var_pct) >= materiality_pct
            # Heuristic: accounts starting with revenue/income/subscription treat positive variance as favourable.
            # All other accounts treat negative variance (under budget) as favourable.
            # TODO(VA-P7): add explicit is_revenue flag to budget_line_items for accuracy.
            is_revenue_line = acc.lower().startswith(("revenue", "income", "subscription", "fee", "gain"))
            favourable = (var_abs > 0 and is_revenue_line) or (var_abs < 0 and not is_revenue_line)
            variances.append({
                "account_ref": acc,
                "period_ordinal": per,
                "budget_amount": bud,
                "actual_amount": act,
                "variance_absolute": round(var_abs, 2),
                "variance_percent": round(var_pct, 2),
                "favourable": favourable,
                "material": is_material,
            })
    return {"variances": variances, "materiality_pct": materiality_pct}


# --- VA-P7-05: Rolling forecast ---


@router.post("/{budget_id}/reforecast", status_code=201)
async def reforecast_budget(
    budget_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    x_user_id: str = Header("", alias="X-User-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Create new version with actuals locked and remaining periods re-projected by LLM (VA-P7-05)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        async with conn.transaction():
            row = await get_budget(conn, x_tenant_id, budget_id)
            if not row:
                raise HTTPException(404, "Budget not found")
            cur_vid = row.get("current_version_id")
            if not cur_vid:
                raise HTTPException(409, "Budget has no current version")
            # Periods that have actuals
            actual_periods = await conn.fetch(
                "SELECT DISTINCT period_ordinal FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2 ORDER BY period_ordinal",
                x_tenant_id,
                budget_id,
            )
            periods_with_actuals = {r["period_ordinal"] for r in actual_periods}
            # Current line items and amounts
            line_rows = await conn.fetch(
                """SELECT line_item_id, account_ref, notes FROM budget_line_items
                   WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3""",
                x_tenant_id,
                budget_id,
                cur_vid,
            )
            version_number = await conn.fetchval(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM budget_versions WHERE tenant_id = $1 AND budget_id = $2",
                x_tenant_id,
                budget_id,
            )
            new_version_id = _version_id()
            await ensure_budget_version(
                conn, x_tenant_id, budget_id, new_version_id, version_number, x_user_id or None
            )
            # Pre-fetch ALL amounts for current version in one query
            all_amounts = await conn.fetch(
                """SELECT bli.line_item_id, bli.account_ref, blia.period_ordinal, blia.amount
                   FROM budget_line_items bli
                   JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
                   WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3""",
                x_tenant_id,
                budget_id,
                cur_vid,
            )
            amounts_by_item: dict[str, list[dict[str, Any]]] = {}
            for r in all_amounts:
                amounts_by_item.setdefault(r["line_item_id"], []).append(
                    {"period_ordinal": r["period_ordinal"], "amount": float(r["amount"])}
                )
            # Pre-fetch ALL actuals in one query (summed by period + account)
            all_actuals = await conn.fetch(
                """SELECT period_ordinal, account_ref, SUM(amount) AS total
                   FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2
                   GROUP BY period_ordinal, account_ref""",
                x_tenant_id,
                budget_id,
            )
            actuals_map: dict[tuple[int, str], float] = {}
            for r in all_actuals:
                actuals_map[(r["period_ordinal"], r["account_ref"])] = float(r["total"])
            # Build context for LLM: YTD actuals + original amounts for remaining periods
            ytd_actuals = [
                {"period_ordinal": r["period_ordinal"], "account_ref": r["account_ref"], "amount": float(r["total"])}
                for r in all_actuals
            ]
            remaining_by_account: dict[str, list[dict[str, Any]]] = {}
            for lid, amts in amounts_by_item.items():
                account_ref = next((li["account_ref"] for li in line_rows if li["line_item_id"] == lid), None)
                if account_ref is not None:
                    remaining_by_account[account_ref] = [
                        a for a in amts
                        if a["period_ordinal"] not in periods_with_actuals
                    ]
            prompt = (
                "You are a financial analyst. Given YTD actuals and original budget amounts for remaining periods, "
                "propose revised forecast amounts for remaining periods only. Output JSON with 'revisions' array: "
                "each item has account_ref, amounts (array of {period_ordinal, amount}), optional confidence (0-1), optional variance_note. "
                "Do not fabricate; base revisions on the data provided.\n\nYTD actuals:\n"
                + json.dumps(ytd_actuals[:50], indent=2)
                + "\n\nRemaining periods by account (original):\n"
                + json.dumps(remaining_by_account, indent=2)
            )
            messages = [{"role": "user", "content": prompt}]
            try:
                response = await llm.complete_with_routing(
                    x_tenant_id,
                    [{"role": "system", "content": "Output only valid JSON matching the required schema."}, *messages],
                    BUDGET_REFORECAST_SCHEMA,
                    "budget_reforecast",
                )
            except LLMError as e:
                raise HTTPException(
                    503 if e.code == "ERR_LLM_ALL_PROVIDERS_FAILED" else 429,
                    detail=e.message,
                ) from e
            content = response.content or {}
            revisions = content.get("revisions") or []
            for li in line_rows:
                new_li_id = _line_item_id()
                account_ref = li["account_ref"]
                rev = next((r for r in revisions if r.get("account_ref") == account_ref), None)
                await conn.execute(
                    """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes, confidence_score)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    x_tenant_id,
                    new_li_id,
                    budget_id,
                    new_version_id,
                    account_ref,
                    li["notes"],
                    (rev.get("confidence") if rev else None),
                )
                # Periods with actuals: use summed actual from pre-fetched actuals_map
                for ap in actual_periods:
                    per = ap["period_ordinal"]
                    amt = actuals_map.get((per, account_ref), 0.0)
                    await conn.execute(
                        "INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount) VALUES ($1, $2, $3, $4)",
                        x_tenant_id,
                        new_li_id,
                        per,
                        amt,
                    )
                # Remaining periods: use LLM revision or keep original from pre-fetched amounts_by_item
                rev_amounts = {a["period_ordinal"]: a["amount"] for a in (rev.get("amounts") or [])} if rev else {}
                orig_amounts = amounts_by_item.get(li["line_item_id"], [])
                for r in orig_amounts:
                    if r["period_ordinal"] in periods_with_actuals:
                        continue
                    amt = rev_amounts.get(r["period_ordinal"], r["amount"])
                    await conn.execute(
                        "INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount) VALUES ($1, $2, $3, $4)",
                        x_tenant_id,
                        new_li_id,
                        r["period_ordinal"],
                        amt,
                    )
    return {
        "budget_id": budget_id,
        "current_version_id": new_version_id,
        "version_number": version_number,
    }
