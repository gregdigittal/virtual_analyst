"""Budget dashboard, NL query, actuals import, variance analysis, and reforecast (VA-P7-04/05, VA-P8-10)."""

from __future__ import annotations

import json
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from apps.api.app.core.settings import get_settings
from apps.api.app.deps import get_agent_service, get_llm_router, require_role, ROLES_CAN_WRITE
from apps.api.app.routers.budgets._common import (
    ActualItem,
    ImportActualsBody,
    NLQueryBody,
    _line_item_id,
    _version_id,
    ensure_budget_version,
    get_budget,
    logger,
    tenant_conn,
)
from apps.api.app.services.agent.budget_agent import run_budget_nl_query_agent
from apps.api.app.services.agent.reforecast_agent import run_reforecast_agent
from apps.api.app.services.llm.router import LLMRouter
from shared.fm_shared.errors import LLMError

router = APIRouter(tags=["budgets"], dependencies=[require_role(*ROLES_CAN_WRITE)])


# --- LLM response schema for reforecast ---
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
                "required": ["account_ref", "amounts", "confidence", "variance_note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["revisions"],
    "additionalProperties": False,
}

NL_QUERY_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string", "description": "Factual answer based only on the provided budget data; say if not determinable"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "e.g. dashboard, budget_variance"},
                    "budget_id": {"type": "string"},
                    "detail": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
    },
    "required": ["answer"],
    "additionalProperties": False,
}


