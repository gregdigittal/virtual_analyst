-- 0004_integrations_billing_llm.sql
-- ERP integrations, billing, and LLM governance tables for Phase 4

-- ============================================================
-- ERP INTEGRATIONS
-- ============================================================

create table if not exists integration_connections (
  tenant_id text not null references tenants(id) on delete cascade,
  connection_id text not null,
  provider text not null check (provider in ('xero', 'quickbooks', 'sage', 'manual')),
  status text not null check (status in ('pending', 'connected', 'error', 'disconnected')) default 'pending',
  org_name text,
  oauth_data_encrypted bytea,  -- encrypted JSON: { access_token, refresh_token, expires_at, scope }
  last_sync_at timestamptz,
  sync_schedule_minutes integer default 1440,  -- default: daily
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, connection_id)
);
create index if not exists idx_integration_connections_status on integration_connections(tenant_id, status);

create table if not exists integration_sync_runs (
  tenant_id text not null references tenants(id) on delete cascade,
  sync_run_id text not null,
  connection_id text not null,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null check (status in ('running', 'succeeded', 'failed', 'partial')) default 'running',
  records_synced integer default 0,
  snapshot_id text,  -- reference to canonical_sync_snapshot
  error_details text,
  created_at timestamptz not null default now(),
  primary key (tenant_id, sync_run_id),
  foreign key (tenant_id, connection_id)
    references integration_connections(tenant_id, connection_id)
    on delete cascade
);
create index if not exists idx_sync_runs_connection on integration_sync_runs(tenant_id, connection_id);
create index if not exists idx_sync_runs_status on integration_sync_runs(tenant_id, status);

create table if not exists canonical_sync_snapshots (
  tenant_id text not null references tenants(id) on delete cascade,
  snapshot_id text not null,
  connection_id text not null,
  as_of timestamptz not null,
  period_start date,
  period_end date,
  storage_path text not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, snapshot_id),
  foreign key (tenant_id, connection_id)
    references integration_connections(tenant_id, connection_id)
    on delete cascade
);
create index if not exists idx_snapshots_connection on canonical_sync_snapshots(tenant_id, connection_id);

create table if not exists erp_discovery_sessions (
  tenant_id text not null references tenants(id) on delete cascade,
  discovery_id text not null,
  connection_id text not null,
  status text not null check (status in ('running', 'completed', 'failed')) default 'running',
  storage_path text not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, discovery_id),
  foreign key (tenant_id, connection_id)
    references integration_connections(tenant_id, connection_id)
    on delete cascade
);

-- ============================================================
-- BILLING
-- ============================================================

create table if not exists billing_plans (
  plan_id text primary key,
  label text not null,
  tier text not null check (tier in ('starter', 'professional', 'enterprise')),
  limits_json jsonb not null,
  pricing_json jsonb not null,
  features_json jsonb,
  status text not null check (status in ('active', 'deprecated')) default 'active',
  created_at timestamptz not null default now()
);

create table if not exists billing_subscriptions (
  tenant_id text not null references tenants(id) on delete cascade,
  subscription_id text not null,
  plan_id text not null references billing_plans(plan_id),
  status text not null check (status in ('active', 'past_due', 'cancelled', 'trialing')) default 'active',
  stripe_customer_id text,
  stripe_subscription_id text,
  current_period_start timestamptz not null,
  current_period_end timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, subscription_id)
);
create index if not exists idx_subscriptions_status on billing_subscriptions(tenant_id, status);

create table if not exists usage_meters (
  tenant_id text not null references tenants(id) on delete cascade,
  period text not null,  -- YYYY-MM format
  usage_json jsonb not null default '{}'::jsonb,
  costs_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, period)
);

-- ============================================================
-- LLM GOVERNANCE
-- ============================================================

create table if not exists llm_call_logs (
  tenant_id text not null references tenants(id) on delete cascade,
  call_id text not null,
  task_label text not null,
  provider text not null,
  model text not null,
  tokens_json jsonb not null,  -- { prompt_tokens, completion_tokens, total_tokens }
  latency_ms integer not null,
  cost_estimate_usd numeric(10, 6) not null,
  status text not null check (status in ('success', 'error', 'timeout')) default 'success',
  error_message text,
  retry_count integer not null default 0,
  correlation_json jsonb,  -- { draft_session_id, user_id, request_id, run_id, memo_id }
  created_at timestamptz not null default now(),
  primary key (tenant_id, call_id)
);
create index if not exists idx_llm_logs_task on llm_call_logs(tenant_id, task_label);
create index if not exists idx_llm_logs_created on llm_call_logs(tenant_id, created_at);

create table if not exists llm_routing_policies (
  policy_id text primary key,
  tenant_id text references tenants(id) on delete cascade,  -- null = platform default
  rules_json jsonb not null,
  fallback_json jsonb not null,
  created_at timestamptz not null default now()
);

-- ============================================================
-- RLS POLICIES
-- ============================================================

