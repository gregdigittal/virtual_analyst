-- 0053_afs_sections.sql — AFS Phase 2: sections and section history

-- ============================================================
-- AFS_SECTIONS (generated statement sections/notes)
-- ============================================================
create table if not exists afs_sections (
  tenant_id text not null references tenants(id) on delete cascade,
  section_id text not null,
  engagement_id text not null,
  section_type text not null check (section_type in ('note','statement','directors_report','accounting_policy')),
  section_number integer not null default 0,
  title text not null,
  content_json jsonb not null default '{}'::jsonb,
  status text not null check (status in ('draft','reviewed','locked')) default 'draft',
  version integer not null default 1,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, section_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_sections_engagement on afs_sections(tenant_id, engagement_id);
create unique index if not exists idx_afs_sections_number on afs_sections(tenant_id, engagement_id, section_number);

-- ============================================================
-- AFS_SECTION_HISTORY (version history per section)
-- ============================================================
create table if not exists afs_section_history (
  tenant_id text not null references tenants(id) on delete cascade,
  history_id text not null,
  section_id text not null,
  version integer not null,
  content_json jsonb not null default '{}'::jsonb,
  nl_instruction text,
  changed_by text references users(id) on delete set null,
  changed_at timestamptz not null default now(),
  primary key (tenant_id, history_id),
  foreign key (tenant_id, section_id) references afs_sections(tenant_id, section_id) on delete cascade
);
create index if not exists idx_afs_section_history_section on afs_section_history(tenant_id, section_id);

-- ============================================================
-- RLS
-- ============================================================
alter table afs_sections enable row level security;
drop policy if exists "afs_sections_select" on afs_sections;
drop policy if exists "afs_sections_insert" on afs_sections;
drop policy if exists "afs_sections_update" on afs_sections;
drop policy if exists "afs_sections_delete" on afs_sections;
create policy "afs_sections_select" on afs_sections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_sections_insert" on afs_sections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_sections_update" on afs_sections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_sections_delete" on afs_sections for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_section_history enable row level security;
drop policy if exists "afs_section_history_select" on afs_section_history;
drop policy if exists "afs_section_history_insert" on afs_section_history;
drop policy if exists "afs_section_history_update" on afs_section_history;
drop policy if exists "afs_section_history_delete" on afs_section_history;
create policy "afs_section_history_select" on afs_section_history for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_section_history_insert" on afs_section_history for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_section_history_update" on afs_section_history for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_section_history_delete" on afs_section_history for delete using (tenant_id = current_setting('app.tenant_id', true));
