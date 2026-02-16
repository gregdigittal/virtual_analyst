-- VA-P8-01: Multi-currency and FX overlays.
-- Tenant currency settings (base + reporting currency, FX source); FX rates per tenant/period (auditable).

create table if not exists tenant_currency_settings (
  tenant_id text not null references tenants(id) on delete cascade,
  base_currency text not null default 'USD',
  reporting_currency text not null default 'USD',
  fx_source text not null default 'manual' check (fx_source in ('manual', 'feed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id)
);
create index if not exists idx_tenant_currency_settings_tenant on tenant_currency_settings(tenant_id);

create table if not exists fx_rates (
  tenant_id text not null references tenants(id) on delete cascade,
  from_currency text not null,
  to_currency text not null,
  effective_date date not null,
  rate numeric not null check (rate > 0),
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, from_currency, to_currency, effective_date)
);
create index if not exists idx_fx_rates_tenant_date on fx_rates(tenant_id, effective_date);

alter table tenant_currency_settings enable row level security;
drop policy if exists "tenant_currency_settings_select" on tenant_currency_settings;
drop policy if exists "tenant_currency_settings_insert" on tenant_currency_settings;
drop policy if exists "tenant_currency_settings_update" on tenant_currency_settings;
drop policy if exists "tenant_currency_settings_delete" on tenant_currency_settings;
create policy "tenant_currency_settings_select" on tenant_currency_settings for select using (tenant_id = current_tenant_id());
create policy "tenant_currency_settings_insert" on tenant_currency_settings for insert with check (tenant_id = current_tenant_id());
create policy "tenant_currency_settings_update" on tenant_currency_settings for update using (tenant_id = current_tenant_id());
create policy "tenant_currency_settings_delete" on tenant_currency_settings for delete using (tenant_id = current_tenant_id());

alter table fx_rates enable row level security;
drop policy if exists "fx_rates_select" on fx_rates;
drop policy if exists "fx_rates_insert" on fx_rates;
drop policy if exists "fx_rates_update" on fx_rates;
drop policy if exists "fx_rates_delete" on fx_rates;
create policy "fx_rates_select" on fx_rates for select using (tenant_id = current_tenant_id());
create policy "fx_rates_insert" on fx_rates for insert with check (tenant_id = current_tenant_id());
create policy "fx_rates_update" on fx_rates for update using (tenant_id = current_tenant_id());
create policy "fx_rates_delete" on fx_rates for delete using (tenant_id = current_tenant_id());
