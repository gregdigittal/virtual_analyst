-- 0055_afs_consolidation_outputs.sql — AFS Phase 4: consolidation rules & output tracking

-- ============================================================
-- AFS_CONSOLIDATION_RULES (links engagement to org-structure)
-- ============================================================
create table if not exists afs_consolidation_rules (
  tenant_id text not null references tenants(id) on delete cascade,
  consolidation_id text not null,
  engagement_id text not null,
  org_id text not null,
  reporting_currency text not null default 'ZAR',
  fx_avg_rates jsonb not null default '{}'::jsonb,
  fx_closing_rates jsonb not null default '{}'::jsonb,
  elimination_entries_json jsonb not null default '[]'::jsonb,
  consolidated_tb_json jsonb,
  entity_tb_map jsonb not null default '{}'::jsonb,
  status text not null check (status in ('pending','consolidated','error')) default 'pending',
  error_message text,
  consolidated_at timestamptz,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, consolidation_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_consol_engagement on afs_consolidation_rules(tenant_id, engagement_id);

-- ============================================================
-- AFS_OUTPUTS (generated document files)
-- ============================================================
create table if not exists afs_outputs (
  tenant_id text not null references tenants(id) on delete cascade,
  output_id text not null,
  engagement_id text not null,
  format text not null check (format in ('pdf','docx','ixbrl','excel')),
  filename text not null,
  file_size_bytes bigint,
  artifact_key text,
  status text not null check (status in ('generating','ready','error')) default 'generating',
  error_message text,
  generated_by text references users(id) on delete set null,
  generated_at timestamptz not null default now(),
  primary key (tenant_id, output_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_outputs_engagement on afs_outputs(tenant_id, engagement_id);

-- ============================================================
-- RLS
-- ============================================================

-- afs_consolidation_rules
alter table afs_consolidation_rules enable row level security;
drop policy if exists "afs_consolidation_rules_select" on afs_consolidation_rules;
drop policy if exists "afs_consolidation_rules_insert" on afs_consolidation_rules;
drop policy if exists "afs_consolidation_rules_update" on afs_consolidation_rules;
drop policy if exists "afs_consolidation_rules_delete" on afs_consolidation_rules;
create policy "afs_consolidation_rules_select" on afs_consolidation_rules for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_consolidation_rules_insert" on afs_consolidation_rules for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_consolidation_rules_update" on afs_consolidation_rules for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_consolidation_rules_delete" on afs_consolidation_rules for delete using (tenant_id = current_setting('app.tenant_id', true));

-- afs_outputs
alter table afs_outputs enable row level security;
drop policy if exists "afs_outputs_select" on afs_outputs;
drop policy if exists "afs_outputs_insert" on afs_outputs;
drop policy if exists "afs_outputs_update" on afs_outputs;
drop policy if exists "afs_outputs_delete" on afs_outputs;
create policy "afs_outputs_select" on afs_outputs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_outputs_insert" on afs_outputs for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_outputs_update" on afs_outputs for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_outputs_delete" on afs_outputs for delete using (tenant_id = current_setting('app.tenant_id', true));
