-- =============================================================================
-- Virtual Analyst — APPLY ALL MIGRATIONS (0008 through 0046)
-- =============================================================================
-- Run this single script against your database to apply all pending migrations.
-- Prerequisites: 0001_init.sql and 0002_functions_and_rls.sql must already be applied.
--
-- Usage: psql "$DATABASE_URL" -f APPLY_ALL_MIGRATIONS.sql
-- =============================================================================

-- ############################################################################
-- 0008_notifications.sql
-- ############################################################################
-- In-app notifications for key events (draft ready, run complete, etc.)

create table if not exists notifications (
  id uuid primary key default gen_random_uuid(),
  tenant_id text not null references tenants(id) on delete cascade,
  user_id text references users(id) on delete cascade,
  type text not null,
  title text not null,
  body text,
  entity_type text,
  entity_id text,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create index if not exists idx_notifications_tenant_unread on notifications(tenant_id, read_at) where read_at is null;
create index if not exists idx_notifications_tenant_created on notifications(tenant_id, created_at desc);
create index if not exists idx_notifications_user_unread on notifications(tenant_id, user_id, read_at) where read_at is null;

alter table notifications enable row level security;
drop policy if exists "notifications_select" on notifications;
create policy "notifications_select" on notifications for select
  using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_insert" on notifications;
create policy "notifications_insert" on notifications for insert
  with check (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_update" on notifications;
create policy "notifications_update" on notifications for update
  using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "notifications_delete" on notifications;
create policy "notifications_delete" on notifications for delete
  using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0009_runs_async_mc.sql
-- ############################################################################
alter table runs add column if not exists task_id text;
alter table runs add column if not exists mc_enabled boolean not null default false;
alter table runs add column if not exists num_simulations integer;
alter table runs add column if not exists seed integer;
alter table runs add column if not exists valuation_config_json jsonb;
alter table runs add column if not exists completed_at timestamptz;
alter table runs add column if not exists error_message text;

-- ############################################################################
-- 0010_scenarios.sql
-- ############################################################################
create table if not exists scenarios (
  tenant_id text not null references tenants(id) on delete cascade,
  scenario_id text not null,
  baseline_id text not null,
  baseline_version text not null,
  label text not null,
  description text,
  overrides_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, scenario_id),
  foreign key (tenant_id, baseline_id, baseline_version)
    references model_baselines(tenant_id, baseline_id, baseline_version)
    on delete cascade
);
create index if not exists idx_scenarios_baseline on scenarios(tenant_id, baseline_id, baseline_version);

alter table scenarios enable row level security;
drop policy if exists "scenarios_select" on scenarios;
create policy "scenarios_select" on scenarios for select using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "scenarios_insert" on scenarios;
create policy "scenarios_insert" on scenarios for insert with check (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "scenarios_update" on scenarios;
create policy "scenarios_update" on scenarios for update using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "scenarios_delete" on scenarios;
create policy "scenarios_delete" on scenarios for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0011_placeholder.sql — no-op (reserved)
-- ############################################################################

-- ############################################################################
-- 0012_integrations.sql
-- ############################################################################
create table if not exists integration_connections (
  tenant_id text not null references tenants(id) on delete cascade,
  connection_id text not null,
  provider text not null check (provider in ('xero', 'quickbooks', 'sage', 'manual')),
  status text not null check (status in ('pending', 'connected', 'error', 'disconnected')) default 'pending',
  org_name text,
  oauth_data_encrypted bytea,
  last_sync_at timestamptz,
  sync_schedule_minutes integer default 1440,
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
  snapshot_id text,
  error_details text,
  created_at timestamptz not null default now(),
  primary key (tenant_id, sync_run_id),
  foreign key (tenant_id, connection_id)
    references integration_connections(tenant_id, connection_id) on delete cascade
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
    references integration_connections(tenant_id, connection_id) on delete cascade
);
create index if not exists idx_snapshots_connection on canonical_sync_snapshots(tenant_id, connection_id);

alter table integration_connections enable row level security;
alter table integration_sync_runs enable row level security;
alter table canonical_sync_snapshots enable row level security;

drop policy if exists "integration_connections_select" on integration_connections;
drop policy if exists "integration_connections_insert" on integration_connections;
drop policy if exists "integration_connections_update" on integration_connections;
drop policy if exists "integration_connections_delete" on integration_connections;
create policy "integration_connections_select" on integration_connections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_insert" on integration_connections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_update" on integration_connections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_delete" on integration_connections for delete using (tenant_id = current_setting('app.tenant_id', true));

drop policy if exists "integration_sync_runs_select" on integration_sync_runs;
drop policy if exists "integration_sync_runs_insert" on integration_sync_runs;
drop policy if exists "integration_sync_runs_update" on integration_sync_runs;
drop policy if exists "integration_sync_runs_delete" on integration_sync_runs;
create policy "integration_sync_runs_select" on integration_sync_runs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_sync_runs_insert" on integration_sync_runs for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_sync_runs_update" on integration_sync_runs for update using (tenant_id = current_setting('app.tenant_id', true));

drop policy if exists "canonical_snapshots_select" on canonical_sync_snapshots;
drop policy if exists "canonical_snapshots_insert" on canonical_sync_snapshots;
drop policy if exists "canonical_snapshots_delete" on canonical_sync_snapshots;
create policy "canonical_snapshots_select" on canonical_sync_snapshots for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "canonical_snapshots_insert" on canonical_sync_snapshots for insert with check (tenant_id = current_setting('app.tenant_id', true));

drop policy if exists "integration_sync_runs_delete" on integration_sync_runs;
create policy "integration_sync_runs_delete" on integration_sync_runs for delete using (tenant_id = current_setting('app.tenant_id', true));
drop policy if exists "canonical_snapshots_delete" on canonical_sync_snapshots;
create policy "canonical_snapshots_delete" on canonical_sync_snapshots for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0013_billing_usage_llm.sql
-- ############################################################################
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
-- billing_plans is intentionally NOT subject to RLS. It is a global catalog
-- visible to all tenants. Plans are read-only from the application layer. (R8-06)

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
  period text not null,
  usage_json jsonb not null default '{}'::jsonb,
  costs_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, period)
);

create table if not exists llm_call_logs (
  tenant_id text not null references tenants(id) on delete cascade,
  call_id text not null,
  task_label text not null,
  provider text not null,
  model text not null,
  tokens_json jsonb not null,
  latency_ms integer not null,
  cost_estimate_usd numeric(10, 6) not null,
  status text not null check (status in ('success', 'error', 'timeout')) default 'success',
  error_message text,
  retry_count integer not null default 0,
  correlation_json jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, call_id)
);
create index if not exists idx_llm_logs_task on llm_call_logs(tenant_id, task_label);
create index if not exists idx_llm_logs_created on llm_call_logs(tenant_id, created_at);

create table if not exists llm_routing_policies (
  policy_id text primary key,
  tenant_id text references tenants(id) on delete cascade,
  rules_json jsonb not null,
  fallback_json jsonb not null,
  created_at timestamptz not null default now()
);

alter table billing_subscriptions enable row level security;
drop policy if exists "billing_subscriptions_select" on billing_subscriptions;
drop policy if exists "billing_subscriptions_insert" on billing_subscriptions;
drop policy if exists "billing_subscriptions_update" on billing_subscriptions;
create policy "billing_subscriptions_select" on billing_subscriptions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "billing_subscriptions_insert" on billing_subscriptions for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "billing_subscriptions_update" on billing_subscriptions for update using (tenant_id = current_setting('app.tenant_id', true));

alter table usage_meters enable row level security;
drop policy if exists "usage_meters_select" on usage_meters;
drop policy if exists "usage_meters_insert" on usage_meters;
drop policy if exists "usage_meters_update" on usage_meters;
create policy "usage_meters_select" on usage_meters for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "usage_meters_insert" on usage_meters for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "usage_meters_update" on usage_meters for update using (tenant_id = current_setting('app.tenant_id', true));

alter table llm_call_logs enable row level security;
drop policy if exists "llm_call_logs_select" on llm_call_logs;
drop policy if exists "llm_call_logs_insert" on llm_call_logs;
create policy "llm_call_logs_select" on llm_call_logs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "llm_call_logs_insert" on llm_call_logs for insert with check (tenant_id = current_setting('app.tenant_id', true));

alter table llm_routing_policies enable row level security;
drop policy if exists "llm_routing_policies_select" on llm_routing_policies;
create policy "llm_routing_policies_select" on llm_routing_policies for select using (
  tenant_id = current_setting('app.tenant_id', true) or tenant_id is null
);

insert into billing_plans (plan_id, label, tier, limits_json, pricing_json, features_json) values
('plan_starter', 'Starter', 'starter', '{"seats": 2, "entities": 1, "llm_tokens_monthly": 500000, "mc_simulations_per_run": 100, "mc_runs_monthly": 10, "connectors": 0, "excel_connections": 0, "memo_pages_monthly": 0, "storage_gb": 1}', '{"currency": "USD", "base_monthly": 0, "per_seat_monthly": null, "custom_pricing": false}', '{"draft_llm": true, "monte_carlo": false, "valuation": false, "erp_sync": false, "excel_live_links": false, "memo_packs": false, "byo_api_key": false, "sso": false, "audit_log": false, "priority_support": false}'),
('plan_professional', 'Professional', 'professional', '{"seats": 10, "entities": 5, "llm_tokens_monthly": 5000000, "mc_simulations_per_run": 10000, "mc_runs_monthly": 100, "connectors": 3, "excel_connections": 5, "memo_pages_monthly": 100, "storage_gb": 10}', '{"currency": "USD", "base_monthly": 9900, "per_seat_monthly": 2900, "per_entity_monthly": 1900, "custom_pricing": false}', '{"draft_llm": true, "monte_carlo": true, "valuation": true, "erp_sync": true, "excel_live_links": true, "memo_packs": true, "byo_api_key": false, "sso": false, "audit_log": false, "priority_support": false}'),
('plan_enterprise', 'Enterprise', 'enterprise', '{"seats": 0, "entities": 0, "llm_tokens_monthly": 0, "mc_simulations_per_run": 0, "mc_runs_monthly": 0, "connectors": 0, "excel_connections": 0, "memo_pages_monthly": 0, "storage_gb": 0}', '{"currency": "USD", "base_monthly": 0, "custom_pricing": true}', '{"draft_llm": true, "monte_carlo": true, "valuation": true, "erp_sync": true, "excel_live_links": true, "memo_packs": true, "byo_api_key": true, "sso": true, "audit_log": true, "priority_support": true}')
on conflict (plan_id) do nothing;

