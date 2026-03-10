"""Shared budget models, helpers, and imports used across budget sub-routers."""

from __future__ import annotations

import uuid
from typing import Any

import asyncpg
import structlog
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field

from apps.api.app.db import tenant_conn  # noqa: F401
from apps.api.app.db.budgets import (  # noqa: F401
    BUDGET_STATUSES,
    ensure_budget_version,
    get_budget,
    get_version_line_item_totals,
)
from apps.api.app.deps import require_role, ROLES_CAN_WRITE  # noqa: F401

logger = structlog.get_logger()


# --- ID generators ---

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


# --- Shared request/response models ---

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
    is_revenue: bool = Field(default=False, description="True if this line item is a revenue/income account")


class UpdateLineItemBody(BaseModel):
    notes: str | None = Field(default=None, max_length=2000)
    amounts: list[LineItemAmount] | None = Field(default=None)
    is_revenue: bool | None = Field(default=None, description="True if this line item is a revenue/income account")


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


class AddPeriodsBody(BaseModel):
    periods: list[PeriodItem] = Field(..., min_length=1)


class ActualItem(BaseModel):
    period_ordinal: int = Field(..., ge=1)
    account_ref: str = Field(..., min_length=1)
    amount: float = Field(...)
    department_ref: str = Field(default="", max_length=255)


class ImportActualsBody(BaseModel):
    actuals: list[ActualItem] = Field(..., min_length=1)
    source: str = Field(default="csv", pattern="^(csv|erp)$")


class NLQueryBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    budget_id: str | None = Field(default=None, description="Optional: scope to one budget")


# --- Shared helpers ---

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
