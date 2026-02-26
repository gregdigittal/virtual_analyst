-- 0052_afs.sql — AFS Module Phase 1
-- Tables: afs_frameworks, afs_disclosure_items, afs_engagements, afs_trial_balances,
--         afs_prior_afs, afs_source_discrepancies, afs_month_projections
-- All tables tenant-scoped with RLS.

-- ============================================================
-- AFS_FRAMEWORKS (accounting standard definitions)
-- ============================================================
create table if not exists afs_frameworks (
  tenant_id text not null references tenants(id) on delete cascade,
  framework_id text not null,
  name text not null,
  standard text not null check (standard in ('ifrs','ifrs_sme','us_gaap','sa_companies_act','custom')),
  version text not null default '1.0',
  jurisdiction text,
  disclosure_schema_json jsonb,
  statement_templates_json jsonb,
  is_builtin boolean not null default false,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, framework_id)
);
create index if not exists idx_afs_frameworks_tenant on afs_frameworks(tenant_id);

-- ============================================================
-- AFS_DISCLOSURE_ITEMS (checklist items per framework)
-- ============================================================
create table if not exists afs_disclosure_items (
  tenant_id text not null references tenants(id) on delete cascade,
  item_id text not null,
  framework_id text not null,
  section text not null,
  reference text,
  description text not null,
  required boolean not null default true,
  applicable_entity_types text[],
  primary key (tenant_id, item_id),
  foreign key (tenant_id, framework_id) references afs_frameworks(tenant_id, framework_id) on delete cascade
);
create index if not exists idx_afs_disclosure_items_framework on afs_disclosure_items(tenant_id, framework_id);

-- ============================================================
-- AFS_ENGAGEMENTS (one engagement per entity per period)
-- ============================================================
create table if not exists afs_engagements (
  tenant_id text not null references tenants(id) on delete cascade,
  engagement_id text not null,
  entity_name text not null,
  framework_id text not null,
  period_start date not null,
  period_end date not null,
  prior_engagement_id text,
  status text not null check (status in ('setup','ingestion','drafting','review','approved','published')) default 'setup',
  base_source text check (base_source in ('pdf','excel','va_baseline')),
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id, engagement_id),
  foreign key (tenant_id, framework_id) references afs_frameworks(tenant_id, framework_id) on delete restrict
);
create index if not exists idx_afs_engagements_tenant on afs_engagements(tenant_id);
create index if not exists idx_afs_engagements_status on afs_engagements(tenant_id, status);

