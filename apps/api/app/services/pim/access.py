"""PIM access gate.

Every PIM endpoint must call check_pim_access(tenant_id, conn) as its first
operation. PIM is a licensed feature — tenants without an active subscription
that includes pim: true are denied with HTTP 403.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException


async def check_pim_access(tenant_id: str, conn: Any) -> None:
    """Raise HTTP 403 if the tenant's active subscription does not include PIM.

    Queries billing_subscriptions joined with billing_plans to check
    features_json->>'pim'. A missing or inactive subscription, or a plan
    without pim: true, is treated as no access.
    """
    row = await conn.fetchrow(
        """SELECT (bp.features_json->>'pim')::boolean AS pim_enabled
           FROM billing_subscriptions bs
           JOIN billing_plans bp ON bp.plan_id = bs.plan_id
           WHERE bs.tenant_id = $1 AND bs.status IN ('active', 'trialing')
           ORDER BY bs.created_at DESC
           LIMIT 1""",
        tenant_id,
    )
    if not row or not row["pim_enabled"]:
        raise HTTPException(403, "PIM is not enabled for this tenant's subscription")