insert into llm_routing_policies (policy_id, tenant_id, rules_json, fallback_json) values
('policy_default', null, '[{"task_label": "draft_assumptions", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "standard"},{"task_label": "draft_assumptions", "priority": 2, "provider": "openai", "model": "gpt-4o", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "standard"},{"task_label": "evidence_extraction", "priority": 1, "provider": "anthropic", "model": "claude-haiku-4-5-20251001", "max_tokens": 2048, "temperature": 0.1, "cost_tier": "low"},{"task_label": "memo_generation", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 8192, "temperature": 0.3, "cost_tier": "standard"},{"task_label": "template_matching", "priority": 1, "provider": "anthropic", "model": "claude-haiku-4-5-20251001", "max_tokens": 2048, "temperature": 0.1, "cost_tier": "low"},{"task_label": "template_initialization", "priority": 1, "provider": "anthropic", "model": "claude-sonnet-4-5-20250929", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "standard"}]', '{"provider": "openai", "model": "gpt-4o-mini", "max_tokens": 4096, "temperature": 0.2, "cost_tier": "low"}')
on conflict (policy_id) do nothing;

create or replace function get_tenant_by_stripe_subscription(p_stripe_sid text)
returns table(tenant_id text, subscription_id text)
language sql security definer set search_path = public
as $$
  select billing_subscriptions.tenant_id, billing_subscriptions.subscription_id
  from billing_subscriptions
  where billing_subscriptions.stripe_subscription_id = p_stripe_sid
  limit 1;
$$;

create index if not exists idx_billing_subscriptions_stripe_sid
  on billing_subscriptions(stripe_subscription_id)
  where stripe_subscription_id is not null;

-- ############################################################################
-- 0014_audit_log.sql
-- ############################################################################
create table if not exists audit_log (
  audit_event_id text primary key,
  tenant_id text not null,
  user_id text,
  event_type text not null,
  event_category text not null,
  "timestamp" timestamptz not null default now(),
  resource_type text not null,
  resource_id text not null,
  event_data jsonb not null default '{}',
  checksum text not null
);

create index if not exists idx_audit_tenant_time on audit_log(tenant_id, "timestamp" desc);
create index if not exists idx_audit_event_type on audit_log(event_type, "timestamp" desc);
create index if not exists idx_audit_resource on audit_log(resource_type, resource_id);
create index if not exists idx_audit_user_time on audit_log(user_id, "timestamp" desc) where user_id is not null;

alter table audit_log enable row level security;
drop policy if exists "audit_log_insert" on audit_log;
drop policy if exists "audit_log_select" on audit_log;
drop policy if exists "audit_log_update" on audit_log;

create policy "audit_log_insert" on audit_log for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "audit_log_select" on audit_log for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "audit_log_update" on audit_log for update
  using (tenant_id = current_setting('app.tenant_id', true))
  with check (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0015_covenants.sql
-- ############################################################################
create table if not exists covenant_definitions (
  tenant_id text not null references tenants(id) on delete cascade,
  covenant_id text not null,
  label text not null,
  metric_ref text not null,
  operator text not null check (operator in ('<', '>', '<=', '>=')),
  threshold_value double precision not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, covenant_id)
);
create index if not exists idx_covenant_definitions_tenant on covenant_definitions(tenant_id);

alter table covenant_definitions enable row level security;
drop policy if exists "covenant_definitions_select" on covenant_definitions;
drop policy if exists "covenant_definitions_insert" on covenant_definitions;
drop policy if exists "covenant_definitions_update" on covenant_definitions;
drop policy if exists "covenant_definitions_delete" on covenant_definitions;

create policy "covenant_definitions_select" on covenant_definitions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "covenant_definitions_insert" on covenant_definitions for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "covenant_definitions_update" on covenant_definitions for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "covenant_definitions_delete" on covenant_definitions for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table runs add column if not exists covenant_breached boolean not null default false;

-- ############################################################################
-- 0016_excel_and_memos.sql
-- ############################################################################
create table if not exists excel_connections (
  tenant_id text not null references tenants(id) on delete cascade,
  excel_connection_id text not null,
  label text,
  mode text not null check (mode in ('readonly', 'readwrite')) default 'readonly',
  target_json jsonb not null,
  workbook_json jsonb,
  bindings_json jsonb not null default '[]'::jsonb,
  sync_json jsonb,
  permissions_json jsonb,
  status text not null check (status in ('active', 'paused', 'error', 'archived')) default 'active',
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, excel_connection_id)
);
create index if not exists idx_excel_connections_status on excel_connections(tenant_id, status);

create table if not exists excel_sync_events (
  tenant_id text not null references tenants(id) on delete cascade,
  event_id text not null,
  excel_connection_id text not null,
  "timestamp" timestamptz not null default now(),
  direction text not null check (direction in ('pull', 'push')),
  status text not null check (status in ('succeeded', 'failed', 'partial')),
  initiated_by text references users(id) on delete set null,
  bindings_synced integer default 0,
  target_json jsonb,
  diff_json jsonb not null default '{}'::jsonb,
  primary key (tenant_id, event_id),
  foreign key (tenant_id, excel_connection_id)
    references excel_connections(tenant_id, excel_connection_id)
    on delete cascade
);
create index if not exists idx_excel_sync_events_connection on excel_sync_events(tenant_id, excel_connection_id);
create index if not exists idx_excel_sync_events_timestamp on excel_sync_events(tenant_id, "timestamp");

create table if not exists memo_packs (
  tenant_id text not null references tenants(id) on delete cascade,
  memo_id text not null,
  memo_type text not null check (memo_type in ('investment_committee', 'credit_memo', 'valuation_note')),
  title text,
  source_json jsonb not null,
  sections_json jsonb not null default '[]'::jsonb,
  outputs_json jsonb not null default '{}'::jsonb,
  status text not null check (status in ('generating', 'ready', 'error')) default 'generating',
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, memo_id)
);
create index if not exists idx_memo_packs_type on memo_packs(tenant_id, memo_type);
create index if not exists idx_memo_packs_status on memo_packs(tenant_id, status);

alter table excel_connections enable row level security;
drop policy if exists "excel_connections_select" on excel_connections;
drop policy if exists "excel_connections_insert" on excel_connections;
drop policy if exists "excel_connections_update" on excel_connections;
drop policy if exists "excel_connections_delete" on excel_connections;
create policy "excel_connections_select" on excel_connections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "excel_connections_insert" on excel_connections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "excel_connections_update" on excel_connections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "excel_connections_delete" on excel_connections for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table excel_sync_events enable row level security;
drop policy if exists "excel_sync_events_select" on excel_sync_events;
drop policy if exists "excel_sync_events_insert" on excel_sync_events;
create policy "excel_sync_events_select" on excel_sync_events for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "excel_sync_events_insert" on excel_sync_events for insert with check (tenant_id = current_setting('app.tenant_id', true));

alter table memo_packs enable row level security;
drop policy if exists "memo_packs_select" on memo_packs;
drop policy if exists "memo_packs_insert" on memo_packs;
drop policy if exists "memo_packs_update" on memo_packs;
drop policy if exists "memo_packs_delete" on memo_packs;
create policy "memo_packs_select" on memo_packs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "memo_packs_insert" on memo_packs for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "memo_packs_update" on memo_packs for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "memo_packs_delete" on memo_packs for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0017_excel_sync_status_received.sql
-- ############################################################################
alter table excel_sync_events drop constraint if exists excel_sync_events_status_check;
alter table excel_sync_events add constraint excel_sync_events_status_check
  check (status in ('succeeded', 'failed', 'partial', 'received'));

-- ############################################################################
-- 0018_document_collaboration.sql
-- ############################################################################
create table if not exists document_attachments (
  tenant_id text not null references tenants(id) on delete cascade,
  document_id text not null,
  entity_type text not null,
  entity_id text not null,
  filename text not null,
  content_type text not null default 'application/octet-stream',
  file_size bigint not null default 0,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, document_id)
);
create index if not exists idx_document_attachments_entity on document_attachments(tenant_id, entity_type, entity_id);

create table if not exists comments (
  tenant_id text not null references tenants(id) on delete cascade,
  comment_id text not null,
  entity_type text not null,
  entity_id text not null,
  parent_comment_id text,
  body text not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, comment_id),
  foreign key (tenant_id, parent_comment_id) references comments(tenant_id, comment_id) on delete cascade
);
create index if not exists idx_comments_entity on comments(tenant_id, entity_type, entity_id);
create index if not exists idx_comments_created on comments(tenant_id, created_at desc);

alter table document_attachments enable row level security;
drop policy if exists "document_attachments_select" on document_attachments;
drop policy if exists "document_attachments_insert" on document_attachments;
drop policy if exists "document_attachments_delete" on document_attachments;
create policy "document_attachments_select" on document_attachments for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "document_attachments_insert" on document_attachments for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "document_attachments_delete" on document_attachments for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table comments enable row level security;
drop policy if exists "comments_select" on comments;
drop policy if exists "comments_insert" on comments;
drop policy if exists "comments_delete" on comments;
create policy "comments_select" on comments for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "comments_insert" on comments for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "comments_delete" on comments for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0019_teams_hierarchy.sql
-- ############################################################################
create table if not exists job_functions (
  tenant_id text not null references tenants(id) on delete cascade,
  job_function_id text not null,
  name text not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, job_function_id)
);
create index if not exists idx_job_functions_tenant on job_functions(tenant_id);

insert into job_functions (tenant_id, job_function_id, name)
select t.id, v.job_function_id, v.name
from tenants t
cross join (values
  ('jf_analyst', 'Analyst'),
  ('jf_senior_analyst', 'Senior Analyst'),
  ('jf_manager', 'Manager'),
  ('jf_director', 'Director'),
  ('jf_cfo', 'CFO')
) as v(job_function_id, name)
on conflict (tenant_id, job_function_id) do nothing;

