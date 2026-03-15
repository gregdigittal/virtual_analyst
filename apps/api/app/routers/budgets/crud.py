"""Budget CRUD: create, list, get, update, submit, clone."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
from fastapi import APIRouter, Header, HTTPException, Query

from apps.api.app.routers.budgets._common import (
    BUDGET_STATUSES,
    CloneBudgetBody,
    CreateBudgetBody,
    UpdateBudgetBody,
    _allocation_id,
    _budget_id,
    _line_item_id,
    _period_id,
    _resolve_current_version,
    _version_id,
    ensure_budget_version,
    get_budget,
    require_role,
    ROLES_CAN_WRITE,
    tenant_conn,
)

router = APIRouter(tags=["budgets"], dependencies=[require_role(*ROLES_CAN_WRITE)])

BUDGET_APPROVAL_TEMPLATE_ID = "tpl_budget_approval"


@router.post("/", status_code=201)
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


@router.get("/")
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
        "label": row["label"],
        "fiscal_year": row["fiscal_year"],
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
            period_rows = await conn.fetch(
                """SELECT period_ordinal, period_start, period_end, label
                   FROM budget_periods WHERE tenant_id = $1 AND budget_id = $2
                   ORDER BY period_ordinal""",
                x_tenant_id,
                budget_id,
            )
            # Batch insert periods — eliminates N+1
            await conn.executemany(
                """INSERT INTO budget_periods (tenant_id, budget_id, period_id, period_ordinal, period_start, period_end, label)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)
                   ON CONFLICT (tenant_id, budget_id, period_ordinal) DO NOTHING""",
                [
                    (x_tenant_id, new_budget_id, _period_id(), pr["period_ordinal"], pr["period_start"], pr["period_end"], pr["label"])
                    for pr in period_rows
                ],
            )
            rows = await conn.fetch(
                """SELECT line_item_id, account_ref, notes, is_revenue FROM budget_line_items
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
            # Build new line item records with pre-generated IDs for batch insert
            new_line_items = [(x_tenant_id, _line_item_id(), new_budget_id, new_version_id, r["account_ref"], r["notes"], r["is_revenue"]) for r in rows]
            await conn.executemany(
                """INSERT INTO budget_line_items (tenant_id, line_item_id, budget_id, version_id, account_ref, notes, is_revenue)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                new_line_items,
            )
            # Build amounts for all new line items — correlate by position
            new_amounts = []
            for old_row, new_item in zip(rows, new_line_items):
                new_li_id = new_item[1]
                for period_ordinal, amount in amounts_by_item.get(old_row["line_item_id"], []):
                    new_amounts.append((x_tenant_id, new_li_id, period_ordinal, amount))
            if new_amounts:
                await conn.executemany(
                    """INSERT INTO budget_line_item_amounts (tenant_id, line_item_id, period_ordinal, amount)
                       VALUES ($1, $2, $3, $4)""",
                    new_amounts,
                )
            alloc_rows = await conn.fetch(
                """SELECT department_ref, amount_limit FROM budget_department_allocations
                   WHERE tenant_id = $1 AND budget_id = $2 AND version_id = $3""",
                x_tenant_id,
                budget_id,
                version_id,
            )
            # Batch insert allocations — eliminates N+1
            await conn.executemany(
                """INSERT INTO budget_department_allocations (tenant_id, allocation_id, budget_id, version_id, department_ref, amount_limit)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                [
                    (x_tenant_id, _allocation_id(), new_budget_id, new_version_id, ar["department_ref"], ar["amount_limit"])
                    for ar in alloc_rows
                ],
            )
    return {
        "budget_id": new_budget_id,
        "label": body.label,
        "fiscal_year": body.fiscal_year,
        "status": "draft",
        "current_version_id": new_version_id,
    }
