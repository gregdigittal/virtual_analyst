-- 0059_pim_universes.sql
-- PIM-1.1: Company universe definitions per tenant.
-- Each row is a company in a tenant's investable universe.

create table if not exists pim_universes (
  tenant_id       text not null references tenants(id) on delete cascade,
  company_id      text not null,
  ticker          text not null,
  company_name    text not null,
  sector          text,              -- GICS sector (e.g. "Information Technology")
  sub_sector      text,              -- GICS sub-industry
  country_iso     text,              -- ISO 3166-1 alpha-2
  market_cap_usd  double precision,  -- latest market cap in USD
  currency        text,              -- trading currency (ISO 4217)
  exchange        text,              -- exchange code (e.g. "XNYS", "XJSE")
  is_active       boolean not null default true,
  tags            jsonb not null default '[]'::jsonb,  -- custom user tags
  notes           text,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  created_by      text references users(id) on delete set null,
  primary key (tenant_id, company_id)
);

create index if not exists idx_pim_universes_tenant on pim_universes(tenant_id);
create index if not exists idx_pim_universes_ticker on pim_universes(tenant_id, ticker);
create index if not exists idx_pim_universes_sector on pim_universes(tenant_id, sector);
create index if not exists idx_pim_universes_active on pim_universes(tenant_id, is_active);

-- RLS policy (same pattern as other tenant-scoped tables)
alter table pim_universes enable row level security;

create policy pim_universes_tenant_isolation on pim_universes
  using (tenant_id = current_setting('app.tenant_id', true))
  with check (tenant_id = current_setting('app.tenant_id', true));

-- updated_at trigger
create or replace function pim_universes_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

drop trigger if exists trg_pim_universes_updated_at on pim_universes;
create trigger trg_pim_universes_updated_at
  before update on pim_universes
  for each row execute function pim_universes_updated_at();