create table if not exists teams (
  tenant_id text not null references tenants(id) on delete cascade,
  team_id text not null,
  name text not null,
  description text,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, team_id)
);
create index if not exists idx_teams_tenant on teams(tenant_id);

create table if not exists team_members (
  tenant_id text not null references tenants(id) on delete cascade,
  team_id text not null,
  user_id text not null references users(id) on delete cascade,
  job_function_id text not null,
  reports_to text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, team_id, user_id),
  foreign key (tenant_id, team_id) references teams(tenant_id, team_id) on delete cascade,
  foreign key (tenant_id, job_function_id) references job_functions(tenant_id, job_function_id) on delete restrict
);
comment on column team_members.reports_to is 'Manager user_id; API must validate they are in same (tenant_id, team_id).';
create index if not exists idx_team_members_team on team_members(tenant_id, team_id);
create index if not exists idx_team_members_user on team_members(tenant_id, user_id);
create index if not exists idx_team_members_reports_to on team_members(tenant_id, team_id, reports_to) where reports_to is not null;

alter table job_functions enable row level security;
drop policy if exists "job_functions_select" on job_functions;
drop policy if exists "job_functions_insert" on job_functions;
drop policy if exists "job_functions_update" on job_functions;
drop policy if exists "job_functions_delete" on job_functions;
create policy "job_functions_select" on job_functions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "job_functions_insert" on job_functions for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "job_functions_update" on job_functions for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "job_functions_delete" on job_functions for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table teams enable row level security;
drop policy if exists "teams_select" on teams;
drop policy if exists "teams_insert" on teams;
drop policy if exists "teams_update" on teams;
drop policy if exists "teams_delete" on teams;
create policy "teams_select" on teams for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "teams_insert" on teams for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "teams_update" on teams for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "teams_delete" on teams for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table team_members enable row level security;
drop policy if exists "team_members_select" on team_members;
drop policy if exists "team_members_insert" on team_members;
drop policy if exists "team_members_update" on team_members;
drop policy if exists "team_members_delete" on team_members;
create policy "team_members_select" on team_members for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "team_members_insert" on team_members for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "team_members_update" on team_members for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "team_members_delete" on team_members for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0020_workflow_templates.sql (VA-P6-03)
-- ############################################################################
create table if not exists workflow_templates (
  tenant_id text not null references tenants(id) on delete cascade,
  template_id text not null,
  name text not null,
  description text,
  stages_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, template_id)
);
create index if not exists idx_workflow_templates_tenant on workflow_templates(tenant_id);
create table if not exists workflow_instances (
  tenant_id text not null references tenants(id) on delete cascade,
  instance_id text not null,
  template_id text not null,
  entity_type text not null,
  entity_id text not null,
  current_stage_index integer not null default 0,
  status text not null default 'pending'
    check (status in ('pending','in_progress','submitted','approved','returned','completed')),
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, instance_id),
  foreign key (tenant_id, template_id) references workflow_templates(tenant_id, template_id) on delete restrict
);
create index if not exists idx_workflow_instances_tenant on workflow_instances(tenant_id);
create index if not exists idx_workflow_instances_entity on workflow_instances(tenant_id, entity_type, entity_id);
create index if not exists idx_workflow_instances_status on workflow_instances(tenant_id, status);
alter table workflow_templates enable row level security;
drop policy if exists "workflow_templates_select" on workflow_templates;
drop policy if exists "workflow_templates_insert" on workflow_templates;
drop policy if exists "workflow_templates_update" on workflow_templates;
drop policy if exists "workflow_templates_delete" on workflow_templates;
create policy "workflow_templates_select" on workflow_templates for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_templates_insert" on workflow_templates for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_templates_update" on workflow_templates for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_templates_delete" on workflow_templates for delete using (tenant_id = current_setting('app.tenant_id', true));
alter table workflow_instances enable row level security;
drop policy if exists "workflow_instances_select" on workflow_instances;
drop policy if exists "workflow_instances_insert" on workflow_instances;
drop policy if exists "workflow_instances_update" on workflow_instances;
drop policy if exists "workflow_instances_delete" on workflow_instances;
create policy "workflow_instances_select" on workflow_instances for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_instances_insert" on workflow_instances for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_instances_update" on workflow_instances for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_instances_delete" on workflow_instances for delete using (tenant_id = current_setting('app.tenant_id', true));
insert into workflow_templates (tenant_id, template_id, name, description, stages_json)
select t.id, v.template_id, v.name, v.description, v.stages_json::jsonb
from tenants t
cross join (values
  ('tpl_self_service', 'Self-Service', 'Single stage; any team member can claim',
   '[{"stage_id":"s1","name":"Complete","assignee_rule":"team_pool","assignee_config":{}}]'),
  ('tpl_standard_review', 'Standard Review', 'Assignee works; manager reviews',
   '[{"stage_id":"s1","name":"Prepare","assignee_rule":"explicit","assignee_config":{}},{"stage_id":"s2","name":"Review","assignee_rule":"reports_to","assignee_config":{}}]'),
  ('tpl_full_approval', 'Full Approval', 'Analyst -> Manager -> Director/CFO',
   '[{"stage_id":"s1","name":"Prepare","assignee_rule":"explicit","assignee_config":{}},{"stage_id":"s2","name":"Manager Review","assignee_rule":"reports_to","assignee_config":{}},{"stage_id":"s3","name":"Director Approval","assignee_rule":"reports_to_chain","assignee_config":{}}]')
) as v(template_id, name, description, stages_json)
on conflict (tenant_id, template_id) do nothing;

-- ############################################################################
-- 0021_task_assignments.sql (VA-P6-04)
-- ############################################################################
create table if not exists task_assignments (
  tenant_id text not null references tenants(id) on delete cascade,
  assignment_id text not null,
  workflow_instance_id text,
  entity_type text not null,
  entity_id text not null,
  assignee_user_id text references users(id) on delete cascade,
  assigned_by_user_id text references users(id) on delete set null,
  status text not null default 'draft'
    check (status in ('draft','assigned','in_progress','submitted','approved','returned','completed')),
  deadline timestamptz,
  instructions text,
  created_at timestamptz not null default now(),
  submitted_at timestamptz,
  primary key (tenant_id, assignment_id)
);
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'fk_task_assignments_workflow') then
    alter table task_assignments
      add constraint fk_task_assignments_workflow
      foreign key (tenant_id, workflow_instance_id) references workflow_instances(tenant_id, instance_id) on delete set null;
  end if;
end $$;
create index if not exists idx_task_assignments_tenant on task_assignments(tenant_id);
create index if not exists idx_task_assignments_assignee on task_assignments(tenant_id, assignee_user_id);
create index if not exists idx_task_assignments_status on task_assignments(tenant_id, status);
create index if not exists idx_task_assignments_entity on task_assignments(tenant_id, entity_type, entity_id);
create index if not exists idx_task_assignments_deadline on task_assignments(tenant_id, deadline) where deadline is not null;
alter table task_assignments enable row level security;
drop policy if exists "task_assignments_select" on task_assignments;
drop policy if exists "task_assignments_insert" on task_assignments;
drop policy if exists "task_assignments_update" on task_assignments;
drop policy if exists "task_assignments_delete" on task_assignments;
create policy "task_assignments_select" on task_assignments for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "task_assignments_insert" on task_assignments for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "task_assignments_update" on task_assignments for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "task_assignments_delete" on task_assignments for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0022_reviews.sql (VA-P6-05)
-- ############################################################################
create table if not exists reviews (
  tenant_id text not null references tenants(id) on delete cascade,
  review_id text not null,
  assignment_id text not null,
  reviewer_user_id text not null references users(id) on delete cascade,
  decision text not null check (decision in ('approved', 'request_changes', 'rejected')),
  notes text,
  corrections_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, review_id),
  foreign key (tenant_id, assignment_id) references task_assignments(tenant_id, assignment_id) on delete cascade
);
create index if not exists idx_reviews_assignment on reviews(tenant_id, assignment_id);
create index if not exists idx_reviews_reviewer on reviews(tenant_id, reviewer_user_id);
create table if not exists change_summaries (
  tenant_id text not null references tenants(id) on delete cascade,
  summary_id text not null,
  review_id text not null,
  summary_text text not null,
  learning_points_json jsonb default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, summary_id),
  foreign key (tenant_id, review_id) references reviews(tenant_id, review_id) on delete cascade
);
create index if not exists idx_change_summaries_review on change_summaries(tenant_id, review_id);
alter table reviews enable row level security;
drop policy if exists "reviews_select" on reviews;
drop policy if exists "reviews_insert" on reviews;
drop policy if exists "reviews_update" on reviews;
drop policy if exists "reviews_delete" on reviews;
create policy "reviews_select" on reviews for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "reviews_insert" on reviews for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "reviews_update" on reviews for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "reviews_delete" on reviews for delete using (tenant_id = current_setting('app.tenant_id', true));
alter table change_summaries enable row level security;
drop policy if exists "change_summaries_select" on change_summaries;
drop policy if exists "change_summaries_insert" on change_summaries;
drop policy if exists "change_summaries_update" on change_summaries;
drop policy if exists "change_summaries_delete" on change_summaries;
create policy "change_summaries_select" on change_summaries for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "change_summaries_insert" on change_summaries for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "change_summaries_update" on change_summaries for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "change_summaries_delete" on change_summaries for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0023_workflow_instances_updated_at_trigger.sql (R5-11)
-- ############################################################################
create or replace function update_workflow_instances_updated_at()
returns trigger as $$
begin
  NEW.updated_at = now();
  return NEW;
end;
$$ language plpgsql;

drop trigger if exists trg_workflow_instances_updated_at on workflow_instances;
create trigger trg_workflow_instances_updated_at
  before update on workflow_instances
  for each row execute function update_workflow_instances_updated_at();

-- ############################################################################
-- 0024_feedback_acknowledged.sql (VA-P6-06)
-- ############################################################################
alter table change_summaries
  add column if not exists acknowledged_at timestamptz;

create index if not exists idx_change_summaries_acknowledged
  on change_summaries(tenant_id, acknowledged_at) where acknowledged_at is null;

-- ############################################################################
-- 0025_budgets.sql (VA-P7-01)
-- ############################################################################
-- Budget data model: budgets, budget_versions, budget_periods, budget_line_items,
-- budget_line_item_amounts, budget_department_allocations. Lifecycle: draft →
-- submitted → under_review → approved → active → closed.

