"""QuickBooks Online adapter (VA-P8-04): OAuth2 and sync to canonical snapshot / budget actuals."""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlencode

import httpx

from apps.api.app.core.settings import get_settings

INTEGRATION_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
from apps.api.app.services.integrations.base import (
    ConnectionResult,
    DiscoveryResult,
    ERPAdapter,
    SyncResult,
)

QB_BASE = "https://appcenter.intuit.com/connect/oauth2"
QB_TOKEN = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QB_API = "https://quickbooks.api.intuit.com/v3"
QB_SCOPES = "com.intuit.quickbooks.accounting"


class QuickBooksAdapter(ERPAdapter):
    """QuickBooks Online OAuth2 and API adapter."""

    def __init__(self) -> None:
        settings = get_settings()
        self.client_id = settings.quickbooks_client_id or ""
        self.client_secret = settings.quickbooks_client_secret or ""

    async def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "scope": QB_SCOPES,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return f"{QB_BASE}?{urlencode(params)}"

    async def exchange_code(self, code: str, redirect_uri: str) -> ConnectionResult:
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=INTEGRATION_TIMEOUT) as client:
            r = await client.post(
                QB_TOKEN,
                headers={
                    "Authorization": f"Basic {basic}",
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
        access = data["access_token"]
        refresh = data.get("refresh_token", "")
        expires_in = int(data.get("expires_in", 3600))
        expires_at = str(int(datetime.now(UTC).timestamp()) + expires_in)
        realm_id = data.get("realmId", "")
        return ConnectionResult(
            access_token=access,
            refresh_token=refresh,
            expires_at=expires_at,
            org_name=None,
            provider_tenant_id=realm_id or None,
        )

    async def refresh_token(self, refresh_token: str) -> tuple[str, str]:
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        async with httpx.AsyncClient(timeout=INTEGRATION_TIMEOUT) as client:
            r = await client.post(
                QB_TOKEN,
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            )
            r.raise_for_status()
            data = r.json()
        return data["access_token"], data.get("refresh_token", refresh_token)

    async def discover(self, access_token: str, tenant_id: str | None = None) -> DiscoveryResult:
        realm = tenant_id or ""
        if not realm:
            return DiscoveryResult(chart_of_accounts=[], periods_available=[], features={})
        async with httpx.AsyncClient(timeout=INTEGRATION_TIMEOUT) as client:
            r = await client.get(
                f"{QB_API}/company/{realm}/query",
                params={"query": "SELECT * FROM Account MAXRESULTS 1000"},
                headers={"Authorization": f"Bearer {access_token}"},
            )
            r.raise_for_status()
            data = r.json()
        accounts = data.get("QueryResponse", {}).get("Account", [])
        chart = [{"id": a.get("Id"), "name": a.get("Name"), "type": a.get("AccountType")} for a in accounts]
        return DiscoveryResult(
            chart_of_accounts=chart,
            periods_available=[],
            features={"chart_of_accounts": True},
        )

    async def sync(
        self,
        access_token: str,
        period_start: date | None,
        period_end: date | None,
        tenant_id: str | None = None,
    ) -> SyncResult:
        realm = tenant_id or ""
        errors: list[str] = []
        canonical: dict[str, Any] = {"as_of": datetime.now(UTC).isoformat(), "trial_balance": [], "source": "quickbooks"}
        if not realm:
            return SyncResult(records_synced=0, canonical_snapshot=canonical, errors=["No realm_id"])
        try:
            async with httpx.AsyncClient(timeout=INTEGRATION_TIMEOUT) as client:
                r = await client.get(
                    f"{QB_API}/company/{realm}/reports/ProfitAndLoss",
                    params={"start_date": str(period_start), "end_date": str(period_end)},
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                if r.status_code == 200:
                    report = r.json()
                    rows = report.get("Rows", {}).get("Row", [])
                    if isinstance(rows, dict):
                        rows = [rows]
                    for row in rows:
                        group = row.get("group")
                        summary = row.get("Summary", {})
                        if group:
                            for col in row.get("Columns", {}).get("Column", []):
                                canonical["trial_balance"].append(
                                    {"label": group.get("value", ""), "value": col.get("value"), "type": "section"}
                                )
                        elif summary:
                            canonical["trial_balance"].append(
                                {"label": summary.get("ColData", [{}])[0].get("value", ""), "value": summary.get("ColData", [{}])[-1].get("value")}
                            )
                else:
                    errors.append(f"P&L report: {r.status_code}")
        except Exception as e:
            errors.append(str(e))
        return SyncResult(
            records_synced=len(canonical.get("trial_balance", [])),
            canonical_snapshot=canonical,
            errors=errors,
        )
