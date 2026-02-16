"""VA-P8-04: Connector marketplace — list available connectors (QuickBooks, Xero) and config schema."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from apps.api.app.deps import require_role, ROLES_ANY

router = APIRouter(prefix="/connectors", tags=["connectors"], dependencies=[require_role(*ROLES_ANY)])

CONNECTOR_REGISTRY: list[dict[str, Any]] = [
    {
        "connector_id": "quickbooks",
        "name": "QuickBooks Online",
        "description": "Sync chart of accounts and actuals into budget actuals.",
        "config_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "features": ["chart_of_accounts", "actuals_sync"],
    },
    {
        "connector_id": "xero",
        "name": "Xero",
        "description": "Sync trial balance and P&L into canonical snapshot.",
        "config_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "features": ["chart_of_accounts", "trial_balance", "sync"],
    },
]


@router.get("")
async def list_connectors(
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """List available connectors (VA-P8-04). Use /integrations/connections for connect/disconnect/sync."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    return {"connectors": CONNECTOR_REGISTRY}


@router.get("/{connector_id}")
async def get_connector(
    connector_id: str,
    x_tenant_id: str = Header("", alias="X-Tenant-ID"),
) -> dict[str, Any]:
    """Get connector metadata and config schema by id (VA-P8-04)."""
    if not x_tenant_id:
        raise HTTPException(400, "X-Tenant-ID required")
    for c in CONNECTOR_REGISTRY:
        if c["connector_id"] == connector_id:
            return c
    raise HTTPException(404, "Connector not found")
