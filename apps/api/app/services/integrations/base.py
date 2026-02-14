"""Abstract ERP adapter: connect, discover, sync, disconnect."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date


@dataclass
class ConnectionResult:
    access_token: str
    refresh_token: str
    expires_at: str
    org_name: str | None = None
    provider_tenant_id: str | None = None  # e.g. Xero tenant id for API calls


@dataclass
class DiscoveryResult:
    chart_of_accounts: list[dict]
    periods_available: list[dict]
    features: dict


@dataclass
class SyncResult:
    records_synced: int
    canonical_snapshot: dict
    errors: list[str]


class ERPAdapter(ABC):
    """Provider-specific adapter for OAuth2 connection and sync."""

    @abstractmethod
    async def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """Return the OAuth2 authorize URL for the user to visit."""
        ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> ConnectionResult:
        """Exchange authorization code for tokens."""
        ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        """Return (new_access_token, new_refresh_token)."""
        ...

    @abstractmethod
    async def discover(self, access_token: str, tenant_id: str | None = None) -> DiscoveryResult:
        """Probe connected ERP for chart of accounts and periods."""
        ...

    @abstractmethod
    async def sync(
        self,
        access_token: str,
        period_start: date | None,
        period_end: date | None,
        tenant_id: str | None = None,
    ) -> SyncResult:
        """Pull trial balance / P&L / BS and return canonical snapshot."""
        ...

    async def disconnect(self, access_token: str) -> None:
        """Optional: revoke tokens or disconnect. No-op by default."""
        pass
