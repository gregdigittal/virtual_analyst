"""Xero ERP adapter: OAuth2 and sync to canonical snapshot."""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from apps.api.app.core.settings import get_settings
from apps.api.app.services.integrations.base import (
    ConnectionResult,
    DiscoveryResult,
    ERPAdapter,
    SyncResult,
)

XERO_AUTHORIZE = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN = "https://identity.xero.com/connect/token"
XERO_API = "https://api.xero.com/api.xro/2.0"
XERO_SCOPE = "openid profile email accounting.reports.read accounting.settings.read"


class XeroAdapter(ERPAdapter):
    """Xero OAuth2 and Reports API adapter."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client_id = settings.xero_client_id or ""
        self.client_secret = settings.xero_client_secret or ""

    async def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "response_type": "code",
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": XERO_SCOPE,
            "state": state,
        }
        return f"{XERO_AUTHORIZE}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> ConnectionResult:
        token_basic = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                XERO_TOKEN,
                headers={
                    "Authorization": f"Basic {token_basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
            )
            r.raise_for_status()
            data = r.json()

            expires_in = int(data.get("expires_in", 1800))
            expires_at = datetime.now(UTC).timestamp() + expires_in
            access_token = data["access_token"]
            refresh_token_val = data["refresh_token"]

            # Xero requires a separate call to discover connected tenants
            org_name = None
            tenant_id = ""
            try:
                conns_resp = await client.get(
                    "https://api.xero.com/connections",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if conns_resp.status_code == 200:
                    connections = conns_resp.json()
                    if isinstance(connections, list) and connections:
                        first = connections[0]
                        org_name = first.get("tenantName")
                        tenant_id = first.get("tenantId", "")
            except Exception:
                pass  # Proceed without tenant info; sync will fail later if needed

        return ConnectionResult(
            access_token=access_token,
            refresh_token=refresh_token_val,
            expires_at=str(int(expires_at)),
            org_name=org_name,
            provider_tenant_id=tenant_id or None,
        )

    async def refresh_token(self, refresh_token: str) -> str:
        token_basic = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode()
        ).decode()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                XERO_TOKEN,
                headers={
                    "Authorization": f"Basic {token_basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )
            r.raise_for_status()
            data = r.json()
        return data["access_token"], data.get("refresh_token", refresh_token)

    async def discover(self, access_token: str, tenant_id: str | None = None) -> DiscoveryResult:
        xero_tenant = tenant_id
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{XERO_API}/Accounts",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Xero-tenant-id": xero_tenant or "",
                },
            )
            r.raise_for_status()
            data = r.json()
        accounts = data.get("Accounts", [])
        chart = [{"id": a.get("AccountID"), "name": a.get("Name"), "type": a.get("Type")} for a in accounts]
        return DiscoveryResult(
            chart_of_accounts=chart,
            periods_available=[],
            features={"accounts_count": len(chart)},
        )

    async def sync(
        self,
        access_token: str,
        period_start: date | None,
        period_end: date | None,
        tenant_id: str | None = None,
    ) -> SyncResult:
        xero_tenant = tenant_id
        errors: list[str] = []
        canonical: dict[str, Any] = {
            "artifact_type": "canonical_sync_snapshot_v1",
            "provider": "xero",
            "as_of": datetime.now(UTC).isoformat(),
            "period_start": period_start.isoformat() if period_start else None,
            "period_end": period_end.isoformat() if period_end else None,
            "accounts": [],
            "trial_balance": [],
            "pl": [],
            "balance_sheet": [],
        }
        async with httpx.AsyncClient() as client:
            headers = {"Authorization": f"Bearer {access_token}", "Xero-tenant-id": xero_tenant or ""}
            date_param = f"date={period_end or date.today()}" if (period_end or period_start) else ""
            try:
                tb = await client.get(
                    f"{XERO_API}/Reports/TrialBalance?{date_param}",
                    headers=headers,
                )
                if tb.status_code == 200:
                    data = tb.json()
                    rows = data.get("Reports", [{}])[0].get("Rows", [])
                    for row in rows:
                        if row.get("RowType") == "Section":
                            for r in row.get("Rows", []):
                                if r.get("RowType") == "Row":
                                    cells = r.get("Cells", [])
                                    if len(cells) >= 3:
                                        canonical["trial_balance"].append({
                                            "account": cells[0].get("Value"),
                                            "value": cells[1].get("Value"),
                                            "type": _map_xero_type(cells[0].get("Attributes", [{}])[0].get("Value") if cells[0].get("Attributes") else ""),
                                        })
                else:
                    errors.append(f"TrialBalance: {tb.status_code}")
            except Exception as e:
                errors.append(f"TrialBalance: {str(e)}")
            try:
                pl = await client.get(
                    f"{XERO_API}/Reports/ProfitAndLoss?{date_param}",
                    headers=headers,
                )
                if pl.status_code == 200:
                    data = pl.json()
                    canonical["pl"] = data.get("Reports", [])
                else:
                    errors.append(f"ProfitAndLoss: {pl.status_code}")
            except Exception as e:
                errors.append(f"ProfitAndLoss: {str(e)}")
        records = len(canonical["trial_balance"]) + (1 if canonical["pl"] else 0)
        return SyncResult(
            records_synced=records,
            canonical_snapshot=canonical,
            errors=errors,
        )


def _map_xero_type(xero_type: str) -> str:
    m = {"REVENUE": "revenue", "EXPENSE": "expense", "ASSET": "asset", "LIABILITY": "liability", "EQUITY": "equity"}
    return m.get(xero_type.upper(), "other")
