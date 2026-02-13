"""Billing and usage: plans, subscriptions, usage_meters, llm_call_logs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import asyncpg


def _current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


async def get_plans(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    """Return all active billing plans."""
    rows = await conn.fetch(
        """SELECT plan_id, label, tier, limits_json, pricing_json, features_json, status, created_at
           FROM billing_plans WHERE status = 'active' ORDER BY tier"""
    )
    return [
        {
            "plan_id": r["plan_id"],
            "label": r["label"],
            "tier": r["tier"],
            "limits": r["limits_json"],
            "pricing": r["pricing_json"],
            "features": r["features_json"],
            "status": r["status"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


async def get_plan_by_id(conn: asyncpg.Connection, plan_id: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT plan_id, label, tier, limits_json, pricing_json, features_json, status FROM billing_plans WHERE plan_id = $1",
        plan_id,
    )
    if not row:
        return None
    return {
        "plan_id": row["plan_id"],
        "label": row["label"],
        "tier": row["tier"],
        "limits": row["limits_json"],
        "pricing": row["pricing_json"],
        "features": row["features_json"],
        "status": row["status"],
    }


async def get_subscription(
    conn: asyncpg.Connection,
    tenant_id: str,
) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        """SELECT subscription_id, plan_id, status, stripe_customer_id, stripe_subscription_id,
                  current_period_start, current_period_end, created_at, updated_at
           FROM billing_subscriptions
           WHERE tenant_id = $1 AND status IN ('active', 'trialing') ORDER BY created_at DESC LIMIT 1""",
        tenant_id,
    )
    if not row:
        return None
    return {
        "subscription_id": row["subscription_id"],
        "plan_id": row["plan_id"],
        "status": row["status"],
        "stripe_customer_id": row["stripe_customer_id"],
        "stripe_subscription_id": row["stripe_subscription_id"],
        "current_period_start": row["current_period_start"].isoformat() if row["current_period_start"] else None,
        "current_period_end": row["current_period_end"].isoformat() if row["current_period_end"] else None,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def create_subscription(
    conn: asyncpg.Connection,
    tenant_id: str,
    subscription_id: str,
    plan_id: str,
    current_period_start: datetime,
    current_period_end: datetime,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> None:
    await conn.execute(
        """INSERT INTO billing_subscriptions
           (tenant_id, subscription_id, plan_id, status, stripe_customer_id, stripe_subscription_id,
            current_period_start, current_period_end)
           VALUES ($1, $2, $3, 'active', $4, $5, $6, $7)""",
        tenant_id,
        subscription_id,
        plan_id,
        stripe_customer_id,
        stripe_subscription_id,
        current_period_start,
        current_period_end,
    )


async def update_subscription_plan(
    conn: asyncpg.Connection,
    tenant_id: str,
    subscription_id: str,
    new_plan_id: str,
    current_period_start: datetime,
    current_period_end: datetime,
) -> None:
    await conn.execute(
        """UPDATE billing_subscriptions SET
             plan_id = $3, current_period_start = $4, current_period_end = $5, updated_at = now()
           WHERE tenant_id = $1 AND subscription_id = $2""",
        tenant_id,
        subscription_id,
        new_plan_id,
        current_period_start,
        current_period_end,
    )


async def cancel_subscription(
    conn: asyncpg.Connection,
    tenant_id: str,
    subscription_id: str,
) -> None:
    await conn.execute(
        "UPDATE billing_subscriptions SET status = 'cancelled', updated_at = now() WHERE tenant_id = $1 AND subscription_id = $2",
        tenant_id,
        subscription_id,
    )


async def set_stripe_ids(
    conn: asyncpg.Connection,
    tenant_id: str,
    subscription_id: str,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
) -> None:
    await conn.execute(
        """UPDATE billing_subscriptions SET
             stripe_customer_id = COALESCE($3, stripe_customer_id),
             stripe_subscription_id = COALESCE($4, stripe_subscription_id),
             updated_at = now()
           WHERE tenant_id = $1 AND subscription_id = $2""",
        tenant_id,
        subscription_id,
        stripe_customer_id,
        stripe_subscription_id,
    )


async def get_tenant_by_stripe_subscription_id(
    conn: asyncpg.Connection,
    stripe_subscription_id: str,
) -> tuple[str, str] | None:
    """Return (tenant_id, subscription_id) for Stripe webhook lookup. Uses SECURITY DEFINER function."""
    row = await conn.fetchrow(
        "SELECT tenant_id, subscription_id FROM get_tenant_by_stripe_subscription($1)",
        stripe_subscription_id,
    )
    if not row:
        return None
    return (row["tenant_id"], row["subscription_id"])


async def update_subscription_status(
    conn: asyncpg.Connection,
    tenant_id: str,
    subscription_id: str,
    status: str,
) -> None:
    await conn.execute(
        "UPDATE billing_subscriptions SET status = $3, updated_at = now() WHERE tenant_id = $1 AND subscription_id = $2",
        tenant_id,
        subscription_id,
        status,
    )


async def get_usage_meter(
    conn: asyncpg.Connection,
    tenant_id: str,
    period: str | None = None,
) -> dict[str, Any]:
    p = period or _current_period()
    row = await conn.fetchrow(
        "SELECT usage_json, costs_json, updated_at FROM usage_meters WHERE tenant_id = $1 AND period = $2",
        tenant_id,
        p,
    )
    if not row:
        return {
            "period": p,
            "usage": {"llm_calls": 0, "llm_tokens_total": 0, "llm_tokens_by_provider": {}, "llm_tokens_by_task": {}, "mc_runs": 0, "sync_events": 0},
            "costs": {"currency": "USD", "llm_estimated_cents": 0},
        }
    return {
        "period": p,
        "usage": dict(row["usage_json"]) if row["usage_json"] else {},
        "costs": dict(row["costs_json"]) if row["costs_json"] else {},
        "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
    }


async def replace_usage_meter(
    conn: asyncpg.Connection,
    tenant_id: str,
    usage_json: dict[str, Any],
    costs_json: dict[str, Any],
    period: str | None = None,
) -> None:
    """Replace usage and costs for the given period (used after merging deltas in service)."""
    p = period or _current_period()
    await conn.execute(
        """INSERT INTO usage_meters (tenant_id, period, usage_json, costs_json)
           VALUES ($1, $2, $3::jsonb, $4::jsonb)
           ON CONFLICT (tenant_id, period) DO UPDATE SET
             usage_json = EXCLUDED.usage_json,
             costs_json = EXCLUDED.costs_json,
             updated_at = now()""",
        tenant_id,
        p,
        asyncpg.types.Json(usage_json),
        asyncpg.types.Json(costs_json),
    )


async def insert_llm_call_log(
    conn: asyncpg.Connection,
    tenant_id: str,
    call_id: str,
    task_label: str,
    provider: str,
    model: str,
    tokens_json: dict[str, Any],
    latency_ms: int,
    cost_estimate_usd: float,
    status: str = "success",
    error_message: str | None = None,
    retry_count: int = 0,
    correlation_json: dict[str, Any] | None = None,
) -> None:
    await conn.execute(
        """INSERT INTO llm_call_logs
           (tenant_id, call_id, task_label, provider, model, tokens_json, latency_ms, cost_estimate_usd, status, error_message, retry_count, correlation_json)
           VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12::jsonb)""",
        tenant_id,
        call_id,
        task_label,
        provider,
        model,
        asyncpg.types.Json(tokens_json),
        latency_ms,
        cost_estimate_usd,
        status,
        error_message,
        retry_count,
        asyncpg.types.Json(correlation_json) if correlation_json else None,
    )