@router.get("/dashboard")
async def get_budget_dashboard(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    budget_id: str | None = None,
) -> dict[str, Any]:
    """Budget KPI dashboard (VA-P7-11): burn rate, runway, utilisation %, variance trend, department ranking."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if budget_id:
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
        # Collect budget_id/version_id pairs for batch queries (eliminates N+1)
        valid_bids: list[str] = []
        valid_vids: list[str] = []
        for b in rows:
            if b["current_version_id"]:
                valid_bids.append(b["budget_id"])
                valid_vids.append(b["current_version_id"])

        total_budget_map: dict[str, float] = {}
        actuals_by_bid: dict[str, list[dict[str, Any]]] = {}
        period_budget_by_bid: dict[str, dict[int, float]] = {}
        dept_by_bid: dict[str, list[dict[str, Any]]] = {}

        if valid_bids:
            # Q1: total budget per budget_id (version paired via CTE)
            total_rows_q = await conn.fetch(
                """WITH bv AS (
                     SELECT unnest($2::text[]) AS budget_id, unnest($3::text[]) AS version_id
                   )
                   SELECT bli.budget_id, COALESCE(SUM(blia.amount), 0) AS total
                   FROM bv
                   JOIN budget_line_items bli ON bli.budget_id = bv.budget_id AND bli.version_id = bv.version_id AND bli.tenant_id = $1
                   JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
                   GROUP BY bli.budget_id""",
                x_tenant_id, valid_bids, valid_vids,
            )
            for r in total_rows_q:
                total_budget_map[r["budget_id"]] = float(r["total"])

            # Q2: actuals by period per budget_id
            actual_rows_q = await conn.fetch(
                """SELECT budget_id, period_ordinal, COALESCE(SUM(amount), 0) AS total
                   FROM budget_actuals
                   WHERE tenant_id = $1 AND budget_id = ANY($2::text[])
                   GROUP BY budget_id, period_ordinal
                   ORDER BY budget_id, period_ordinal""",
                x_tenant_id, valid_bids,
            )
            for r in actual_rows_q:
                actuals_by_bid.setdefault(r["budget_id"], []).append(
                    {"period_ordinal": r["period_ordinal"], "total": float(r["total"])}
                )

            # Q3: budget amounts by period per budget_id (version paired via CTE)
            period_budget_q = await conn.fetch(
                """WITH bv AS (
                     SELECT unnest($2::text[]) AS budget_id, unnest($3::text[]) AS version_id
                   )
                   SELECT bli.budget_id, blia.period_ordinal, SUM(blia.amount) AS total
                   FROM bv
                   JOIN budget_line_items bli ON bli.budget_id = bv.budget_id AND bli.version_id = bv.version_id AND bli.tenant_id = $1
                   JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
                   GROUP BY bli.budget_id, blia.period_ordinal
                   ORDER BY bli.budget_id, blia.period_ordinal""",
                x_tenant_id, valid_bids, valid_vids,
            )
            for r in period_budget_q:
                period_budget_by_bid.setdefault(r["budget_id"], {})[r["period_ordinal"]] = float(r["total"])

            # Q4: department ranking per budget_id
            dept_rows_q = await conn.fetch(
                """SELECT budget_id, department_ref, SUM(amount) AS total
                   FROM budget_actuals
                   WHERE tenant_id = $1 AND budget_id = ANY($2::text[])
                   GROUP BY budget_id, department_ref
                   ORDER BY budget_id, total DESC""",
                x_tenant_id, valid_bids,
            )
            for r in dept_rows_q:
                dept_by_bid.setdefault(r["budget_id"], []).append(
                    {"department_ref": r["department_ref"] or "(none)", "actual_total": float(r["total"])}
                )

        # Build widgets from pre-fetched data
        widgets: list[dict[str, Any]] = []
        for b in rows:
            bid = b["budget_id"]
            if not b["current_version_id"]:
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
            total_budget = total_budget_map.get(bid, 0.0)
            actual_periods = actuals_by_bid.get(bid, [])
            actual_by_period = {r["period_ordinal"]: r["total"] for r in actual_periods}
            total_actual = sum(actual_by_period.values())
            utilisation_pct = round((total_actual / total_budget * 100.0), 2) if total_budget else None
            budget_by_period = period_budget_by_bid.get(bid, {})
            variance_trend = []
            for per in sorted(set(budget_by_period.keys()) | set(actual_by_period.keys())):
                bval = budget_by_period.get(per, 0)
                aval = actual_by_period.get(per, 0)
                var_pct = (aval - bval) / bval * 100.0 if bval else (100.0 if aval else 0.0)
                variance_trend.append({"period_ordinal": per, "budget_total": bval, "actual_total": aval, "variance_pct": round(var_pct, 2)})
            department_ranking = dept_by_bid.get(bid, [])
            n_actual_periods = len(actual_by_period)
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


@router.post("/nl-query")
async def natural_language_budget_query(
    body: NLQueryBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    llm: LLMRouter = Depends(get_llm_router),
) -> dict[str, Any]:
    """Natural language budget query (VA-P8-10)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    async with tenant_conn(x_tenant_id) as conn:
        if body.budget_id:
            rows = await conn.fetch(
                "SELECT budget_id, label, status, current_version_id FROM budgets WHERE tenant_id = $1 AND budget_id = $2",
                x_tenant_id,
                body.budget_id,
            )
            if not rows:
                raise HTTPException(404, "Budget not found")
        else:
            rows = await conn.fetch(
                "SELECT budget_id, label, status, current_version_id FROM budgets WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 20",
                x_tenant_id,
            )
        # Batch-fetch data for all budgets with versions (eliminates N+1)
        valid_bids: list[str] = []
        valid_vids: list[str] = []
        for b in rows:
            if b["current_version_id"]:
                valid_bids.append(b["budget_id"])
                valid_vids.append(b["current_version_id"])

        nl_total_map: dict[str, float] = {}
        nl_actual_map: dict[str, float] = {}
        nl_dept_map: dict[str, list[dict[str, Any]]] = {}

        if valid_bids:
            # Q1: total budget per budget_id
            tot_rows = await conn.fetch(
                """WITH bv AS (
                     SELECT unnest($2::text[]) AS budget_id, unnest($3::text[]) AS version_id
                   )
                   SELECT bli.budget_id, COALESCE(SUM(blia.amount), 0) AS total
                   FROM bv
                   JOIN budget_line_items bli ON bli.budget_id = bv.budget_id AND bli.version_id = bv.version_id AND bli.tenant_id = $1
                   JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
                   GROUP BY bli.budget_id""",
                x_tenant_id, valid_bids, valid_vids,
            )
            for r in tot_rows:
                nl_total_map[r["budget_id"]] = float(r["total"])

            # Q2: total actuals per budget_id
            act_rows = await conn.fetch(
                """SELECT budget_id, COALESCE(SUM(amount), 0) AS total
                   FROM budget_actuals
                   WHERE tenant_id = $1 AND budget_id = ANY($2::text[])
                   GROUP BY budget_id""",
                x_tenant_id, valid_bids,
            )
            for r in act_rows:
                nl_actual_map[r["budget_id"]] = float(r["total"])

            # Q3: department ranking per budget_id
            dept_rows_q = await conn.fetch(
                """SELECT budget_id, department_ref, SUM(amount) AS total
                   FROM budget_actuals
                   WHERE tenant_id = $1 AND budget_id = ANY($2::text[])
                   GROUP BY budget_id, department_ref
                   ORDER BY budget_id, total DESC""",
                x_tenant_id, valid_bids,
            )
            for r in dept_rows_q:
                nl_dept_map.setdefault(r["budget_id"], []).append(
                    {"department_ref": r["department_ref"] or "(none)", "total": float(r["total"])}
                )

        context_parts: list[str] = []
        for b in rows:
            bid = b["budget_id"]
            label = b["label"]
            if not b["current_version_id"]:
                context_parts.append(f"Budget '{label}' ({bid}): no version yet.")
                continue
            total_budget = nl_total_map.get(bid, 0.0)
            total_actual = nl_actual_map.get(bid, 0.0)
            utilisation_pct = round((total_actual / total_budget * 100.0), 2) if total_budget else None
            dept_entries = nl_dept_map.get(bid, [])
            dept_str = "; ".join(f"{d['department_ref']}: {d['total']:,.0f}" for d in dept_entries[:15])
            context_parts.append(
                f"Budget '{label}' (id={bid}): total_budget={total_budget:,.0f}, total_actual={total_actual:,.0f}, "
                f"utilisation_pct={utilisation_pct}%; departments (actuals): {dept_str or 'none'}"
            )
        budget_ids_list = [r["budget_id"] for r in rows]
        context_text = "\n".join(context_parts) if context_parts else "No budget data available."
    agent = get_agent_service()
    if agent and get_settings().agent_budget_nl_query_enabled:
        try:
            content = await run_budget_nl_query_agent(
                x_tenant_id, agent, body.question, budget_ids=budget_ids_list if budget_ids_list else None
            )
        except LLMError as e:
            raise HTTPException(
                429 if e.code == "ERR_LLM_QUOTA_EXCEEDED" else 503,
                detail=f"{e.message}: {e.details}" if e.details else e.message,
            ) from e
        return {
            "answer": content.get("answer", "No answer generated."),
            "citations": content.get("citations") or [],
        }
    prompt = (
        "Answer the user's question using ONLY the following budget data. "
        "Do not invent or assume any numbers. If the answer cannot be determined from the data, say so clearly. "
        "Keep the answer concise (1-3 sentences).\n\nData:\n" + context_text + "\n\nQuestion: " + body.question
    )
    try:
        response = await llm.complete_with_routing(
            x_tenant_id,
            [{"role": "user", "content": prompt}],
            NL_QUERY_RESPONSE_SCHEMA,
            "budget_nl_query",
            max_tokens=512,
            temperature=0.1,
        )
    except LLMError as e:
        raise HTTPException(
            503 if e.code == "ERR_LLM_ALL_PROVIDERS_FAILED" else 429,
            detail=f"{e.message}: {e.details}" if e.details else e.message,
        ) from e
    content = response.content or {}
    if not isinstance(content, dict):
        logger.warning("llm_nl_query_not_dict", content_type=type(content).__name__)
        content = {}
    return {
        "answer": content.get("answer", "No answer generated."),
        "citations": content.get("citations") or [],
    }


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
        budget_rows = await conn.fetch(
            """SELECT bli.account_ref, bli.is_revenue, blia.period_ordinal, blia.amount AS budget_amount
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
        revenue_flags: dict[str, bool] = {}
        for r in budget_rows:
            key = (r["account_ref"], r["period_ordinal"])
            budget_by_key[key] = float(r["budget_amount"])
            revenue_flags[r["account_ref"]] = r["is_revenue"]
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
            is_revenue_line = revenue_flags.get(acc, False)
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
            actual_periods = await conn.fetch(
                "SELECT DISTINCT period_ordinal FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2 ORDER BY period_ordinal",
                x_tenant_id,
                budget_id,
            )
            periods_with_actuals = {r["period_ordinal"] for r in actual_periods}
            line_rows = await conn.fetch(
                """SELECT line_item_id, account_ref, notes, is_revenue FROM budget_line_items
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
            agent = get_agent_service()
            if agent and get_settings().agent_reforecast_enabled:
                try:
                    content = await run_reforecast_agent(
                        x_tenant_id, agent, budget_id, ytd_actuals, remaining_by_account,
                    )
                except LLMError as e:
                    raise HTTPException(
                        429 if e.code == "ERR_LLM_QUOTA_EXCEEDED" else 503,
                        detail=f"{e.message}: {e.details}" if e.details else e.message,
                    ) from e
            else:
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
            if not isinstance(content, dict):
                logger.warning("llm_reforecast_not_dict", content_type=type(content).__name__)
                content = {}
            revisions = content.get("revisions") or []
            if not isinstance(revisions, list):
                revisions = []
            revisions = [r for r in revisions if isinstance(r, dict)]
            for li in line_rows:
                new_li_id = _line_item_id()
                account_ref = li["account_ref"]
                rev = next((r for r in revisions if r.get("account_ref") == account_ref), None)
                await conn.execute(
                    """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes, confidence_score, is_revenue)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
                    x_tenant_id,
                    new_li_id,
                    budget_id,
                    new_version_id,
                    account_ref,
                    li["notes"],
                    (rev.get("confidence") if rev else None),
                    li["is_revenue"],
                )
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
                _rev_amt_list = (rev.get("amounts") or []) if rev else []
                rev_amounts = {a["period_ordinal"]: a["amount"] for a in _rev_amt_list if isinstance(a, dict) and "period_ordinal" in a}
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
