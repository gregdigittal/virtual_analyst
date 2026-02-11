-- 0003_scenarios.sql
-- Scenario management tables for Phase 3

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

-- Add valuation config to runs
alter table runs add column if not exists valuation_config_json jsonb;
alter table runs add column if not exists seed integer;
alter table runs add column if not exists completed_at timestamptz;
alter table runs add column if not exists error_message text;

-- RLS for scenarios
alter table scenarios enable row level security;

create policy "scenarios_select" on scenarios
  for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "scenarios_insert" on scenarios
  for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "scenarios_update" on scenarios
  for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "scenarios_delete" on scenarios
  for delete using (tenant_id = current_setting('app.tenant_id', true));
