"""Budget DB helpers: current version resolution, status checks."""

from __future__ import annotations

from typing import Any

import asyncpg

BUDGET_STATUSES = frozenset(
    {"draft", "submitted", "under_review", "approved", "active", "closed"}
)


async def get_budget(
    conn: asyncpg.Connection, tenant_id: str, budget_id: str
) -> asyncpg.Record | None:
    """Return budget row or None."""
    return await conn.fetchrow(
        """SELECT budget_id, label, fiscal_year, status, current_version_id,
                  created_at, updated_at, created_by, workflow_instance_id
           FROM budgets WHERE tenant_id = $1 AND budget_id = $2""",
        tenant_id,
        budget_id,
    )


async def get_current_version_id(
    conn: asyncpg.Connection, tenant_id: str, budget_id: str
) -> str | None:
    """Return current_version_id for budget, or None if no version yet."""
    row = await conn.fetchrow(
        "SELECT current_version_id FROM budgets WHERE tenant_id = $1 AND budget_id = $2",
        tenant_id,
        budget_id,
    )
    return row["current_version_id"] if row else None


async def ensure_budget_version(
    conn: asyncpg.Connection,
    tenant_id: str,
    budget_id: str,
    version_id: str,
    version_number: int,
    created_by: str | None = None,
) -> None:
    """Insert a budget version and set it as current. Caller must be in a transaction."""
    await conn.execute(
        """INSERT INTO budget_versions (tenant_id, budget_id, version_id, version_number, created_by)
           VALUES ($1, $2, $3, $4, $5)
           ON CONFLICT (tenant_id, budget_id, version_id) DO NOTHING""",
        tenant_id,
        budget_id,
        version_id,
        version_number,
        created_by,
    )
    await conn.execute(
        """UPDATE budgets SET current_version_id = $1, updated_at = now()
           WHERE tenant_id = $2 AND budget_id = $3""",
        version_id,
        tenant_id,
        budget_id,
    )


async def get_version_line_item_totals(
    conn: asyncpg.Connection, tenant_id: str, budget_id: str, version_id: str
) -> dict[str, float]:
    """Return total amount per period_ordinal for the given version (sum over line items)."""
    rows = await conn.fetch(
        """SELECT period_ordinal, COALESCE(SUM(amount), 0) AS total
           FROM budget_line_items bli
           JOIN budget_line_item_amounts blia ON blia.tenant_id = bli.tenant_id AND blia.line_item_id = bli.line_item_id
           WHERE bli.tenant_id = $1 AND bli.budget_id = $2 AND bli.version_id = $3
           GROUP BY period_ordinal""",
        tenant_id,
        budget_id,
        version_id,
    )
    return {str(r["period_ordinal"]): float(r["total"]) for r in rows}
