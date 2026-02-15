-- 0001_init.sql
-- Core schema for Virtual Analyst (Postgres/Supabase friendly).
-- Run this before 0002 and before RUN_ALL_PENDING_MIGRATIONS.sql (0008-0019).

create table if not exists tenants (
  id text primary key,
  name text not null,
  created_at timestamptz not null default now()
);

create table if not exists users (
  id text primary key,
  tenant_id text not null references tenants(id) on delete cascade,
  email text,
  role text not null check (role in ('owner','investor','analyst','admin')),
  created_at timestamptz not null default now()
);
create index if not exists idx_users_tenant_id on users(tenant_id);

create table if not exists draft_sessions (
  tenant_id text not null references tenants(id) on delete cascade,
  draft_session_id text not null,
  parent_baseline_id text,
  parent_baseline_version text,
  status text not null check (status in ('active','ready_to_commit','committed','abandoned')),
  storage_path text not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, draft_session_id)
);
create index if not exists idx_draft_sessions_tenant_status on draft_sessions(tenant_id, status);
create index if not exists idx_draft_sessions_parent on draft_sessions(tenant_id, parent_baseline_id, parent_baseline_version);

create table if not exists model_baselines (
  tenant_id text not null references tenants(id) on delete cascade,
  baseline_id text not null,
  baseline_version text not null,
  status text not null check (status in ('active','archived')),
  storage_path text not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  is_active boolean not null default false,
  primary key (tenant_id, baseline_id, baseline_version)
);
create index if not exists idx_model_baselines_active on model_baselines(tenant_id, is_active);
create index if not exists idx_model_baselines_status on model_baselines(tenant_id, status);

create unique index if not exists uq_one_active_baseline_per_tenant
on model_baselines(tenant_id)
where is_active = true;

create table if not exists model_changesets (
  tenant_id text not null references tenants(id) on delete cascade,
  changeset_id text not null,
  baseline_id text not null,
  base_version text not null,
  status text not null check (status in ('draft','tested','merged','abandoned')),
  storage_path text not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, changeset_id),
  foreign key (tenant_id, baseline_id, base_version)
    references model_baselines(tenant_id, baseline_id, baseline_version)
    on delete restrict
);
create index if not exists idx_changesets_baseline on model_changesets(tenant_id, baseline_id, base_version);
create index if not exists idx_changesets_status on model_changesets(tenant_id, status);

create table if not exists ventures (
  tenant_id text not null references tenants(id) on delete cascade,
  venture_id text not null,
  status text not null check (status in ('draft','locked','archived')),
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  latest_instance_path text,
  primary key (tenant_id, venture_id)
);
create index if not exists idx_ventures_tenant_status on ventures(tenant_id, status);

create table if not exists venture_artifacts (
  tenant_id text not null references tenants(id) on delete cascade,
  venture_id text not null,
  artifact_type text not null,
  storage_path text not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, venture_id, artifact_type, storage_path),
  foreign key (tenant_id, venture_id)
    references ventures(tenant_id, venture_id)
    on delete cascade
);
create index if not exists idx_venture_artifacts_lookup on venture_artifacts(tenant_id, venture_id, artifact_type);

create table if not exists runs (
  tenant_id text not null references tenants(id) on delete cascade,
  run_id text not null,
  baseline_id text not null,
  baseline_version text not null,
  scenario_id text,
  mc_enabled boolean not null default false,
  num_simulations integer,
  status text not null check (status in ('queued','running','succeeded','failed')),
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, run_id),
  foreign key (tenant_id, baseline_id, baseline_version)
    references model_baselines(tenant_id, baseline_id, baseline_version)
    on delete restrict
);
create index if not exists idx_runs_tenant_status on runs(tenant_id, status);
create index if not exists idx_runs_baseline on runs(tenant_id, baseline_id, baseline_version);

create table if not exists run_artifacts (
  tenant_id text not null references tenants(id) on delete cascade,
  run_id text not null,
  artifact_type text not null,
  storage_path text not null,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, run_id, artifact_type, storage_path),
  foreign key (tenant_id, run_id)
    references runs(tenant_id, run_id)
    on delete cascade
);
create index if not exists idx_run_artifacts_lookup on run_artifacts(tenant_id, run_id, artifact_type);