-- ============================================================
-- AFS_TRIAL_BALANCES (imported trial balance data)
-- ============================================================
create table if not exists afs_trial_balances (
  tenant_id text not null references tenants(id) on delete cascade,
  trial_balance_id text not null,
  engagement_id text not null,
  entity_id text,
  source text not null check (source in ('va_baseline','upload','connector','pdf_extracted')),
  data_json jsonb not null default '[]'::jsonb,
  mapped_accounts_json jsonb,
  period_months text[],
  is_partial boolean not null default false,
  uploaded_at timestamptz not null default now(),
  primary key (tenant_id, trial_balance_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_trial_balances_engagement on afs_trial_balances(tenant_id, engagement_id);

-- ============================================================
-- AFS_PRIOR_AFS (prior-year AFS uploads: PDF and/or Excel)
-- ============================================================
create table if not exists afs_prior_afs (
  tenant_id text not null references tenants(id) on delete cascade,
  prior_afs_id text not null,
  engagement_id text not null,
  source_type text not null check (source_type in ('pdf','excel')),
  filename text not null,
  file_size integer,
  extracted_json jsonb,
  upload_path text,
  uploaded_at timestamptz not null default now(),
  primary key (tenant_id, prior_afs_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_prior_afs_engagement on afs_prior_afs(tenant_id, engagement_id);

-- ============================================================
-- AFS_SOURCE_DISCREPANCIES (PDF vs Excel reconciliation)
-- ============================================================
create table if not exists afs_source_discrepancies (
  tenant_id text not null references tenants(id) on delete cascade,
  discrepancy_id text not null,
  engagement_id text not null,
  line_item text not null,
  pdf_value numeric,
  excel_value numeric,
  difference numeric,
  resolution text check (resolution in ('use_pdf','use_excel','noted')),
  resolution_note text,
  resolved_by text references users(id) on delete set null,
  resolved_at timestamptz,
  primary key (tenant_id, discrepancy_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_source_discrepancies_engagement on afs_source_discrepancies(tenant_id, engagement_id);

-- ============================================================
-- AFS_MONTH_PROJECTIONS (AI-projected missing months)
-- ============================================================
create table if not exists afs_month_projections (
  tenant_id text not null references tenants(id) on delete cascade,
  projection_id text not null,
  engagement_id text not null,
  month text not null,
  basis_description text not null,
  projected_data_json jsonb not null default '{}'::jsonb,
  is_estimate boolean not null default true,
  created_by text references users(id) on delete set null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, projection_id),
  foreign key (tenant_id, engagement_id) references afs_engagements(tenant_id, engagement_id) on delete cascade
);
create index if not exists idx_afs_month_projections_engagement on afs_month_projections(tenant_id, engagement_id);

-- ============================================================
-- RLS
-- ============================================================
alter table afs_frameworks enable row level security;
drop policy if exists "afs_frameworks_select" on afs_frameworks;
drop policy if exists "afs_frameworks_insert" on afs_frameworks;
drop policy if exists "afs_frameworks_update" on afs_frameworks;
drop policy if exists "afs_frameworks_delete" on afs_frameworks;
create policy "afs_frameworks_select" on afs_frameworks for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_frameworks_insert" on afs_frameworks for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_frameworks_update" on afs_frameworks for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_frameworks_delete" on afs_frameworks for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_disclosure_items enable row level security;
drop policy if exists "afs_disclosure_items_select" on afs_disclosure_items;
drop policy if exists "afs_disclosure_items_insert" on afs_disclosure_items;
drop policy if exists "afs_disclosure_items_update" on afs_disclosure_items;
drop policy if exists "afs_disclosure_items_delete" on afs_disclosure_items;
create policy "afs_disclosure_items_select" on afs_disclosure_items for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_disclosure_items_insert" on afs_disclosure_items for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_disclosure_items_update" on afs_disclosure_items for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_disclosure_items_delete" on afs_disclosure_items for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_engagements enable row level security;
drop policy if exists "afs_engagements_select" on afs_engagements;
drop policy if exists "afs_engagements_insert" on afs_engagements;
drop policy if exists "afs_engagements_update" on afs_engagements;
drop policy if exists "afs_engagements_delete" on afs_engagements;
create policy "afs_engagements_select" on afs_engagements for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_engagements_insert" on afs_engagements for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_engagements_update" on afs_engagements for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_engagements_delete" on afs_engagements for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_trial_balances enable row level security;
drop policy if exists "afs_trial_balances_select" on afs_trial_balances;
drop policy if exists "afs_trial_balances_insert" on afs_trial_balances;
drop policy if exists "afs_trial_balances_update" on afs_trial_balances;
drop policy if exists "afs_trial_balances_delete" on afs_trial_balances;
create policy "afs_trial_balances_select" on afs_trial_balances for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_trial_balances_insert" on afs_trial_balances for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_trial_balances_update" on afs_trial_balances for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_trial_balances_delete" on afs_trial_balances for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_prior_afs enable row level security;
drop policy if exists "afs_prior_afs_select" on afs_prior_afs;
drop policy if exists "afs_prior_afs_insert" on afs_prior_afs;
drop policy if exists "afs_prior_afs_update" on afs_prior_afs;
drop policy if exists "afs_prior_afs_delete" on afs_prior_afs;
create policy "afs_prior_afs_select" on afs_prior_afs for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_prior_afs_insert" on afs_prior_afs for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_prior_afs_update" on afs_prior_afs for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_prior_afs_delete" on afs_prior_afs for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_source_discrepancies enable row level security;
drop policy if exists "afs_source_discrepancies_select" on afs_source_discrepancies;
drop policy if exists "afs_source_discrepancies_insert" on afs_source_discrepancies;
drop policy if exists "afs_source_discrepancies_update" on afs_source_discrepancies;
drop policy if exists "afs_source_discrepancies_delete" on afs_source_discrepancies;
create policy "afs_source_discrepancies_select" on afs_source_discrepancies for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_source_discrepancies_insert" on afs_source_discrepancies for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_source_discrepancies_update" on afs_source_discrepancies for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_source_discrepancies_delete" on afs_source_discrepancies for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table afs_month_projections enable row level security;
drop policy if exists "afs_month_projections_select" on afs_month_projections;
drop policy if exists "afs_month_projections_insert" on afs_month_projections;
drop policy if exists "afs_month_projections_update" on afs_month_projections;
drop policy if exists "afs_month_projections_delete" on afs_month_projections;
create policy "afs_month_projections_select" on afs_month_projections for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_month_projections_insert" on afs_month_projections for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_month_projections_update" on afs_month_projections for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "afs_month_projections_delete" on afs_month_projections for delete using (tenant_id = current_setting('app.tenant_id', true));