create table if not exists budgets (
  tenant_id text not null references tenants(id) on delete cascade,
  budget_id text not null,
  label text not null,
  fiscal_year text not null,
  status text not null check (status in (
    'draft', 'submitted', 'under_review', 'approved', 'active', 'closed'
  )),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, budget_id)
);
create index if not exists idx_budgets_tenant_status on budgets(tenant_id, status);
create index if not exists idx_budgets_tenant_fiscal on budgets(tenant_id, fiscal_year);

create table if not exists budget_versions (
  tenant_id text not null references tenants(id) on delete cascade,
  budget_id text not null,
  version_id text not null,
  version_number int not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, budget_id, version_id),
  foreign key (tenant_id, budget_id) references budgets(tenant_id, budget_id) on delete cascade
);
create index if not exists idx_budget_versions_budget on budget_versions(tenant_id, budget_id);

alter table budgets add column if not exists current_version_id text;
alter table budgets drop constraint if exists fk_budgets_current_version;
alter table budgets
  add constraint fk_budgets_current_version
  foreign key (tenant_id, budget_id, current_version_id)
  references budget_versions(tenant_id, budget_id, version_id) on delete set null;

create table if not exists budget_periods (
  tenant_id text not null references tenants(id) on delete cascade,
  budget_id text not null,
  period_id text not null,
  period_ordinal int not null,
  period_start date not null,
  period_end date not null,
  label text,
  primary key (tenant_id, budget_id, period_id),
  foreign key (tenant_id, budget_id) references budgets(tenant_id, budget_id) on delete cascade,
  unique (tenant_id, budget_id, period_ordinal)
);
create index if not exists idx_budget_periods_budget on budget_periods(tenant_id, budget_id);

create table if not exists budget_line_items (
  tenant_id text not null references tenants(id) on delete cascade,
  line_item_id text not null,
  budget_id text not null,
  version_id text not null,
  account_ref text not null,
  notes text,
  primary key (tenant_id, line_item_id),
  foreign key (tenant_id, budget_id, version_id)
    references budget_versions(tenant_id, budget_id, version_id) on delete cascade,
  unique (tenant_id, budget_id, version_id, account_ref)
);
create index if not exists idx_budget_line_items_version on budget_line_items(tenant_id, budget_id, version_id);

create table if not exists budget_line_item_amounts (
  tenant_id text not null references tenants(id) on delete cascade,
  line_item_id text not null,
  period_ordinal int not null,
  amount numeric not null default 0,
  primary key (tenant_id, line_item_id, period_ordinal),
  foreign key (tenant_id, line_item_id)
    references budget_line_items(tenant_id, line_item_id) on delete cascade
);
create index if not exists idx_budget_line_item_amounts_line on budget_line_item_amounts(tenant_id, line_item_id);

create table if not exists budget_department_allocations (
  tenant_id text not null references tenants(id) on delete cascade,
  allocation_id text not null,
  budget_id text not null,
  version_id text not null,
  department_ref text not null,
  amount_limit numeric not null,
  primary key (tenant_id, allocation_id),
  foreign key (tenant_id, budget_id, version_id)
    references budget_versions(tenant_id, budget_id, version_id) on delete cascade,
  unique (tenant_id, budget_id, version_id, department_ref)
);
create index if not exists idx_budget_department_alloc_version on budget_department_allocations(tenant_id, budget_id, version_id);

alter table budgets enable row level security;
drop policy if exists "budgets_select" on budgets;
drop policy if exists "budgets_insert" on budgets;
drop policy if exists "budgets_update" on budgets;
drop policy if exists "budgets_delete" on budgets;
create policy "budgets_select" on budgets for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "budgets_insert" on budgets for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "budgets_update" on budgets for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "budgets_delete" on budgets for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table budget_versions enable row level security;
drop policy if exists "budget_versions_select" on budget_versions;
drop policy if exists "budget_versions_insert" on budget_versions;
drop policy if exists "budget_versions_update" on budget_versions;
drop policy if exists "budget_versions_delete" on budget_versions;
create policy "budget_versions_select" on budget_versions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_versions_insert" on budget_versions for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_versions_update" on budget_versions for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_versions_delete" on budget_versions for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table budget_periods enable row level security;
drop policy if exists "budget_periods_select" on budget_periods;
drop policy if exists "budget_periods_insert" on budget_periods;
drop policy if exists "budget_periods_update" on budget_periods;
drop policy if exists "budget_periods_delete" on budget_periods;
create policy "budget_periods_select" on budget_periods for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_periods_insert" on budget_periods for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_periods_update" on budget_periods for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_periods_delete" on budget_periods for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table budget_line_items enable row level security;
drop policy if exists "budget_line_items_select" on budget_line_items;
drop policy if exists "budget_line_items_insert" on budget_line_items;
drop policy if exists "budget_line_items_update" on budget_line_items;
drop policy if exists "budget_line_items_delete" on budget_line_items;
create policy "budget_line_items_select" on budget_line_items for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_line_items_insert" on budget_line_items for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_line_items_update" on budget_line_items for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_line_items_delete" on budget_line_items for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table budget_line_item_amounts enable row level security;
drop policy if exists "budget_line_item_amounts_select" on budget_line_item_amounts;
drop policy if exists "budget_line_item_amounts_insert" on budget_line_item_amounts;
drop policy if exists "budget_line_item_amounts_update" on budget_line_item_amounts;
drop policy if exists "budget_line_item_amounts_delete" on budget_line_item_amounts;
create policy "budget_line_item_amounts_select" on budget_line_item_amounts for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_line_item_amounts_insert" on budget_line_item_amounts for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_line_item_amounts_update" on budget_line_item_amounts for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_line_item_amounts_delete" on budget_line_item_amounts for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table budget_department_allocations enable row level security;
drop policy if exists "budget_department_allocations_select" on budget_department_allocations;
drop policy if exists "budget_department_allocations_insert" on budget_department_allocations;
drop policy if exists "budget_department_allocations_update" on budget_department_allocations;
drop policy if exists "budget_department_allocations_delete" on budget_department_allocations;
create policy "budget_department_allocations_select" on budget_department_allocations for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_department_allocations_insert" on budget_department_allocations for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_department_allocations_update" on budget_department_allocations for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "budget_department_allocations_delete" on budget_department_allocations for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0026_budget_actuals_and_confidence.sql (VA-P7-03/04/05)
-- Prerequisite: 0025 must be applied first.
-- ############################################################################
do $$
begin
  if exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'budget_line_items') then
    alter table budget_line_items add column if not exists confidence_score numeric;
    comment on column budget_line_items.confidence_score is 'Optional 0-1 confidence from LLM budget_initialization or budget_reforecast.';
  end if;
end $$;

do $$
begin
  if exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'budgets') then
    create table if not exists budget_actuals (
      tenant_id text not null references tenants(id) on delete cascade,
      budget_id text not null,
      period_ordinal int not null,
      account_ref text not null,
      amount numeric not null,
      department_ref text not null default '',
      source text not null check (source in ('csv', 'erp')),
      created_at timestamptz not null default now(),
      primary key (tenant_id, budget_id, period_ordinal, account_ref, department_ref),
      foreign key (tenant_id, budget_id) references budgets(tenant_id, budget_id) on delete cascade
    );
    create index if not exists idx_budget_actuals_budget_period on budget_actuals(tenant_id, budget_id, period_ordinal);
    create index if not exists idx_budget_actuals_department on budget_actuals(tenant_id, budget_id, department_ref) where department_ref != '';
    alter table budget_actuals enable row level security;
    drop policy if exists "budget_actuals_select" on budget_actuals;
    drop policy if exists "budget_actuals_insert" on budget_actuals;
    drop policy if exists "budget_actuals_update" on budget_actuals;
    drop policy if exists "budget_actuals_delete" on budget_actuals;
    create policy "budget_actuals_select" on budget_actuals for select using (tenant_id = current_setting('app.tenant_id', true));
    create policy "budget_actuals_insert" on budget_actuals for insert with check (tenant_id = current_setting('app.tenant_id', true));
    create policy "budget_actuals_update" on budget_actuals for update using (tenant_id = current_setting('app.tenant_id', true));
    create policy "budget_actuals_delete" on budget_actuals for delete using (tenant_id = current_setting('app.tenant_id', true));
  end if;
end $$;

-- ############################################################################
-- 0027_notifications_id_text.sql (R7-10: ntf_ prefix)
-- ############################################################################
do $$
begin
  if exists (select 1 from information_schema.columns c join information_schema.tables t on t.table_name = c.table_name and t.table_schema = c.table_schema
             where t.table_schema = 'public' and t.table_name = 'notifications' and c.column_name = 'id' and c.data_type = 'uuid') then
    alter table notifications alter column id drop default;
    alter table notifications alter column id type text using id::text;
  end if;
end $$;

-- ############################################################################
-- 0028_audit_log_restrict_update.sql (R8-03)
-- ############################################################################
drop policy if exists "audit_log_update" on audit_log;
create or replace function anonymize_audit_user(
  p_tenant_id text,
  p_user_id text,
  p_replacement text default 'anonymized'
) returns integer
language plpgsql security definer set search_path = public
as $$
declare
  affected integer;
begin
  update audit_log
  set user_id = p_replacement,
      event_data = event_data - 'user_email' - 'user_name'
  where tenant_id = p_tenant_id and user_id = p_user_id;
  GET DIAGNOSTICS affected = ROW_COUNT;
  return affected;
end;
$$;

-- ############################################################################
-- 0029_standardize_rls_function.sql (R8-04)
-- ############################################################################
-- R8-04: Standardize all RLS policies to use current_tenant_id() function for consistency.

-- notifications
drop policy if exists "notifications_select" on notifications;
create policy "notifications_select" on notifications for select
  using (tenant_id = current_tenant_id());
drop policy if exists "notifications_insert" on notifications;
create policy "notifications_insert" on notifications for insert
  with check (tenant_id = current_tenant_id());
drop policy if exists "notifications_update" on notifications;
create policy "notifications_update" on notifications for update
  using (tenant_id = current_tenant_id());
