# Phase 4 Prompt — ERP Integrations + Billing

## Pre-requisites
- Phase 3 gate passed
- Read: `AUTH_AND_TENANCY.md` (RLS policies)
- Schemas: `integration_connection_v1`, `integration_sync_run_v1`, `canonical_sync_snapshot_v1`, `erp_discovery_session_v1`, `billing_plan_v1`, `billing_subscription_v1`, `usage_meter_v1`
- Apply migration: `0004_integrations_billing_llm.sql`

## Tasks

### 1. Migration 0004
The migration file must create tables for:
- `integration_connections` (tenant_id, connection_id, provider, status, oauth_data_encrypted, last_sync_at, created_at, created_by)
- `integration_sync_runs` (tenant_id, sync_run_id, connection_id, started_at, completed_at, status, records_synced, error_details)
- `canonical_sync_snapshots` (tenant_id, snapshot_id, connection_id, as_of, storage_path, created_at)
- `erp_discovery_sessions` (tenant_id, discovery_id, connection_id, status, storage_path, created_at)
- `billing_plans` (plan_id, label, limits_json, pricing_json, status, created_at)
- `billing_subscriptions` (tenant_id, subscription_id, plan_id, status, stripe_subscription_id, current_period_start, current_period_end, created_at)
- `usage_meters` (tenant_id, period, usage_json, costs_json, updated_at)
- `llm_call_logs` (tenant_id, call_id, task_label, provider, model, tokens_json, latency_ms, cost_estimate_usd, correlation_json, created_at)
- `llm_routing_policies` (policy_id, rules_json, fallback_json, created_at)

Add RLS policies to ALL tables (per AUTH_AND_TENANCY.md pattern).
Add indexes on (tenant_id, status) and (tenant_id, connection_id) as appropriate.
Seed billing_plans with Starter, Professional, Enterprise tiers per PRICING_AND_GTM.md.

### 2. Integration Framework
```
File: apps/api/app/services/integrations/base.py

Abstract adapter:
  class ERPAdapter(ABC):
    async def connect(self, oauth_code: str) -> ConnectionResult
    async def refresh_token(self) -> str
    async def discover(self) -> DiscoveryResult
    async def sync(self, period_start: date, period_end: date) -> SyncResult
    async def disconnect(self) -> None

ConnectionResult: { access_token, refresh_token, expires_at, org_name }
DiscoveryResult: { chart_of_accounts, periods_available, features }
SyncResult: { records_synced, canonical_snapshot: dict, errors: list }
```

### 3. Xero Adapter
```
File: apps/api/app/services/integrations/xero.py

OAuth2 flow:
  1. Redirect to https://login.xero.com/identity/connect/authorize
  2. Callback: exchange code for tokens
  3. Store encrypted in integration_connections

Sync:
  - GET /api.xro/2.0/Reports/TrialBalance
  - GET /api.xro/2.0/Reports/ProfitAndLoss
  - GET /api.xro/2.0/Reports/BalanceSheet
  Map Xero account types (REVENUE, EXPENSE, ASSET, LIABILITY, EQUITY) to canonical types.
  Store as canonical_sync_snapshot_v1.
```

### 4. QBO Adapter
```
File: apps/api/app/services/integrations/qbo.py

Same pattern as Xero but using Intuit OAuth2 + QuickBooks API.
  - GET /v3/company/{id}/reports/TrialBalance
  Map QBO account types to canonical.
```

### 5. Integration API Routes
```
File: apps/api/app/routers/integrations.py

POST /api/v1/integrations/connections — initiate OAuth (returns redirect URL)
GET /api/v1/integrations/connections/callback — OAuth callback handler
GET /api/v1/integrations/connections — list connections
GET /api/v1/integrations/connections/{id} — connection details
POST /api/v1/integrations/connections/{id}/sync — trigger sync
GET /api/v1/integrations/connections/{id}/snapshots — list snapshots
POST /api/v1/integrations/connections/{id}/discover — run discovery
DELETE /api/v1/integrations/connections/{id} — disconnect

Auth: require_role("owner", "admin") for all integration routes.
```

### 6. Billing Service
```
File: apps/api/app/services/billing.py

Plan management:
  get_plans() -> list[BillingPlan]
  get_subscription(tenant_id) -> BillingSubscription
  create_subscription(tenant_id, plan_id) -> BillingSubscription
  update_subscription(tenant_id, new_plan_id) -> BillingSubscription
  cancel_subscription(tenant_id) -> None

Limit enforcement:
  check_limit(tenant_id, resource: str, amount: int) -> bool
  Resources: "llm_tokens", "sync_events", "mc_simulations", "seats", "entities", "connectors"

Stripe integration:
  Create customer on tenant creation
  Create subscription on plan selection
  Report metered usage via Stripe usage records
  Handle webhooks: invoice.paid, subscription.updated, subscription.deleted

File: apps/api/app/routers/billing.py
  GET /api/v1/billing/plans
  GET /api/v1/billing/subscription
  POST /api/v1/billing/subscription — create or update
  GET /api/v1/billing/usage — current period usage
  POST /api/v1/billing/webhook — Stripe webhook handler
```

### 7. Integration + Billing UI
```
apps/web/app/integrations/page.tsx — connection list + "Add Connection" button
apps/web/app/integrations/connect/page.tsx — provider selection → OAuth flow
apps/web/app/integrations/[id]/page.tsx — connection detail + sync history + trigger sync
apps/web/app/settings/billing/page.tsx — current plan, usage meters, upgrade/downgrade
```

### 8. Tests
Per TESTING_STRATEGY.md Phase 4 section.

## Verification
Verify Phase 4 gate criteria from BUILD_PLAN.md.
