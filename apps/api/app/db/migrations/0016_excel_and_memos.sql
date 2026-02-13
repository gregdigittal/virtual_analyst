-- VA-P5: Excel live links and memo pack tables (Phase 5)

-- ============================================================
-- EXCEL LIVE LINKS
-- ============================================================

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

-- ============================================================
-- MEMO PACKS
-- ============================================================

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

-- ============================================================
-- RLS POLICIES
-- ============================================================

alter table excel_connections enable row level security;
drop policy if exists "excel_connections_select" on excel_connections;
drop policy if exists "excel_connections_insert" on excel_connections;
drop policy if exists "excel_connections_update" on excel_connections;
drop policy if exists "excel_connections_delete" on excel_connections;
create policy "excel_connections_select" on excel_connections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "excel_connections_insert" on excel_connections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "excel_connections_update" on excel_connections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "excel_connections_delete" on excel_connections for delete using (tenant_id = current_setting('app.tenant_id', true));

-- excel_sync_events: append-only event log. No UPDATE/DELETE policies (intentional).
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