alter table integration_connections enable row level security;
create policy "integration_connections_select" on integration_connections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_insert" on integration_connections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_update" on integration_connections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_delete" on integration_connections for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table integration_sync_runs enable row level security;
create policy "integration_sync_runs_select" on integration_sync_runs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_sync_runs_insert" on integration_sync_runs for insert with check (tenant_id = current_setting('app.tenant_id', true));

alter table canonical_sync_snapshots enable row level security;
create policy "canonical_sync_snapshots_select" on canonical_sync_snapshots for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "canonical_sync_snapshots_insert" on canonical_sync_snapshots for insert with check (tenant_id = current_setting('app.tenant_id', true));

alter table erp_discovery_sessions enable row level security;
create policy "erp_discovery_sessions_select" on erp_discovery_sessions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "erp_discovery_sessions_insert" on erp_discovery_sessions for insert with check (tenant_id = current_setting('app.tenant_id', true));

alter table billing_subscriptions enable row level security;
create policy "billing_subscriptions_select" on billing_subscriptions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "billing_subscriptions_insert" on billing_subscriptions for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "billing_subscriptions_update" on billing_subscriptions for update using (tenant_id = current_setting('app.tenant_id', true));

alter table usage_meters enable row level security;
create policy "usage_meters_select" on usage_meters for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "usage_meters_insert" on usage_meters for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "usage_meters_update" on usage_meters for update using (tenant_id = current_setting('app.tenant_id', true));

alter table llm_call_logs enable row level security;
create policy "llm_call_logs_select" on llm_call_logs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "llm_call_logs_insert" on llm_call_logs for insert with check (tenant_id = current_setting('app.tenant_id', true));

alter table llm_routing_policies enable row level security;
create policy "llm_routing_policies_select" on llm_routing_policies for select using (
  tenant_id = current_setting('app.tenant_id', true) or tenant_id is null
);

-- ============================================================
-- SEED BILLING PLANS
-- ============================================================

insert into billing_plans (plan_id, label, tier, limits_json, pricing_json, features_json) values
(
  'plan_starter',
  'Starter',
  'starter',
  '{"seats": 2, "entities": 1, "llm_tokens_monthly": 500000, "mc_simulations_per_run": 100, "mc_runs_monthly": 10, "connectors": 0, "excel_connections": 0, "memo_pages_monthly": 0, "storage_gb": 1}',
  '{"currency": "USD", "base_monthly": 0, "per_seat_monthly": null, "custom_pricing": false}',
  '{"draft_llm": true, "monte_carlo": false, "valuation": false, "erp_sync": false, "excel_live_links": false, "memo_packs": false, "byo_api_key": false, "sso": false, "audit_log": false, "priority_support": false}'
),
(
  'plan_professional',
  'Professional',
  'professional',
  '{"seats": 10, "entities": 5, "llm_tokens_monthly": 5000000, "mc_simulations_per_run": 10000, "mc_runs_monthly": 100, "connectors": 3, "excel_connections": 5, "memo_pages_monthly": 100, "storage_gb": 10}',
  '{"currency": "USD", "base_monthly": 9900, "per_seat_monthly": 2900, "per_entity_monthly": 1900, "custom_pricing": false}',
  '{"draft_llm": true, "monte_carlo": true, "valuation": true, "erp_sync": true, "excel_live_links": true, "memo_packs": true, "byo_api_key": false, "sso": false, "audit_log": false, "priority_support": false}'
),
(
  'plan_enterprise',
  'Enterprise',
  'enterprise',
  '{"seats": 0, "entities": 0, "llm_tokens_monthly": 0, "mc_simulations_per_run": 0, "mc_runs_monthly": 0, "connectors": 0, "excel_connections": 0, "memo_pages_monthly": 0, "storage_gb": 0}',
  '{"currency": "USD", "base_monthly": 0, "custom_pricing": true}',
  '{"draft_llm": true, "monte_carlo": true, "valuation": true, "erp_sync": true, "excel_live_links": true, "memo_packs": true, "byo_api_key": true, "sso": true, "audit_log": true, "priority_support": true}'
)
on conflict (plan_id) do nothing;

-- Seed default routing policy
insert into llm_routing_policies (policy_id, tenant_id, rules_json, fallback_json) values
(
  'policy_default',
  null,
  '[
    {"task_label": "draft_assumptions", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "standard"},
    {"task_label": "draft_assumptions", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "standard"},
    {"task_label": "evidence_extraction", "priority": 1, "provider": "anthropic", "model": "claude-haiku-4-5-20251001", "max_tokens": 2048, "temperature": 0.1, "cost_tier": "low"},
    {"task_label": "memo_generation", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 8192, "temperature": 0.3, "cost_tier": "standard"},
    {"task_label": "template_matching", "priority": 1, "provider": "anthropic", "model": "claude-haiku-4-5-20251001", "max_tokens": 2048, "temperature": 0.1, "cost_tier": "low"},
    {"task_label": "template_initialization", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "standard"}
  ]',
  '{"provider": "openai", "model": "gpt-4o-mini", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "low"}'
)
on conflict (policy_id) do nothing;
