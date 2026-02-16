"""ERP integration adapters: OAuth2 connection and sync to canonical snapshot."""

from __future__ import annotations

from apps.api.app.services.integrations.base import (
    ConnectionResult,
    DiscoveryResult,
    ERPAdapter,
    SyncResult,
)
from apps.api.app.services.integrations.quickbooks import QuickBooksAdapter
from apps.api.app.services.integrations.xero import XeroAdapter


def get_adapter(provider: str) -> ERPAdapter | None:
    """Return the adapter for the given provider, or None if unknown (VA-P8-04)."""
    if provider == "xero":
        return XeroAdapter()
    if provider == "quickbooks":
        return QuickBooksAdapter()
    return None


__all__ = [
    "ERPAdapter",
    "ConnectionResult",
    "DiscoveryResult",
    "SyncResult",
    "XeroAdapter",
    "QuickBooksAdapter",
    "get_adapter",
]
