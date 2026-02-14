-- =============================================================================
-- Virtual Analyst — Pending migrations (0008 through 0019)
-- Run in order against your database. Skip any you have already applied.
-- Prerequisites: migrations 0001–0007 must already be applied (tenants, users,
-- model_baselines, runs, etc.).
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
