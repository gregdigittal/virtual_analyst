-- VA-P7-03/04/05: Budget actuals (import/variance); confidence on line items (LLM seeding/reforecast).
-- Prerequisite: 0025_budgets.sql must be applied first (creates budget_line_items, budgets, etc.).

-- Optional confidence score on line items (0.0–1.0) for LLM-proposed amounts
do $$
begin
  if exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'budget_line_items') then
    alter table budget_line_items add column if not exists confidence_score numeric;
    comment on column budget_line_items.confidence_score is 'Optional 0-1 confidence from LLM budget_initialization or budget_reforecast.';
  end if;
end $$;

-- Actuals: per budget, per period, per account (and optional department). Source = csv | erp.
-- Only create if budgets table exists (0025 applied).
do $$
begin
  if exists (select 1 from information_schema.tables where table_schema = 'public' and table_name = 'budgets') then
    create table if not exists budget_actuals (
      tenant_id text not null references tenants(id) on delete cascade,
      budget_id text not null,
      period_ordinal int not null,
      account_ref text not null,
      amount numeric not null,
      department_ref text not null default '',
      source text not null check (source in ('csv', 'erp')),
      created_at timestamptz not null default now(),
      primary key (tenant_id, budget_id, period_ordinal, account_ref, department_ref),
      foreign key (tenant_id, budget_id) references budgets(tenant_id, budget_id) on delete cascade
    );
    create index if not exists idx_budget_actuals_budget_period on budget_actuals(tenant_id, budget_id, period_ordinal);
    create index if not exists idx_budget_actuals_department on budget_actuals(tenant_id, budget_id, department_ref) where department_ref != '';
    alter table budget_actuals enable row level security;
    drop policy if exists "budget_actuals_select" on budget_actuals;
    drop policy if exists "budget_actuals_insert" on budget_actuals;
    drop policy if exists "budget_actuals_update" on budget_actuals;
    drop policy if exists "budget_actuals_delete" on budget_actuals;
    create policy "budget_actuals_select" on budget_actuals for select using (tenant_id = current_setting('app.tenant_id', true));
    create policy "budget_actuals_insert" on budget_actuals for insert with check (tenant_id = current_setting('app.tenant_id', true));
    create policy "budget_actuals_update" on budget_actuals for update using (tenant_id = current_setting('app.tenant_id', true));
    create policy "budget_actuals_delete" on budget_actuals for delete using (tenant_id = current_setting('app.tenant_id', true));
  end if;
end $$;
