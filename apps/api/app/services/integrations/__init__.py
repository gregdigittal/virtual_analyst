"""ERP integration adapters: OAuth2 connection and sync to canonical snapshot."""

from __future__ import annotations

from apps.api.app.services.integrations.base import (
    ConnectionResult,
    DiscoveryResult,
    ERPAdapter,
    SyncResult,
)
from apps.api.app.services.integrations.xero import XeroAdapter


def get_adapter(provider: str) -> ERPAdapter | None:
    """Return the adapter for the given provider, or None if unknown."""
    if provider == "xero":
        return XeroAdapter()
    return None


__all__ = [
    "ERPAdapter",
    "ConnectionResult",
    "DiscoveryResult",
    "SyncResult",
    "XeroAdapter",
    "get_adapter",
]