drop policy if exists "notifications_delete" on notifications;
create policy "notifications_delete" on notifications for delete
  using (tenant_id = current_tenant_id());

-- scenarios
drop policy if exists "scenarios_select" on scenarios;
create policy "scenarios_select" on scenarios for select using (tenant_id = current_tenant_id());
drop policy if exists "scenarios_insert" on scenarios;
create policy "scenarios_insert" on scenarios for insert with check (tenant_id = current_tenant_id());
drop policy if exists "scenarios_update" on scenarios;
create policy "scenarios_update" on scenarios for update using (tenant_id = current_tenant_id());
drop policy if exists "scenarios_delete" on scenarios;
create policy "scenarios_delete" on scenarios for delete using (tenant_id = current_tenant_id());

-- integration_connections
drop policy if exists "integration_connections_select" on integration_connections;
create policy "integration_connections_select" on integration_connections for select using (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_insert" on integration_connections;
create policy "integration_connections_insert" on integration_connections for insert with check (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_update" on integration_connections;
create policy "integration_connections_update" on integration_connections for update using (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_delete" on integration_connections;
create policy "integration_connections_delete" on integration_connections for delete using (tenant_id = current_tenant_id());

-- integration_sync_runs
drop policy if exists "integration_sync_runs_select" on integration_sync_runs;
create policy "integration_sync_runs_select" on integration_sync_runs for select using (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_insert" on integration_sync_runs;
create policy "integration_sync_runs_insert" on integration_sync_runs for insert with check (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_update" on integration_sync_runs;
create policy "integration_sync_runs_update" on integration_sync_runs for update using (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_delete" on integration_sync_runs;
create policy "integration_sync_runs_delete" on integration_sync_runs for delete using (tenant_id = current_tenant_id());

-- canonical_sync_snapshots
drop policy if exists "canonical_snapshots_select" on canonical_sync_snapshots;
create policy "canonical_snapshots_select" on canonical_sync_snapshots for select using (tenant_id = current_tenant_id());
drop policy if exists "canonical_snapshots_insert" on canonical_sync_snapshots;
create policy "canonical_snapshots_insert" on canonical_sync_snapshots for insert with check (tenant_id = current_tenant_id());
drop policy if exists "canonical_snapshots_delete" on canonical_sync_snapshots;
create policy "canonical_snapshots_delete" on canonical_sync_snapshots for delete using (tenant_id = current_tenant_id());

-- billing_subscriptions
drop policy if exists "billing_subscriptions_select" on billing_subscriptions;
create policy "billing_subscriptions_select" on billing_subscriptions for select using (tenant_id = current_tenant_id());
drop policy if exists "billing_subscriptions_insert" on billing_subscriptions;
create policy "billing_subscriptions_insert" on billing_subscriptions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "billing_subscriptions_update" on billing_subscriptions;
create policy "billing_subscriptions_update" on billing_subscriptions for update using (tenant_id = current_tenant_id());

-- usage_meters
drop policy if exists "usage_meters_select" on usage_meters;
create policy "usage_meters_select" on usage_meters for select using (tenant_id = current_tenant_id());
drop policy if exists "usage_meters_insert" on usage_meters;
create policy "usage_meters_insert" on usage_meters for insert with check (tenant_id = current_tenant_id());
drop policy if exists "usage_meters_update" on usage_meters;
create policy "usage_meters_update" on usage_meters for update using (tenant_id = current_tenant_id());

-- llm_call_logs
drop policy if exists "llm_call_logs_select" on llm_call_logs;
create policy "llm_call_logs_select" on llm_call_logs for select using (tenant_id = current_tenant_id());
drop policy if exists "llm_call_logs_insert" on llm_call_logs;
create policy "llm_call_logs_insert" on llm_call_logs for insert with check (tenant_id = current_tenant_id());

-- llm_routing_policies (special: tenant_id can be null for defaults)
drop policy if exists "llm_routing_policies_select" on llm_routing_policies;
create policy "llm_routing_policies_select" on llm_routing_policies for select using (
  tenant_id = current_tenant_id() or tenant_id is null
);

-- audit_log (note: no UPDATE policy per R8-03)
drop policy if exists "audit_log_insert" on audit_log;
create policy "audit_log_insert" on audit_log for insert with check (tenant_id = current_tenant_id());
drop policy if exists "audit_log_select" on audit_log;
create policy "audit_log_select" on audit_log for select using (tenant_id = current_tenant_id());

-- covenant_definitions
drop policy if exists "covenant_definitions_select" on covenant_definitions;
create policy "covenant_definitions_select" on covenant_definitions for select using (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_insert" on covenant_definitions;
create policy "covenant_definitions_insert" on covenant_definitions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_update" on covenant_definitions;
create policy "covenant_definitions_update" on covenant_definitions for update using (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_delete" on covenant_definitions;
create policy "covenant_definitions_delete" on covenant_definitions for delete using (tenant_id = current_tenant_id());

-- excel_connections
drop policy if exists "excel_connections_select" on excel_connections;
create policy "excel_connections_select" on excel_connections for select using (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_insert" on excel_connections;
create policy "excel_connections_insert" on excel_connections for insert with check (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_update" on excel_connections;
create policy "excel_connections_update" on excel_connections for update using (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_delete" on excel_connections;
create policy "excel_connections_delete" on excel_connections for delete using (tenant_id = current_tenant_id());

-- excel_sync_events
drop policy if exists "excel_sync_events_select" on excel_sync_events;
create policy "excel_sync_events_select" on excel_sync_events for select using (tenant_id = current_tenant_id());
drop policy if exists "excel_sync_events_insert" on excel_sync_events;
create policy "excel_sync_events_insert" on excel_sync_events for insert with check (tenant_id = current_tenant_id());

-- memo_packs
drop policy if exists "memo_packs_select" on memo_packs;
create policy "memo_packs_select" on memo_packs for select using (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_insert" on memo_packs;
create policy "memo_packs_insert" on memo_packs for insert with check (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_update" on memo_packs;
create policy "memo_packs_update" on memo_packs for update using (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_delete" on memo_packs;
create policy "memo_packs_delete" on memo_packs for delete using (tenant_id = current_tenant_id());

-- document_attachments
drop policy if exists "document_attachments_select" on document_attachments;
create policy "document_attachments_select" on document_attachments for select using (tenant_id = current_tenant_id());
drop policy if exists "document_attachments_insert" on document_attachments;
create policy "document_attachments_insert" on document_attachments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "document_attachments_delete" on document_attachments;
create policy "document_attachments_delete" on document_attachments for delete using (tenant_id = current_tenant_id());

-- comments
drop policy if exists "comments_select" on comments;
create policy "comments_select" on comments for select using (tenant_id = current_tenant_id());
drop policy if exists "comments_insert" on comments;
create policy "comments_insert" on comments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "comments_delete" on comments;
create policy "comments_delete" on comments for delete using (tenant_id = current_tenant_id());

-- job_functions
drop policy if exists "job_functions_select" on job_functions;
create policy "job_functions_select" on job_functions for select using (tenant_id = current_tenant_id());
drop policy if exists "job_functions_insert" on job_functions;
create policy "job_functions_insert" on job_functions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "job_functions_update" on job_functions;
create policy "job_functions_update" on job_functions for update using (tenant_id = current_tenant_id());
drop policy if exists "job_functions_delete" on job_functions;
create policy "job_functions_delete" on job_functions for delete using (tenant_id = current_tenant_id());

-- teams
drop policy if exists "teams_select" on teams;
create policy "teams_select" on teams for select using (tenant_id = current_tenant_id());
drop policy if exists "teams_insert" on teams;
create policy "teams_insert" on teams for insert with check (tenant_id = current_tenant_id());
drop policy if exists "teams_update" on teams;
create policy "teams_update" on teams for update using (tenant_id = current_tenant_id());
drop policy if exists "teams_delete" on teams;
create policy "teams_delete" on teams for delete using (tenant_id = current_tenant_id());

-- team_members
drop policy if exists "team_members_select" on team_members;
create policy "team_members_select" on team_members for select using (tenant_id = current_tenant_id());
drop policy if exists "team_members_insert" on team_members;
create policy "team_members_insert" on team_members for insert with check (tenant_id = current_tenant_id());
drop policy if exists "team_members_update" on team_members;
create policy "team_members_update" on team_members for update using (tenant_id = current_tenant_id());
drop policy if exists "team_members_delete" on team_members;
create policy "team_members_delete" on team_members for delete using (tenant_id = current_tenant_id());

-- workflow_templates
drop policy if exists "workflow_templates_select" on workflow_templates;
create policy "workflow_templates_select" on workflow_templates for select using (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_insert" on workflow_templates;
create policy "workflow_templates_insert" on workflow_templates for insert with check (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_update" on workflow_templates;
create policy "workflow_templates_update" on workflow_templates for update using (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_delete" on workflow_templates;
create policy "workflow_templates_delete" on workflow_templates for delete using (tenant_id = current_tenant_id());

-- workflow_instances
drop policy if exists "workflow_instances_select" on workflow_instances;
create policy "workflow_instances_select" on workflow_instances for select using (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_insert" on workflow_instances;
create policy "workflow_instances_insert" on workflow_instances for insert with check (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_update" on workflow_instances;
create policy "workflow_instances_update" on workflow_instances for update using (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_delete" on workflow_instances;
create policy "workflow_instances_delete" on workflow_instances for delete using (tenant_id = current_tenant_id());

-- task_assignments
drop policy if exists "task_assignments_select" on task_assignments;
create policy "task_assignments_select" on task_assignments for select using (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_insert" on task_assignments;
create policy "task_assignments_insert" on task_assignments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_update" on task_assignments;
create policy "task_assignments_update" on task_assignments for update using (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_delete" on task_assignments;
create policy "task_assignments_delete" on task_assignments for delete using (tenant_id = current_tenant_id());

-- reviews
drop policy if exists "reviews_select" on reviews;
create policy "reviews_select" on reviews for select using (tenant_id = current_tenant_id());
drop policy if exists "reviews_insert" on reviews;
create policy "reviews_insert" on reviews for insert with check (tenant_id = current_tenant_id());
drop policy if exists "reviews_update" on reviews;
create policy "reviews_update" on reviews for update using (tenant_id = current_tenant_id());
drop policy if exists "reviews_delete" on reviews;
create policy "reviews_delete" on reviews for delete using (tenant_id = current_tenant_id());

-- change_summaries
drop policy if exists "change_summaries_select" on change_summaries;
create policy "change_summaries_select" on change_summaries for select using (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_insert" on change_summaries;
create policy "change_summaries_insert" on change_summaries for insert with check (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_update" on change_summaries;
create policy "change_summaries_update" on change_summaries for update using (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_delete" on change_summaries;
create policy "change_summaries_delete" on change_summaries for delete using (tenant_id = current_tenant_id());

-- budgets
drop policy if exists "budgets_select" on budgets;
create policy "budgets_select" on budgets for select using (tenant_id = current_tenant_id());
drop policy if exists "budgets_insert" on budgets;
create policy "budgets_insert" on budgets for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budgets_update" on budgets;
create policy "budgets_update" on budgets for update using (tenant_id = current_tenant_id());
drop policy if exists "budgets_delete" on budgets;
create policy "budgets_delete" on budgets for delete using (tenant_id = current_tenant_id());

-- budget_versions
drop policy if exists "budget_versions_select" on budget_versions;
create policy "budget_versions_select" on budget_versions for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_insert" on budget_versions;
create policy "budget_versions_insert" on budget_versions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_update" on budget_versions;
create policy "budget_versions_update" on budget_versions for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_delete" on budget_versions;
create policy "budget_versions_delete" on budget_versions for delete using (tenant_id = current_tenant_id());

-- budget_periods
drop policy if exists "budget_periods_select" on budget_periods;
create policy "budget_periods_select" on budget_periods for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_insert" on budget_periods;
create policy "budget_periods_insert" on budget_periods for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_update" on budget_periods;
create policy "budget_periods_update" on budget_periods for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_delete" on budget_periods;
create policy "budget_periods_delete" on budget_periods for delete using (tenant_id = current_tenant_id());

-- budget_line_items
drop policy if exists "budget_line_items_select" on budget_line_items;
create policy "budget_line_items_select" on budget_line_items for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_insert" on budget_line_items;
create policy "budget_line_items_insert" on budget_line_items for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_update" on budget_line_items;
create policy "budget_line_items_update" on budget_line_items for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_delete" on budget_line_items;
create policy "budget_line_items_delete" on budget_line_items for delete using (tenant_id = current_tenant_id());

-- budget_line_item_amounts
drop policy if exists "budget_line_item_amounts_select" on budget_line_item_amounts;
create policy "budget_line_item_amounts_select" on budget_line_item_amounts for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_insert" on budget_line_item_amounts;
create policy "budget_line_item_amounts_insert" on budget_line_item_amounts for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_update" on budget_line_item_amounts;
create policy "budget_line_item_amounts_update" on budget_line_item_amounts for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_delete" on budget_line_item_amounts;
create policy "budget_line_item_amounts_delete" on budget_line_item_amounts for delete using (tenant_id = current_tenant_id());

-- budget_department_allocations
drop policy if exists "budget_department_allocations_select" on budget_department_allocations;
create policy "budget_department_allocations_select" on budget_department_allocations for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_insert" on budget_department_allocations;
create policy "budget_department_allocations_insert" on budget_department_allocations for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_update" on budget_department_allocations;
create policy "budget_department_allocations_update" on budget_department_allocations for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_delete" on budget_department_allocations;
create policy "budget_department_allocations_delete" on budget_department_allocations for delete using (tenant_id = current_tenant_id());

-- budget_actuals
drop policy if exists "budget_actuals_select" on budget_actuals;
create policy "budget_actuals_select" on budget_actuals for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_insert" on budget_actuals;
create policy "budget_actuals_insert" on budget_actuals for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_update" on budget_actuals;
create policy "budget_actuals_update" on budget_actuals for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_delete" on budget_actuals;
create policy "budget_actuals_delete" on budget_actuals for delete using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0030_core_delete_policies.sql (R8-05)
-- ############################################################################
-- R8-05: Add DELETE RLS policies to core tables that were missing them in 0002.

drop policy if exists "model_baselines_delete" on model_baselines;
create policy "model_baselines_delete" on model_baselines for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "model_changesets_delete" on model_changesets;
create policy "model_changesets_delete" on model_changesets for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "ventures_delete" on ventures;
create policy "ventures_delete" on ventures for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "venture_artifacts_delete" on venture_artifacts;
create policy "venture_artifacts_delete" on venture_artifacts for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "runs_delete" on runs;
create policy "runs_delete" on runs for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "run_artifacts_delete" on run_artifacts;
create policy "run_artifacts_delete" on run_artifacts for delete
  using (tenant_id = current_tenant_id());

-- Also add missing UPDATE policies for venture_artifacts and run_artifacts
drop policy if exists "venture_artifacts_update" on venture_artifacts;
create policy "venture_artifacts_update" on venture_artifacts for update
  using (tenant_id = current_tenant_id());

drop policy if exists "run_artifacts_update" on run_artifacts;
create policy "run_artifacts_update" on run_artifacts for update
  using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0031_comments_docs_update_policies.sql (R8-07)
-- ############################################################################
-- R8-07: Add UPDATE RLS policies for comments and document_attachments.

drop policy if exists "comments_update" on comments;
create policy "comments_update" on comments for update
  using (tenant_id = current_tenant_id());

drop policy if exists "document_attachments_update" on document_attachments;
create policy "document_attachments_update" on document_attachments for update
  using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0032_budget_approval_workflow.sql (VA-P7-06)
-- ############################################################################
alter table budgets add column if not exists workflow_instance_id text;
comment on column budgets.workflow_instance_id is 'Set when budget is submitted for approval; links to workflow_instances(instance_id) for entity_type=budget.';
insert into workflow_templates (tenant_id, template_id, name, description, stages_json)
select t.id, v.template_id, v.name, v.description, v.stages_json::jsonb
from tenants t
cross join (values
  ('tpl_budget_approval', 'Budget Approval', 'Department head -> Finance -> CFO -> Board presentation',
   '[{"stage_id":"s1","name":"Department head review","assignee_rule":"reports_to","assignee_config":{}},{"stage_id":"s2","name":"Finance review","assignee_rule":"reports_to","assignee_config":{}},{"stage_id":"s3","name":"CFO approval","assignee_rule":"reports_to_chain","assignee_config":{}},{"stage_id":"s4","name":"Board presentation","assignee_rule":"team_pool","assignee_config":{}}]')
) as v(template_id, name, description, stages_json)
on conflict (tenant_id, template_id) do nothing;

-- ############################################################################
-- 0033_board_packs.sql (VA-P7-07)
-- ############################################################################
create table if not exists board_packs (
  tenant_id text not null references tenants(id) on delete cascade,
  pack_id text not null,
  label text not null,
  run_id text,
  budget_id text,
  section_order jsonb not null default '["executive_summary","income_statement","balance_sheet","cash_flow","budget_variance","kpi_dashboard","scenario_comparison","strategic_commentary"]'::jsonb,
  status text not null default 'draft' check (status in ('draft', 'generating', 'ready', 'error')),
  narrative_json jsonb default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, pack_id)
);
create index if not exists idx_board_packs_tenant on board_packs(tenant_id);
create index if not exists idx_board_packs_status on board_packs(tenant_id, status);

alter table board_packs enable row level security;
drop policy if exists "board_packs_select" on board_packs;
drop policy if exists "board_packs_insert" on board_packs;
drop policy if exists "board_packs_update" on board_packs;
drop policy if exists "board_packs_delete" on board_packs;
create policy "board_packs_select" on board_packs for select using (tenant_id = current_tenant_id());
create policy "board_packs_insert" on board_packs for insert with check (tenant_id = current_tenant_id());
create policy "board_packs_update" on board_packs for update using (tenant_id = current_tenant_id());
create policy "board_packs_delete" on board_packs for delete using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0034_board_pack_branding.sql (VA-P7-07 / Phase 10 stub)
-- ############################################################################
alter table board_packs add column if not exists branding_json jsonb not null default '{}'::jsonb;
comment on column board_packs.branding_json is 'Optional branding: logo_url, primary_color, terms_footer; applied on export (Phase 10).';

-- ############################################################################
-- 0035_board_pack_scheduling.sql (VA-P7-09)
-- ############################################################################
create table if not exists pack_schedules (
  tenant_id text not null references tenants(id) on delete cascade,
  schedule_id text not null,
  label text not null,
  run_id text,
  budget_id text,
  section_order jsonb not null default '["executive_summary","income_statement","balance_sheet","cash_flow","budget_variance","kpi_dashboard","scenario_comparison","strategic_commentary"]'::jsonb,
  cron_expr text not null,
  next_run_at timestamptz,
  distribution_emails text[] default '{}',
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, schedule_id)
);
create index if not exists idx_pack_schedules_tenant_next on pack_schedules(tenant_id, next_run_at) where enabled;

create table if not exists pack_generation_history (
  tenant_id text not null references tenants(id) on delete cascade,
  history_id text not null,
  schedule_id text,
  pack_id text not null,
  label text not null,
  run_id text,
  generated_at timestamptz not null default now(),
  distributed_at timestamptz,
  status text not null default 'ready' check (status in ('ready', 'distributed', 'failed')),
  error_message text,
  primary key (tenant_id, history_id)
);
create index if not exists idx_pack_history_tenant_generated on pack_generation_history(tenant_id, generated_at desc);
create index if not exists idx_pack_history_schedule on pack_generation_history(tenant_id, schedule_id);

alter table pack_schedules enable row level security;
alter table pack_generation_history enable row level security;
drop policy if exists "pack_schedules_select" on pack_schedules;
drop policy if exists "pack_schedules_insert" on pack_schedules;
drop policy if exists "pack_schedules_update" on pack_schedules;
drop policy if exists "pack_schedules_delete" on pack_schedules;
create policy "pack_schedules_select" on pack_schedules for select using (tenant_id = current_tenant_id());
create policy "pack_schedules_insert" on pack_schedules for insert with check (tenant_id = current_tenant_id());
create policy "pack_schedules_update" on pack_schedules for update using (tenant_id = current_tenant_id());
create policy "pack_schedules_delete" on pack_schedules for delete using (tenant_id = current_tenant_id());

drop policy if exists "pack_generation_history_select" on pack_generation_history;
drop policy if exists "pack_generation_history_insert" on pack_generation_history;
drop policy if exists "pack_generation_history_update" on pack_generation_history;
drop policy if exists "pack_generation_history_delete" on pack_generation_history;
create policy "pack_generation_history_select" on pack_generation_history for select using (tenant_id = current_tenant_id());
create policy "pack_generation_history_insert" on pack_generation_history for insert with check (tenant_id = current_tenant_id());
create policy "pack_generation_history_update" on pack_generation_history for update using (tenant_id = current_tenant_id());
create policy "pack_generation_history_delete" on pack_generation_history for delete using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0036_multi_currency_fx.sql (VA-P8-01)
-- ############################################################################
create table if not exists tenant_currency_settings (
  tenant_id text not null references tenants(id) on delete cascade,
  base_currency text not null default 'USD',
  reporting_currency text not null default 'USD',
  fx_source text not null default 'manual' check (fx_source in ('manual', 'feed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id)
);
create index if not exists idx_tenant_currency_settings_tenant on tenant_currency_settings(tenant_id);

create table if not exists fx_rates (
  tenant_id text not null references tenants(id) on delete cascade,
  from_currency text not null,
  to_currency text not null,
  effective_date date not null,
  rate numeric not null check (rate > 0),
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, from_currency, to_currency, effective_date)
);
create index if not exists idx_fx_rates_tenant_date on fx_rates(tenant_id, effective_date);

alter table tenant_currency_settings enable row level security;
drop policy if exists "tenant_currency_settings_select" on tenant_currency_settings;
drop policy if exists "tenant_currency_settings_insert" on tenant_currency_settings;
drop policy if exists "tenant_currency_settings_update" on tenant_currency_settings;
drop policy if exists "tenant_currency_settings_delete" on tenant_currency_settings;
create policy "tenant_currency_settings_select" on tenant_currency_settings for select using (tenant_id = current_tenant_id());
create policy "tenant_currency_settings_insert" on tenant_currency_settings for insert with check (tenant_id = current_tenant_id());
create policy "tenant_currency_settings_update" on tenant_currency_settings for update using (tenant_id = current_tenant_id());
create policy "tenant_currency_settings_delete" on tenant_currency_settings for delete using (tenant_id = current_tenant_id());

alter table fx_rates enable row level security;
drop policy if exists "fx_rates_select" on fx_rates;
drop policy if exists "fx_rates_insert" on fx_rates;
drop policy if exists "fx_rates_update" on fx_rates;
drop policy if exists "fx_rates_delete" on fx_rates;
create policy "fx_rates_select" on fx_rates for select using (tenant_id = current_tenant_id());
create policy "fx_rates_insert" on fx_rates for insert with check (tenant_id = current_tenant_id());
create policy "fx_rates_update" on fx_rates for update using (tenant_id = current_tenant_id());
create policy "fx_rates_delete" on fx_rates for delete using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0037_marketplace_templates.sql (VA-P8-03)
-- ############################################################################
create table if not exists marketplace_templates (
  template_id text primary key,
  name text not null,
  industry text not null default '',
  template_type text not null check (template_type in ('budget', 'model')),
  description text default '',
  created_at timestamptz not null default now()
);
create index if not exists idx_marketplace_templates_industry on marketplace_templates(industry);
create index if not exists idx_marketplace_templates_type on marketplace_templates(template_type);
insert into marketplace_templates (template_id, name, industry, template_type, description)
values
  ('manufacturing', 'Manufacturing', 'manufacturing', 'budget', 'Budget template for manufacturing: headcount, capacity, capex, revenue growth'),
  ('saas', 'SaaS', 'software', 'budget', 'Budget template for SaaS: ARR/MRR, headcount, infrastructure'),
  ('services', 'Services', 'services', 'budget', 'Budget template for professional services: billable headcount, utilization'),
  ('wholesale', 'Wholesale', 'wholesale', 'budget', 'Budget template for wholesale: inventory, margin, seasonality')
on conflict (template_id) do nothing;

-- ############################################################################
-- 0038_workflow_events.sql (VA-P8-06)
-- ############################################################################
create table if not exists workflow_events (
  tenant_id text not null references tenants(id) on delete cascade,
  instance_id text not null,
  stage_index integer not null,
  entered_at timestamptz not null,
  exited_at timestamptz,
  outcome text check (outcome is null or outcome in ('submitted', 'approved', 'returned', 'completed')),
  primary key (tenant_id, instance_id, stage_index, entered_at),
  foreign key (tenant_id, instance_id) references workflow_instances(tenant_id, instance_id) on delete cascade
);
create index if not exists idx_workflow_events_tenant_entered on workflow_events(tenant_id, entered_at);
alter table workflow_events enable row level security;
drop policy if exists "workflow_events_select" on workflow_events;
drop policy if exists "workflow_events_insert" on workflow_events;
drop policy if exists "workflow_events_update" on workflow_events;
drop policy if exists "workflow_events_delete" on workflow_events;
create policy "workflow_events_select" on workflow_events for select using (tenant_id = current_tenant_id());
create policy "workflow_events_insert" on workflow_events for insert with check (tenant_id = current_tenant_id());
create policy "workflow_events_update" on workflow_events for update using (tenant_id = current_tenant_id());
create policy "workflow_events_delete" on workflow_events for delete using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0039_tenant_saml_config.sql (VA-P8-02)
-- ############################################################################
create table if not exists tenant_saml_config (
  tenant_id text not null references tenants(id) on delete cascade,
  idp_metadata_url text,
  idp_metadata_xml text,
  entity_id text not null,
  acs_url text not null,
  idp_sso_url text,
  attribute_mapping_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id),
  constraint chk_saml_config check (idp_metadata_url is not null or idp_metadata_xml is not null or idp_sso_url is not null)
);
create index if not exists idx_tenant_saml_config_entity on tenant_saml_config(entity_id);
alter table tenant_saml_config enable row level security;
drop policy if exists "tenant_saml_config_select" on tenant_saml_config;
drop policy if exists "tenant_saml_config_insert" on tenant_saml_config;
drop policy if exists "tenant_saml_config_update" on tenant_saml_config;
drop policy if exists "tenant_saml_config_delete" on tenant_saml_config;
create policy "tenant_saml_config_select" on tenant_saml_config for select using (tenant_id = current_tenant_id());
create policy "tenant_saml_config_insert" on tenant_saml_config for insert with check (tenant_id = current_tenant_id());
create policy "tenant_saml_config_update" on tenant_saml_config for update using (tenant_id = current_tenant_id());
create policy "tenant_saml_config_delete" on tenant_saml_config for delete using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0040_peer_benchmark.sql (VA-P8-08, VA-P8-09)
-- ############################################################################
create table if not exists tenant_benchmark_opt_in (
  tenant_id text not null references tenants(id) on delete cascade,
  industry_segment text not null default 'general',
  size_segment text not null default 'general',
  opted_in_at timestamptz not null default now(),
  primary key (tenant_id)
);
create table if not exists benchmark_aggregates (
  id text primary key default ('bag_' || substr(md5(random()::text), 1, 12)),
  segment_key text not null,
  metric_name text not null,
  median_value numeric not null,
  p25_value numeric,
  p75_value numeric,
  sample_count integer not null default 0,
  computed_at timestamptz not null default now(),
  unique (segment_key, metric_name)
);
create index if not exists idx_benchmark_aggregates_segment on benchmark_aggregates(segment_key, metric_name);
alter table tenant_benchmark_opt_in enable row level security;
drop policy if exists "tenant_benchmark_opt_in_select" on tenant_benchmark_opt_in;
drop policy if exists "tenant_benchmark_opt_in_insert" on tenant_benchmark_opt_in;
drop policy if exists "tenant_benchmark_opt_in_update" on tenant_benchmark_opt_in;
drop policy if exists "tenant_benchmark_opt_in_delete" on tenant_benchmark_opt_in;
create policy "tenant_benchmark_opt_in_select" on tenant_benchmark_opt_in for select using (tenant_id = current_tenant_id());
create policy "tenant_benchmark_opt_in_insert" on tenant_benchmark_opt_in for insert with check (tenant_id = current_tenant_id());
create policy "tenant_benchmark_opt_in_update" on tenant_benchmark_opt_in for update using (tenant_id = current_tenant_id());
create policy "tenant_benchmark_opt_in_delete" on tenant_benchmark_opt_in for delete using (tenant_id = current_tenant_id());

-- ############################################################################
-- 0041_saml_lookup_function.sql (R11-10)
-- ############################################################################
create or replace function lookup_saml_tenant_by_entity_id(p_entity_id text)
returns text
language sql security definer stable as $$
  select tenant_id from tenant_saml_config where entity_id = p_entity_id limit 1;
$$;
comment on function lookup_saml_tenant_by_entity_id(text) is 'Used by SAML ACS to resolve tenant from IdP Issuer entity_id; SECURITY DEFINER bypasses RLS';

create unique index if not exists uq_tenant_saml_config_entity_id on tenant_saml_config(entity_id);

-- ############################################################################
-- 0042_saml_idp_certificate.sql (FIX-C01)
-- ############################################################################
alter table tenant_saml_config
  add column if not exists idp_certificate text;
comment on column tenant_saml_config.idp_certificate is 'PEM-formatted X.509 certificate from IdP metadata; required for production SAML signature verification';

-- ############################################################################
-- 0043_llm_usage_log.sql (FIX-C03)
-- ############################################################################
create table if not exists llm_usage_log (
    id bigint generated always as identity primary key,
    tenant_id text not null references tenants(id) on delete cascade,
    provider text not null default 'unknown',
    tokens_total int not null default 0,
    calls int not null default 1,
    estimated_usd numeric(12, 6) not null default 0,
    period text not null default to_char(now(), 'YYYY-MM'),
    created_at timestamptz not null default now()
);
create index if not exists idx_llm_usage_log_tenant_period on llm_usage_log(tenant_id, period);
comment on table llm_usage_log is 'One row per LLM call for usage metering; aggregated by get_usage()';
alter table llm_usage_log enable row level security;
create policy llm_usage_log_select on llm_usage_log for select using (tenant_id = current_setting('app.tenant_id', true));
create policy llm_usage_log_insert on llm_usage_log for insert with check (tenant_id = current_setting('app.tenant_id', true));

-- ############################################################################
-- 0044_excel_ingestion_sessions.sql (VA-P9-01: Excel Model Ingestion)
-- ############################################################################
CREATE TABLE IF NOT EXISTS excel_ingestion_sessions (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ingestion_id text NOT NULL,
    filename text NOT NULL,
    file_size_bytes bigint NOT NULL,
    status text NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'parsing', 'parsed', 'analyzing', 'analyzed', 'mapping', 'draft_created', 'failed')),
    sheet_count integer,
    formula_count integer,
    cross_ref_count integer,
    classification_json jsonb DEFAULT '{}'::jsonb,
    mapping_json jsonb DEFAULT '{}'::jsonb,
    unmapped_items_json jsonb DEFAULT '[]'::jsonb,
    draft_session_id text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, ingestion_id)
);
CREATE INDEX IF NOT EXISTS idx_excel_ingestion_tenant_status ON excel_ingestion_sessions(tenant_id, status);
ALTER TABLE excel_ingestion_sessions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "excel_ingestion_sessions_select" ON excel_ingestion_sessions;
DROP POLICY IF EXISTS "excel_ingestion_sessions_insert" ON excel_ingestion_sessions;
DROP POLICY IF EXISTS "excel_ingestion_sessions_update" ON excel_ingestion_sessions;
DROP POLICY IF EXISTS "excel_ingestion_sessions_delete" ON excel_ingestion_sessions;
CREATE POLICY "excel_ingestion_sessions_select" ON excel_ingestion_sessions FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "excel_ingestion_sessions_insert" ON excel_ingestion_sessions FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "excel_ingestion_sessions_update" ON excel_ingestion_sessions FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "excel_ingestion_sessions_delete" ON excel_ingestion_sessions FOR DELETE USING (tenant_id = current_tenant_id());

-- ############################################################################
-- 0045_org_structures.sql (VA-P9-02: Organization Hierarchy & Consolidation)
-- ############################################################################
CREATE TABLE IF NOT EXISTS org_structures (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    group_name text NOT NULL,
    reporting_currency text NOT NULL DEFAULT 'USD',
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'archived')),
    consolidation_method text NOT NULL DEFAULT 'full'
        CHECK (consolidation_method IN ('full', 'proportional', 'equity_method')),
    eliminate_intercompany boolean NOT NULL DEFAULT true,
    minority_interest_treatment text NOT NULL DEFAULT 'proportional'
        CHECK (minority_interest_treatment IN ('proportional', 'full_goodwill')),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id)
);
CREATE INDEX IF NOT EXISTS idx_org_structures_tenant_status ON org_structures(tenant_id, status);
CREATE TABLE IF NOT EXISTS org_entities (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    entity_id text NOT NULL,
    name text NOT NULL,
    entity_type text NOT NULL
        CHECK (entity_type IN ('holding', 'operating', 'spv', 'jv', 'associate', 'branch')),
    currency text NOT NULL DEFAULT 'USD',
    country_iso text NOT NULL DEFAULT 'US',
    tax_jurisdiction text,
    tax_rate numeric CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1)),
    withholding_tax_rate numeric DEFAULT 0
        CHECK (withholding_tax_rate >= 0 AND withholding_tax_rate <= 1),
    is_root boolean NOT NULL DEFAULT false,
    baseline_id text,
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'dormant', 'disposed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id, entity_id),
    FOREIGN KEY (tenant_id, org_id)
        REFERENCES org_structures(tenant_id, org_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_org_entities_org ON org_entities(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_org_entities_baseline ON org_entities(tenant_id, baseline_id)
    WHERE baseline_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS org_ownership_links (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    parent_entity_id text NOT NULL,
    child_entity_id text NOT NULL,
    ownership_pct numeric NOT NULL CHECK (ownership_pct > 0 AND ownership_pct <= 100),
    voting_pct numeric CHECK (voting_pct IS NULL OR (voting_pct >= 0 AND voting_pct <= 100)),
    consolidation_method text NOT NULL DEFAULT 'full'
        CHECK (consolidation_method IN ('full', 'proportional', 'equity_method', 'not_consolidated')),
    effective_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id, parent_entity_id, child_entity_id),
    FOREIGN KEY (tenant_id, org_id, parent_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, org_id, child_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    CHECK (parent_entity_id != child_entity_id)
);
CREATE INDEX IF NOT EXISTS idx_org_ownership_parent ON org_ownership_links(tenant_id, org_id, parent_entity_id);
CREATE INDEX IF NOT EXISTS idx_org_ownership_child ON org_ownership_links(tenant_id, org_id, child_entity_id);
CREATE TABLE IF NOT EXISTS org_intercompany_links (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    link_id text NOT NULL,
    from_entity_id text NOT NULL,
    to_entity_id text NOT NULL,
    link_type text NOT NULL
        CHECK (link_type IN ('management_fee', 'royalty', 'loan', 'trade', 'dividend')),
    description text,
    driver_ref text,
    amount_or_rate numeric,
    frequency text DEFAULT 'monthly'
        CHECK (frequency IN ('monthly', 'quarterly', 'annual', 'one_time')),
    withholding_tax_applicable boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id, link_id),
    FOREIGN KEY (tenant_id, org_id, from_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, org_id, to_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    CHECK (from_entity_id != to_entity_id)
);
CREATE INDEX IF NOT EXISTS idx_org_intercompany_org ON org_intercompany_links(tenant_id, org_id);
CREATE TABLE IF NOT EXISTS consolidated_runs (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    consolidated_run_id text NOT NULL,
    org_id text NOT NULL,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    entity_run_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    consolidation_adjustments_json jsonb DEFAULT '{}'::jsonb,
    fx_rates_used_json jsonb DEFAULT '{}'::jsonb,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text REFERENCES users(id) ON DELETE SET NULL,
    completed_at timestamptz,
    PRIMARY KEY (tenant_id, consolidated_run_id),
    FOREIGN KEY (tenant_id, org_id)
        REFERENCES org_structures(tenant_id, org_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_consolidated_runs_org ON consolidated_runs(tenant_id, org_id);
ALTER TABLE org_structures ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_ownership_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_intercompany_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE consolidated_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "org_structures_select" ON org_structures;
DROP POLICY IF EXISTS "org_structures_insert" ON org_structures;
DROP POLICY IF EXISTS "org_structures_update" ON org_structures;
DROP POLICY IF EXISTS "org_structures_delete" ON org_structures;
CREATE POLICY "org_structures_select" ON org_structures FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_structures_insert" ON org_structures FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_structures_update" ON org_structures FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_structures_delete" ON org_structures FOR DELETE USING (tenant_id = current_tenant_id());
DROP POLICY IF EXISTS "org_entities_select" ON org_entities;
DROP POLICY IF EXISTS "org_entities_insert" ON org_entities;
DROP POLICY IF EXISTS "org_entities_update" ON org_entities;
DROP POLICY IF EXISTS "org_entities_delete" ON org_entities;
CREATE POLICY "org_entities_select" ON org_entities FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_entities_insert" ON org_entities FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_entities_update" ON org_entities FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_entities_delete" ON org_entities FOR DELETE USING (tenant_id = current_tenant_id());
DROP POLICY IF EXISTS "org_ownership_links_select" ON org_ownership_links;
DROP POLICY IF EXISTS "org_ownership_links_insert" ON org_ownership_links;
DROP POLICY IF EXISTS "org_ownership_links_update" ON org_ownership_links;
DROP POLICY IF EXISTS "org_ownership_links_delete" ON org_ownership_links;
CREATE POLICY "org_ownership_links_select" ON org_ownership_links FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_ownership_links_insert" ON org_ownership_links FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_ownership_links_update" ON org_ownership_links FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_ownership_links_delete" ON org_ownership_links FOR DELETE USING (tenant_id = current_tenant_id());
DROP POLICY IF EXISTS "org_intercompany_links_select" ON org_intercompany_links;
DROP POLICY IF EXISTS "org_intercompany_links_insert" ON org_intercompany_links;
DROP POLICY IF EXISTS "org_intercompany_links_update" ON org_intercompany_links;
DROP POLICY IF EXISTS "org_intercompany_links_delete" ON org_intercompany_links;
CREATE POLICY "org_intercompany_links_select" ON org_intercompany_links FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_intercompany_links_insert" ON org_intercompany_links FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_intercompany_links_update" ON org_intercompany_links FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_intercompany_links_delete" ON org_intercompany_links FOR DELETE USING (tenant_id = current_tenant_id());
DROP POLICY IF EXISTS "consolidated_runs_select" ON consolidated_runs;
DROP POLICY IF EXISTS "consolidated_runs_insert" ON consolidated_runs;
DROP POLICY IF EXISTS "consolidated_runs_update" ON consolidated_runs;
DROP POLICY IF EXISTS "consolidated_runs_delete" ON consolidated_runs;
CREATE POLICY "consolidated_runs_select" ON consolidated_runs FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "consolidated_runs_insert" ON consolidated_runs FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "consolidated_runs_update" ON consolidated_runs FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "consolidated_runs_delete" ON consolidated_runs FOR DELETE USING (tenant_id = current_tenant_id());

-- ############################################################################
-- 0046_fix_llm_usage_log_rls.sql — Use current_tenant_id() for RLS (Round 12 H-03)
-- ############################################################################
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'llm_usage_log') THEN
    DROP POLICY IF EXISTS llm_usage_log_select ON llm_usage_log;
    DROP POLICY IF EXISTS llm_usage_log_insert ON llm_usage_log;
    CREATE POLICY "llm_usage_log_select" ON llm_usage_log
      FOR SELECT USING (tenant_id = current_tenant_id());
    CREATE POLICY "llm_usage_log_insert" ON llm_usage_log
      FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
  END IF;
END $$;

-- ############################################################################
-- 0047_order_by_indexes.sql — Covering indexes for list ORDER BY created_at DESC
-- ############################################################################
CREATE INDEX IF NOT EXISTS idx_excel_ingestion_tenant_created
    ON excel_ingestion_sessions(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_consolidated_runs_org_created
    ON consolidated_runs(tenant_id, org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_org_structures_tenant_created
    ON org_structures(tenant_id, created_at DESC);
