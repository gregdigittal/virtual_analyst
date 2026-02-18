"""LLM usage metering — persisted to llm_usage_log (FIX-C03)."""

from __future__ import annotations

from datetime import UTC, datetime

from apps.api.app.db import tenant_conn


def _current_period() -> str:
    now = datetime.now(UTC)
    return now.strftime("%Y-%m")


async def get_usage(tenant_id: str, period: str | None = None) -> dict[str, int | float]:
    """Return aggregated LLM usage for tenant/period from llm_usage_log."""
    p = period or _current_period()
    async with tenant_conn(tenant_id) as conn:
        row = await conn.fetchrow(
            """SELECT COALESCE(SUM(tokens_total), 0)::bigint AS llm_tokens_total,
                      COALESCE(SUM(calls), 0)::bigint AS llm_calls,
                      COALESCE(SUM(estimated_usd), 0)::numeric AS llm_estimated_usd
               FROM llm_usage_log WHERE tenant_id = $1 AND period = $2""",
            tenant_id,
            p,
        )
    if not row:
        return {"llm_tokens_total": 0, "llm_calls": 0, "llm_estimated_usd": 0.0}
    return {
        "llm_tokens_total": int(row["llm_tokens_total"]),
        "llm_calls": int(row["llm_calls"]),
        "llm_estimated_usd": float(row["llm_estimated_usd"]),
    }


async def add_usage(
    tenant_id: str,
    tokens: int,
    cost_estimate_usd: float,
    period: str | None = None,
    provider: str = "unknown",
) -> None:
    """Record one LLM call in llm_usage_log."""
    p = period or _current_period()
    async with tenant_conn(tenant_id) as conn:
        await conn.execute(
            """INSERT INTO llm_usage_log (tenant_id, provider, tokens_total, calls, estimated_usd, period)
               VALUES ($1, $2, $3, 1, $4, $5)""",
            tenant_id,
            provider,
            tokens,
            cost_estimate_usd,
            p,
        )


async def check_limit(tenant_id: str, limit: int, period: str | None = None) -> bool:
    """Return True if tenant's usage is below limit."""
    usage = await get_usage(tenant_id, period)
    return int(usage["llm_tokens_total"]) < limit


def reset_usage() -> None:
    """No-op: usage is persisted; use DB truncate if needed for tests."""
    pass
