-- VA-P4-01: Integration framework — connections, sync runs, canonical snapshots
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

create policy "integration_connections_select" on integration_connections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_insert" on integration_connections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_update" on integration_connections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_connections_delete" on integration_connections for delete using (tenant_id = current_setting('app.tenant_id', true));

create policy "integration_sync_runs_select" on integration_sync_runs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_sync_runs_insert" on integration_sync_runs for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "integration_sync_runs_update" on integration_sync_runs for update using (tenant_id = current_setting('app.tenant_id', true));

create policy "canonical_snapshots_select" on canonical_sync_snapshots for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "canonical_snapshots_insert" on canonical_sync_snapshots for insert with check (tenant_id = current_setting('app.tenant_id', true));

create policy "integration_sync_runs_delete" on integration_sync_runs for delete using (tenant_id = current_setting('app.tenant_id', true));
create policy "canonical_snapshots_delete" on canonical_sync_snapshots for delete using (tenant_id = current_setting('app.tenant_id', true));
