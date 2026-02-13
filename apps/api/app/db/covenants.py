"""Covenant definitions and breach check (VA-P4-05)."""

from __future__ import annotations

from typing import Any

import asyncpg

# Metric refs that match KPI keys from calculate_kpis (e.g. debt_equity, dscr, current_ratio)
COVENANT_METRIC_REFS = frozenset({
    "debt_equity", "dscr", "current_ratio", "roe", "fcf",
    "gross_margin_pct", "ebitda_margin_pct", "net_margin_pct",
    "revenue_growth_pct", "cash_conversion_cycle",
})


def _is_breach(actual: float, operator: str, threshold: float) -> bool:
    """Return True if the covenant is breached (condition not satisfied)."""
    if operator == "<":
        return actual >= threshold
    if operator == ">":
        return actual <= threshold
    if operator == "<=":
        return actual > threshold
    if operator == ">=":
        return actual < threshold
    return False


def check_covenants(
    kpis: list[dict[str, Any]],
    definitions: list[dict[str, Any]],
    *,
    check_all_periods: bool = False,
) -> list[dict[str, Any]]:
    """
    Check covenant definitions against KPI list (one dict per period).
    If check_all_periods=True, checks every period; otherwise last period only.
    Returns list of breached covenants with actual value and period_index.
    """
    if not kpis or not definitions:
        return []
    periods = kpis if check_all_periods else [kpis[-1]]
    breached: list[dict[str, Any]] = []
    for period_data in periods:
        for defn in definitions:
            metric_ref = defn.get("metric_ref") or ""
            if metric_ref not in period_data:
                continue
            actual = period_data.get(metric_ref)
            if actual is None:
                continue
            try:
                actual_f = float(actual)
            except (TypeError, ValueError):
                continue
            operator = defn.get("operator") or ""
            try:
                threshold = float(defn.get("threshold_value", 0))
            except (TypeError, ValueError):
                continue
            if _is_breach(actual_f, operator, threshold):
                breached.append({
                    "covenant_id": defn.get("covenant_id"),
                    "label": defn.get("label"),
                    "metric_ref": metric_ref,
                    "operator": operator,
                    "threshold_value": threshold,
                    "actual_value": actual_f,
                    "period_index": period_data.get("period_index"),
                })
    return breached


async def list_covenant_definitions(conn: asyncpg.Connection, tenant_id: str) -> list[dict[str, Any]]:
    """Return all covenant definitions for a tenant."""
    rows = await conn.fetch(
        """SELECT covenant_id, label, metric_ref, operator, threshold_value, created_at
           FROM covenant_definitions WHERE tenant_id = $1 ORDER BY created_at""",
        tenant_id,
    )
    return [
        {
            "covenant_id": r["covenant_id"],
            "label": r["label"],
            "metric_ref": r["metric_ref"],
            "operator": r["operator"],
            "threshold_value": float(r["threshold_value"]),
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]
