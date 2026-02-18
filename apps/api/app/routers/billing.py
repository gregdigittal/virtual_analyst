"""Billing API: plans, subscription, usage, Stripe webhook."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from apps.api.app.db import ensure_tenant, tenant_conn
from apps.api.app.deps import get_billing_service, require_role, ROLES_OWNER_ONLY, ROLES_OWNER_OR_ADMIN
from apps.api.app.services.billing import BillingService

router = APIRouter(prefix="/billing", tags=["billing"])


class CreateSubscriptionBody(BaseModel):
    plan_id: str = Field(..., description="Plan id e.g. plan_starter, plan_professional")


@router.get("/plans")
async def list_plans(
    billing: BillingService = Depends(get_billing_service),
) -> dict[str, Any]:
    """List active billing plans (no auth; public catalog)."""
    plans = await billing.get_plans()
    return {"plans": plans}


@router.get("/subscription")
async def get_subscription(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    billing: BillingService = Depends(get_billing_service),
    _: None = require_role(*ROLES_OWNER_OR_ADMIN),
) -> dict[str, Any]:
    """Current tenant subscription; ensures default if none."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    sub = await billing.ensure_default_subscription(x_tenant_id)
    if not sub:
        raise HTTPException(404, "No subscription")
    return {"subscription": sub}


@router.post("/subscription", status_code=201)
async def create_or_update_subscription(
    body: CreateSubscriptionBody,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    billing: BillingService = Depends(get_billing_service),
    _: None = require_role(*ROLES_OWNER_ONLY),
) -> dict[str, Any]:
    """Create subscription if none, or update to new plan."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    try:
        sub = await billing.get_subscription(x_tenant_id)
        if sub:
            updated = await billing.update_subscription(x_tenant_id, body.plan_id)
            return {"subscription": updated, "updated": True}
        await billing.create_subscription(x_tenant_id, body.plan_id)
        new_sub = await billing.get_subscription(x_tenant_id)
        return {"subscription": new_sub, "updated": False}
    except ValueError as e:
        raise HTTPException(400, str(e)) from e


@router.delete("/subscription", status_code=204)
async def cancel_subscription(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    billing: BillingService = Depends(get_billing_service),
    _: None = require_role(*ROLES_OWNER_ONLY),
) -> None:
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    cancelled = await billing.cancel_subscription(x_tenant_id)
    if not cancelled:
        raise HTTPException(404, "No active subscription")


@router.get("/usage")
async def get_usage(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
    period: str | None = None,
    billing: BillingService = Depends(get_billing_service),
    _: None = require_role(*ROLES_OWNER_OR_ADMIN),
) -> dict[str, Any]:
    """Current period usage and costs. period=YYYY-MM optional."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    await billing.ensure_default_subscription(x_tenant_id)
    data = await billing.get_usage(x_tenant_id, period=period)
    limit = await billing.get_llm_limit(x_tenant_id)
    return {
        "usage": data,
        "limits": {"llm_tokens_monthly": limit} if limit else {"llm_tokens_monthly": None},
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
) -> JSONResponse:
    """Stripe webhook: subscription.updated, subscription.deleted. Verifies signature."""
    from apps.api.app.core.settings import get_settings
    from apps.api.app.db.billing import (
        cancel_subscription as db_cancel_subscription,
        get_tenant_by_stripe_subscription_id,
        update_subscription_status,
    )
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        return JSONResponse(status_code=501, content={"error": "Webhook not configured"})
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        import stripe
        event = stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid webhook signature"})
    sid = None
    if event.type == "subscription.updated":
        sub = event.data.object
        sid = sub.get("id")
        status = sub.get("status")
        status_map = {"active": "active", "past_due": "past_due", "canceled": "cancelled", "trialing": "trialing"}
        our_status = status_map.get(status, "active")
        # Cross-tenant lookup: get_tenant_by_stripe_subscription_id queries by subscription id; RLS not applied for this lookup.
        async with tenant_conn("") as conn:
            row = await get_tenant_by_stripe_subscription_id(conn, sid)
        if row:
            tenant_id, subscription_id = row
            # Stripe webhooks resolve tenant from subscription; use resolved tenant_id for RLS context
            async with tenant_conn(tenant_id) as conn:
                await update_subscription_status(conn, tenant_id, subscription_id, our_status)
    elif event.type == "subscription.deleted":
        sub = event.data.object
        sid = sub.get("id")
        # Cross-tenant lookup: resolve tenant from subscription id (see subscription.updated above).
        async with tenant_conn("") as conn:
            row = await get_tenant_by_stripe_subscription_id(conn, sid)
        if row:
            tenant_id, subscription_id = row
            # Stripe webhooks resolve tenant from subscription; use resolved tenant_id for RLS context
            async with tenant_conn(tenant_id) as conn:
                await db_cancel_subscription(conn, tenant_id, subscription_id)
    return JSONResponse(content={"received": True})
