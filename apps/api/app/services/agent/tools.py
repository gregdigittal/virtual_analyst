"""Tenant-scoped tools for Claude Agent SDK agents."""

from __future__ import annotations

import json
from typing import Any

import structlog

from apps.api.app.db import tenant_conn
from shared.fm_shared.model.kpis import calculate_kpis
from shared.fm_shared.model.statements import Statements

logger = structlog.get_logger()

# Budget tools: used by budget_agent.py and reforecast_agent.py tool dispatch.
# Model tools (query_model_state, query_run_results, compute_kpis_from_statements):
# available for future agent tasks; not currently wired into any dispatch.


async def query_budget_summary(tenant_id: str, budget_id: str | None = None) -> dict[str, Any]:
    """List budgets or get a specific budget summary. Returns budget metadata + total amounts."""
    async with tenant_conn(tenant_id) as conn:
        if budget_id:
            row = await conn.fetchrow(
                """SELECT budget_id, label, fiscal_year, status, current_version_id, created_at
                   FROM budgets WHERE tenant_id = $1 AND budget_id = $2""",
                tenant_id,
                budget_id,
            )
            if not row:
                return {"error": f"Budget {budget_id} not found"}
            total = await conn.fetchval(
                """SELECT COALESCE(SUM(a.amount), 0)::numeric
                   FROM budget_line_item_amounts a
                   JOIN budget_line_items li ON li.tenant_id = a.tenant_id AND li.line_item_id = a.line_item_id
                   WHERE li.tenant_id = $1 AND li.budget_id = $2 AND li.version_id = $3""",
                tenant_id,
                budget_id,
                row["current_version_id"],
            )
            return {
                "budget_id": row["budget_id"],
                "label": row["label"],
                "fiscal_year": row["fiscal_year"],
                "status": row["status"],
                "total_budget": float(total or 0),
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        rows = await conn.fetch(
            """SELECT budget_id, label, fiscal_year, status, created_at
               FROM budgets WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 20""",
            tenant_id,
        )
    return {
        "budgets": [
            {
                "budget_id": r["budget_id"],
                "label": r["label"],
                "fiscal_year": r["fiscal_year"],
                "status": r["status"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


async def query_budget_line_items(
    tenant_id: str,
    budget_id: str,
    account_ref: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Get line items for a budget, optionally filtered by account_ref. Includes per-period amounts."""
    async with tenant_conn(tenant_id) as conn:
        version_id = await conn.fetchval(
            "SELECT current_version_id FROM budgets WHERE tenant_id = $1 AND budget_id = $2",
            tenant_id,
            budget_id,
        )
        if not version_id:
            return {"error": f"Budget {budget_id} not found"}
        if account_ref:
            rows = await conn.fetch(
                """SELECT li.line_item_id, li.account_ref, li.notes,
                          json_agg(json_build_object('period', a.period_ordinal, 'amount', a.amount) ORDER BY a.period_ordinal) AS amounts
                   FROM budget_line_items li
                   LEFT JOIN budget_line_item_amounts a ON a.tenant_id = li.tenant_id AND a.line_item_id = li.line_item_id
                   WHERE li.tenant_id = $1 AND li.budget_id = $2 AND li.version_id = $3 AND li.account_ref = $4
                   GROUP BY li.line_item_id, li.account_ref, li.notes LIMIT $5""",
                tenant_id,
                budget_id,
                version_id,
                account_ref,
                limit,
            )
        else:
            rows = await conn.fetch(
                """SELECT li.line_item_id, li.account_ref, li.notes,
                          json_agg(json_build_object('period', a.period_ordinal, 'amount', a.amount) ORDER BY a.period_ordinal) AS amounts
                   FROM budget_line_items li
                   LEFT JOIN budget_line_item_amounts a ON a.tenant_id = li.tenant_id AND a.line_item_id = li.line_item_id
                   WHERE li.tenant_id = $1 AND li.budget_id = $2 AND li.version_id = $3
                   GROUP BY li.line_item_id, li.account_ref, li.notes LIMIT $4""",
                tenant_id,
                budget_id,
                version_id,
                limit,
            )
    return {
        "line_items": [
            {
                "line_item_id": r["line_item_id"],
                "account_ref": r["account_ref"],
                "notes": r["notes"],
                "amounts": json.loads(r["amounts"]) if isinstance(r["amounts"], str) else (r["amounts"] or []),
            }
            for r in rows
        ]
    }


async def query_budget_actuals(
    tenant_id: str,
    budget_id: str,
    account_ref: str | None = None,
) -> dict[str, Any]:
    """Get actual spending for a budget, optionally filtered by account_ref."""
    async with tenant_conn(tenant_id) as conn:
        if account_ref:
            rows = await conn.fetch(
                """SELECT period_ordinal, account_ref, SUM(amount) AS total
                   FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2 AND account_ref = $3
                   GROUP BY period_ordinal, account_ref ORDER BY period_ordinal""",
                tenant_id,
                budget_id,
                account_ref,
            )
        else:
            rows = await conn.fetch(
                """SELECT period_ordinal, account_ref, SUM(amount) AS total
                   FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2
                   GROUP BY period_ordinal, account_ref ORDER BY period_ordinal, account_ref""",
                tenant_id,
                budget_id,
            )
    return {
        "actuals": [
            {"period_ordinal": r["period_ordinal"], "account_ref": r["account_ref"], "total": float(r["total"])}
            for r in rows
        ]
    }


async def query_department_breakdown(tenant_id: str, budget_id: str) -> dict[str, Any]:
    """Get department-level allocation and actuals breakdown for a budget."""
    async with tenant_conn(tenant_id) as conn:
        alloc_rows = await conn.fetch(
            """SELECT department_ref, SUM(allocation_amount) AS total
               FROM budget_department_allocations WHERE tenant_id = $1 AND budget_id = $2
               GROUP BY department_ref ORDER BY total DESC""",
            tenant_id,
            budget_id,
        )
        actual_rows = await conn.fetch(
            """SELECT department_ref, SUM(amount) AS total
               FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2
               GROUP BY department_ref ORDER BY total DESC""",
            tenant_id,
            budget_id,
        )
    return {
        "allocations": [{"department": r["department_ref"], "total": float(r["total"])} for r in alloc_rows],
        "actuals_by_department": [{"department": r["department_ref"], "total": float(r["total"])} for r in actual_rows],
    }


async def calculate_variance(
    tenant_id: str,
    budget_id: str,
    account_ref: str | None = None,
) -> dict[str, Any]:
    """Calculate budget vs. actual variance for a budget, optionally filtered by account_ref."""
    async with tenant_conn(tenant_id) as conn:
        version_id = await conn.fetchval(
            "SELECT current_version_id FROM budgets WHERE tenant_id = $1 AND budget_id = $2",
            tenant_id,
            budget_id,
        )
        if not version_id:
            return {"error": f"Budget {budget_id} not found"}
        budget_query = """
            SELECT li.account_ref, SUM(a.amount) AS total_budget
            FROM budget_line_items li
            JOIN budget_line_item_amounts a ON a.tenant_id = li.tenant_id AND a.line_item_id = li.line_item_id
            WHERE li.tenant_id = $1 AND li.budget_id = $2 AND li.version_id = $3
        """
        params: list[Any] = [tenant_id, budget_id, version_id]
        if account_ref:
            budget_query += " AND li.account_ref = $4"
            params.append(account_ref)
        budget_query += " GROUP BY li.account_ref"
        budget_rows = await conn.fetch(budget_query, *params)
        actual_query = """
            SELECT account_ref, SUM(amount) AS total_actual
            FROM budget_actuals WHERE tenant_id = $1 AND budget_id = $2
        """
        actual_params: list[Any] = [tenant_id, budget_id]
        if account_ref:
            actual_query += " AND account_ref = $3"
            actual_params.append(account_ref)
        actual_query += " GROUP BY account_ref"
        actual_rows = await conn.fetch(actual_query, *actual_params)
    budget_map = {r["account_ref"]: float(r["total_budget"]) for r in budget_rows}
    actual_map = {r["account_ref"]: float(r["total_actual"]) for r in actual_rows}
    all_accounts = sorted(set(budget_map) | set(actual_map))
    variances = []
    for acct in all_accounts:
        b = budget_map.get(acct, 0.0)
        a = actual_map.get(acct, 0.0)
        variances.append(
            {
                "account_ref": acct,
                "budget": round(b, 2),
                "actual": round(a, 2),
                "variance": round(a - b, 2),
                "variance_pct": round(((a - b) / b * 100), 2) if b else None,
            }
        )
    return {"variances": variances}


async def query_model_state(
    tenant_id: str,
    baseline_id: str | None = None,
    store: Any = None,
) -> dict[str, Any]:
    """Load the current model config/assumptions from artifact store or list active baselines."""
    if baseline_id and store:
        try:
            data = store.load(tenant_id, "baseline", baseline_id)
            config = data.get("model_config", data)
            return {"baseline_id": baseline_id, "config_keys": list(config.keys()), "config": config}
        except Exception as e:
            return {"error": f"Could not load baseline {baseline_id}: {e}"}
    async with tenant_conn(tenant_id) as conn:
        rows = await conn.fetch(
            """SELECT baseline_id, baseline_version, status, is_active, created_at
               FROM model_baselines WHERE tenant_id = $1 ORDER BY created_at DESC LIMIT 10""",
            tenant_id,
        )
    return {
        "baselines": [
            {
                "baseline_id": r["baseline_id"],
                "version": r["baseline_version"],
                "status": r["status"],
                "is_active": r["is_active"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
            }
            for r in rows
        ]
    }


async def query_run_results(
    tenant_id: str,
    run_id: str,
    store: Any = None,
) -> dict[str, Any]:
    """Load run results (statements + KPIs) from artifact store."""
    if not store:
        return {"error": "Artifact store not available"}
    try:
        data = store.load(tenant_id, "run_results", f"{run_id}_statements")
        return {
            "run_id": run_id,
            "has_statements": "statements" in data,
            "has_kpis": "kpis" in data,
            "periods": data.get("statements", {}).get("periods", []),
            "kpi_count": len(data.get("kpis", [])),
            "kpis_summary": data.get("kpis", [])[:3],
        }
    except Exception as e:
        return {"error": f"Could not load run results for {run_id}: {e}"}


def compute_kpis_from_statements(statements_dict: dict[str, Any]) -> list[dict[str, Any]]:
    """Run KPI calculations on raw statements data. Pure computation, no DB."""
    try:
        stmts = Statements(**statements_dict)
        return calculate_kpis(stmts)
    except Exception as e:
        return [{"error": f"KPI calculation failed: {e}"}]
