"""Budget periods, line items, and department allocations."""

from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import Any

from fastapi import APIRouter, Header, HTTPException

from apps.api.app.routers.budgets._common import (
    AddLineItemBody,
    AddPeriodsBody,
    DepartmentAllocationItem,
    SetDepartmentsBody,
    UpdateLineItemBody,
    _allocation_id,
    _line_item_id,
    _period_id,
    _resolve_current_version,
    get_budget,
    get_version_line_item_totals,
    require_role,
    ROLES_CAN_WRITE,
    tenant_conn,
)

router = APIRouter(tags=["budgets"], dependencies=[require_role(*ROLES_CAN_WRITE)])


# --- Periods ---


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
                       VALUES ($1, $2, $3, $4, $5, $6, $7)
                       ON CONFLICT (tenant_id, budget_id, period_ordinal) DO UPDATE SET period_start = $5, period_end = $6, label = $7""",
                    x_tenant_id,
                    budget_id,
                    period_id,
                    item.period_ordinal,
                    date.fromisoformat(item.period_start),
                    date.fromisoformat(item.period_end),
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
            """SELECT bli.line_item_id, bli.account_ref, bli.notes, bli.confidence_score, bli.is_revenue,
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
                    "is_revenue": r["is_revenue"],
                    "amounts": [],
                }
            if r["period_ordinal"] is not None:
                grouped[lid]["amounts"].append({
                    "period_ordinal": r["period_ordinal"],
                    "amount": float(r["amount"]),
                })
    return {"line_items": list(grouped.values())}


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
                """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes, is_revenue)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                x_tenant_id,
                line_item_id,
                budget_id,
                version_id,
                body.account_ref,
                body.notes,
                body.is_revenue,
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
        "is_revenue": body.is_revenue,
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
            """SELECT line_item_id, account_ref, notes, is_revenue FROM budget_line_items
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
        if body.is_revenue is not None:
            await conn.execute(
                "UPDATE budget_line_items SET is_revenue = $1 WHERE tenant_id = $2 AND line_item_id = $3",
                body.is_revenue,
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
            "SELECT account_ref, notes, is_revenue FROM budget_line_items WHERE tenant_id = $1 AND line_item_id = $2",
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
        "is_revenue": row["is_revenue"],
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
    """Set department allocations for the current version."""
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
