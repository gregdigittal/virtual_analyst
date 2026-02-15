-- VA-P7-01: Budget data model & migrations
-- Tables: budgets, budget_versions, budget_periods, budget_line_items, budget_department_allocations
-- Budget lifecycle: draft → submitted → under_review → approved → active → closed
-- Versioning: immutable budget_versions per budget; line items and allocations are per-version.

-- ============================================================
-- BUDGETS (metadata; current_version_id added after versions table)
-- ============================================================
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

-- ============================================================
-- BUDGET VERSIONS (immutable snapshots; revision history)
-- ============================================================
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

-- Point budgets to their current snapshot (after versions exist)
alter table budgets add column if not exists current_version_id text;
alter table budgets drop constraint if exists fk_budgets_current_version;
alter table budgets
  add constraint fk_budgets_current_version
  foreign key (tenant_id, budget_id, current_version_id)
  references budget_versions(tenant_id, budget_id, version_id) on delete set null;

-- ============================================================
-- BUDGET PERIODS (time buckets for this budget, e.g. monthly)
-- ============================================================
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

-- ============================================================
-- BUDGET LINE ITEMS (per version; account + monthly amounts)
-- ============================================================
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

-- Amounts per period (monthly granularity)
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

-- ============================================================
-- BUDGET DEPARTMENT ALLOCATIONS (per version; department limits)
-- ============================================================
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

-- ============================================================
-- RLS
-- ============================================================
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
