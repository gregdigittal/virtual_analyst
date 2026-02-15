-- 0002_functions_and_rls.sql
-- Helper functions + RLS policies for core tables.
-- Run after 0001_init.sql; required before 0008-0019.

-- Helper: get current tenant from session variable
create or replace function current_tenant_id() returns text as $$
  select coalesce(
    current_setting('app.tenant_id', true),
    ''
  );
$$ language sql stable;

-- Helper: generate prefixed IDs
create or replace function generate_id(prefix text) returns text as $$
  select prefix || '_' || replace(gen_random_uuid()::text, '-', '');
$$ language sql volatile;

-- RLS on tenants (users can only see their own tenant)
alter table tenants enable row level security;
drop policy if exists "tenants_select" on tenants;
drop policy if exists "tenants_update" on tenants;
create policy "tenants_select" on tenants for select using (id = current_tenant_id());
create policy "tenants_update" on tenants for update using (id = current_tenant_id());

-- RLS on users
alter table users enable row level security;
drop policy if exists "users_select" on users;
drop policy if exists "users_insert" on users;
drop policy if exists "users_update" on users;
drop policy if exists "users_delete" on users;
create policy "users_select" on users for select using (tenant_id = current_tenant_id());
create policy "users_insert" on users for insert with check (tenant_id = current_tenant_id());
create policy "users_update" on users for update using (tenant_id = current_tenant_id());
create policy "users_delete" on users for delete using (tenant_id = current_tenant_id());

-- RLS on draft_sessions
alter table draft_sessions enable row level security;
drop policy if exists "draft_sessions_select" on draft_sessions;
drop policy if exists "draft_sessions_insert" on draft_sessions;
drop policy if exists "draft_sessions_update" on draft_sessions;
drop policy if exists "draft_sessions_delete" on draft_sessions;
create policy "draft_sessions_select" on draft_sessions for select using (tenant_id = current_tenant_id());
create policy "draft_sessions_insert" on draft_sessions for insert with check (tenant_id = current_tenant_id());
create policy "draft_sessions_update" on draft_sessions for update using (tenant_id = current_tenant_id());
create policy "draft_sessions_delete" on draft_sessions for delete using (tenant_id = current_tenant_id());

-- RLS on model_baselines
alter table model_baselines enable row level security;
drop policy if exists "model_baselines_select" on model_baselines;
drop policy if exists "model_baselines_insert" on model_baselines;
drop policy if exists "model_baselines_update" on model_baselines;
create policy "model_baselines_select" on model_baselines for select using (tenant_id = current_tenant_id());
create policy "model_baselines_insert" on model_baselines for insert with check (tenant_id = current_tenant_id());
create policy "model_baselines_update" on model_baselines for update using (tenant_id = current_tenant_id());

-- RLS on model_changesets
alter table model_changesets enable row level security;
drop policy if exists "model_changesets_select" on model_changesets;
drop policy if exists "model_changesets_insert" on model_changesets;
drop policy if exists "model_changesets_update" on model_changesets;
create policy "model_changesets_select" on model_changesets for select using (tenant_id = current_tenant_id());
create policy "model_changesets_insert" on model_changesets for insert with check (tenant_id = current_tenant_id());
create policy "model_changesets_update" on model_changesets for update using (tenant_id = current_tenant_id());

-- RLS on ventures
alter table ventures enable row level security;
drop policy if exists "ventures_select" on ventures;
drop policy if exists "ventures_insert" on ventures;
drop policy if exists "ventures_update" on ventures;
create policy "ventures_select" on ventures for select using (tenant_id = current_tenant_id());
create policy "ventures_insert" on ventures for insert with check (tenant_id = current_tenant_id());
create policy "ventures_update" on ventures for update using (tenant_id = current_tenant_id());

-- RLS on venture_artifacts
alter table venture_artifacts enable row level security;
drop policy if exists "venture_artifacts_select" on venture_artifacts;
drop policy if exists "venture_artifacts_insert" on venture_artifacts;
create policy "venture_artifacts_select" on venture_artifacts for select using (tenant_id = current_tenant_id());
create policy "venture_artifacts_insert" on venture_artifacts for insert with check (tenant_id = current_tenant_id());

-- RLS on runs
alter table runs enable row level security;
drop policy if exists "runs_select" on runs;
drop policy if exists "runs_insert" on runs;
drop policy if exists "runs_update" on runs;
create policy "runs_select" on runs for select using (tenant_id = current_tenant_id());
create policy "runs_insert" on runs for insert with check (tenant_id = current_tenant_id());
create policy "runs_update" on runs for update using (tenant_id = current_tenant_id());

-- RLS on run_artifacts
alter table run_artifacts enable row level security;
drop policy if exists "run_artifacts_select" on run_artifacts;
drop policy if exists "run_artifacts_insert" on run_artifacts;
create policy "run_artifacts_select" on run_artifacts for select using (tenant_id = current_tenant_id());
create policy "run_artifacts_insert" on run_artifacts for insert with check (tenant_id = current_tenant_id());
