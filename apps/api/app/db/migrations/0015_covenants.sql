-- VA-P4-05: Covenant monitoring — definitions and breach flag on runs

create table if not exists covenant_definitions (
  tenant_id text not null references tenants(id) on delete cascade,
  covenant_id text not null,
  label text not null,
  metric_ref text not null,
  operator text not null check (operator in ('<', '>', '<=', '>=')),
  threshold_value double precision not null,
  created_at timestamptz not null default now(),
  primary key (tenant_id, covenant_id)
);

create index if not exists idx_covenant_definitions_tenant on covenant_definitions(tenant_id);

comment on table covenant_definitions is 'Covenant thresholds (e.g. debt_equity < 2.5, dscr > 1.2); checked on run completion.';

alter table covenant_definitions enable row level security;

drop policy if exists "covenant_definitions_select" on covenant_definitions;
drop policy if exists "covenant_definitions_insert" on covenant_definitions;
drop policy if exists "covenant_definitions_update" on covenant_definitions;
drop policy if exists "covenant_definitions_delete" on covenant_definitions;

create policy "covenant_definitions_select" on covenant_definitions for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "covenant_definitions_insert" on covenant_definitions for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "covenant_definitions_update" on covenant_definitions for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "covenant_definitions_delete" on covenant_definitions for delete using (tenant_id = current_setting('app.tenant_id', true));

-- Flag on run when any covenant is breached (notification created separately)
alter table runs add column if not exists covenant_breached boolean not null default false;
