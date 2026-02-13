"""Billing service: plans, subscriptions, limit checks, usage recording."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from apps.api.app.db import tenant_conn
from apps.api.app.db.billing import (
    cancel_subscription as db_cancel_subscription,
    create_subscription as db_create_subscription,
    get_plan_by_id,
    get_plans,
    get_subscription as db_get_subscription,
    get_usage_meter,
    insert_llm_call_log,
    replace_usage_meter,
    update_subscription_plan as db_update_subscription_plan,
)
from apps.api.app.db.connection import ensure_tenant

DEFAULT_PLAN_ID = "plan_starter"


def _current_period() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _period_range(period: str) -> tuple[datetime, datetime]:
    """Return (period_start, period_end) for YYYY-MM."""
    year, month = int(period[:4]), int(period[5:7])
    from calendar import monthrange
    start = datetime(year, month, 1, tzinfo=UTC)
    last_day = monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59, 999999, tzinfo=UTC)
    return start, end


class BillingService:
    """Plan and subscription management; limit enforcement; usage recording."""

    async def get_plans(self) -> list[dict[str, Any]]:
        """Return all active billing plans (platform table, no tenant scope)."""
        async with tenant_conn("") as conn:
            return await get_plans(conn)

    async def get_subscription(self, tenant_id: str) -> dict[str, Any] | None:
        async with tenant_conn(tenant_id) as conn:
            return await db_get_subscription(conn, tenant_id)

    async def get_usage(self, tenant_id: str, period: str | None = None) -> dict[str, Any]:
        """Current period usage and costs for tenant."""
        p = period or _current_period()
        async with tenant_conn(tenant_id) as conn:
            return await get_usage_meter(conn, tenant_id, p)

    async def create_subscription(
        self,
        tenant_id: str,
        plan_id: str,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a new subscription for the tenant on the given plan."""
        async with tenant_conn(tenant_id) as conn:
            async with conn.transaction():
                await ensure_tenant(conn, tenant_id)
                plan = await get_plan_by_id(conn, plan_id)
                if not plan:
                    raise ValueError(f"Unknown plan: {plan_id}")
                sub_id = f"sub_{uuid.uuid4().hex[:16]}"
                p = _current_period()
                start, end = _period_range(p)
                await db_create_subscription(
                    conn,
                    tenant_id,
                    sub_id,
                    plan_id,
                    start,
                    end,
                    stripe_customer_id=stripe_customer_id,
                    stripe_subscription_id=stripe_subscription_id,
                )
        return await self.get_subscription(tenant_id) or {}

    async def update_subscription(self, tenant_id: str, new_plan_id: str) -> dict[str, Any] | None:
        """Change subscription to new plan (same period or new period)."""
        async with tenant_conn(tenant_id) as conn:
            sub = await db_get_subscription(conn, tenant_id)
            if not sub:
                return None
            plan = await get_plan_by_id(conn, new_plan_id)
            if not plan:
                raise ValueError(f"Unknown plan: {new_plan_id}")
            p = _current_period()
            start, end = _period_range(p)
            await db_update_subscription_plan(
                conn,
                tenant_id,
                sub["subscription_id"],
                new_plan_id,
                start,
                end,
            )
        return await self.get_subscription(tenant_id)

    async def cancel_subscription(self, tenant_id: str) -> bool:
        """Cancel current subscription. Returns True if one was cancelled."""
        async with tenant_conn(tenant_id) as conn:
            sub = await db_get_subscription(conn, tenant_id)
            if not sub:
                return False
            await db_cancel_subscription(conn, tenant_id, sub["subscription_id"])
        return True

    async def get_llm_limit(self, tenant_id: str) -> int:
        """Return the tenant's monthly LLM token limit (0 = unlimited)."""
        async with tenant_conn(tenant_id) as conn:
            await ensure_tenant(conn, tenant_id)
            sub = await db_get_subscription(conn, tenant_id)
            if not sub:
                return 0
            plan = await get_plan_by_id(conn, sub["plan_id"])
            if not plan:
                return 0
            limits = plan.get("limits") or {}
            return int(limits.get("llm_tokens_monthly", 0))

    async def check_llm_limit(self, tenant_id: str, estimated_tokens: int = 0) -> tuple[bool, int, int]:
        """
        Check if tenant is within LLM token limit for current period.
        Returns (allowed, current_usage, limit). Limit 0 means unlimited.
        """
        limit = await self.get_llm_limit(tenant_id)
        if limit == 0:
            return True, 0, 0
        usage_data = await self.get_usage(tenant_id)
        usage = usage_data.get("usage") or {}
        current = int(usage.get("llm_tokens_total", 0))
        if current + estimated_tokens > limit:
            return False, current, limit
        return True, current, limit

    async def record_llm_usage(
        self,
        tenant_id: str,
        tokens: int,
        cost_estimate_usd: float,
        task_label: str,
        provider: str,
        model: str,
        tokens_json: dict[str, Any],
        latency_ms: int,
        call_id: str | None = None,
        correlation_json: dict[str, Any] | None = None,
    ) -> None:
        """Record one LLM call: update usage_meter and insert llm_call_log."""
        call_id = call_id or f"call_{uuid.uuid4().hex[:16]}"
        p = _current_period()
        async with tenant_conn(tenant_id) as conn:
            async with conn.transaction():
                await ensure_tenant(conn, tenant_id)
                meter = await get_usage_meter(conn, tenant_id, p)
                usage = meter.get("usage") or {}
                costs = meter.get("costs") or {}
                usage = {
                    "llm_calls": int(usage.get("llm_calls", 0)) + 1,
                    "llm_tokens_total": int(usage.get("llm_tokens_total", 0)) + tokens,
                    "llm_tokens_by_provider": dict(usage.get("llm_tokens_by_provider") or {}),
                    "llm_tokens_by_task": dict(usage.get("llm_tokens_by_task") or {}),
                    "mc_runs": int(usage.get("mc_runs", 0)),
                    "sync_events": int(usage.get("sync_events", 0)),
                }
                usage["llm_tokens_by_provider"][provider] = usage["llm_tokens_by_provider"].get(provider, 0) + tokens
                usage["llm_tokens_by_task"][task_label] = usage["llm_tokens_by_task"].get(task_label, 0) + tokens
                cost_cents = int(round(cost_estimate_usd * 100))
                costs = {
                    "currency": costs.get("currency", "USD"),
                    "llm_estimated_cents": int(costs.get("llm_estimated_cents", 0)) + cost_cents,
                }
                await replace_usage_meter(conn, tenant_id, usage, costs, period=p)
                await insert_llm_call_log(
                    conn,
                    tenant_id,
                    call_id,
                    task_label,
                    provider,
                    model,
                    tokens_json,
                    latency_ms,
                    cost_estimate_usd,
                    status="success",
                    correlation_json=correlation_json,
                )

    async def ensure_default_subscription(self, tenant_id: str) -> dict[str, Any] | None:
        """If tenant has no subscription, create one on default plan. Return subscription."""
        sub = await self.get_subscription(tenant_id)
        if sub:
            return sub
        await self.create_subscription(tenant_id, DEFAULT_PLAN_ID)
        return await self.get_subscription(tenant_id)
