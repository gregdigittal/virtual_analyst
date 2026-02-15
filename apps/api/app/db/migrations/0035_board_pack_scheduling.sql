-- VA-P7-09: Board pack scheduling & distribution, pack generation history.

create table if not exists pack_schedules (
  tenant_id text not null references tenants(id) on delete cascade,
  schedule_id text not null,
  label text not null,
  run_id text,
  budget_id text,
  section_order jsonb not null default '["executive_summary","income_statement","balance_sheet","cash_flow","budget_variance","kpi_dashboard","scenario_comparison","strategic_commentary"]'::jsonb,
  cron_expr text not null,
  next_run_at timestamptz,
  distribution_emails text[] default '{}',
  enabled boolean not null default true,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, schedule_id)
);
create index if not exists idx_pack_schedules_tenant_next on pack_schedules(tenant_id, next_run_at) where enabled;

create table if not exists pack_generation_history (
  tenant_id text not null references tenants(id) on delete cascade,
  history_id text not null,
  schedule_id text,
  pack_id text not null,
  label text not null,
  run_id text,
  generated_at timestamptz not null default now(),
  distributed_at timestamptz,
  status text not null default 'ready' check (status in ('ready', 'distributed', 'failed')),
  error_message text,
  primary key (tenant_id, history_id)
);
create index if not exists idx_pack_history_tenant_generated on pack_generation_history(tenant_id, generated_at desc);
create index if not exists idx_pack_history_schedule on pack_generation_history(tenant_id, schedule_id);

alter table pack_schedules enable row level security;
alter table pack_generation_history enable row level security;
drop policy if exists "pack_schedules_select" on pack_schedules;
drop policy if exists "pack_schedules_insert" on pack_schedules;
drop policy if exists "pack_schedules_update" on pack_schedules;
drop policy if exists "pack_schedules_delete" on pack_schedules;
create policy "pack_schedules_select" on pack_schedules for select using (tenant_id = current_tenant_id());
create policy "pack_schedules_insert" on pack_schedules for insert with check (tenant_id = current_tenant_id());
create policy "pack_schedules_update" on pack_schedules for update using (tenant_id = current_tenant_id());
create policy "pack_schedules_delete" on pack_schedules for delete using (tenant_id = current_tenant_id());

drop policy if exists "pack_generation_history_select" on pack_generation_history;
drop policy if exists "pack_generation_history_insert" on pack_generation_history;
drop policy if exists "pack_generation_history_update" on pack_generation_history;
drop policy if exists "pack_generation_history_delete" on pack_generation_history;
create policy "pack_generation_history_select" on pack_generation_history for select using (tenant_id = current_tenant_id());
create policy "pack_generation_history_insert" on pack_generation_history for insert with check (tenant_id = current_tenant_id());
create policy "pack_generation_history_update" on pack_generation_history for update using (tenant_id = current_tenant_id());
create policy "pack_generation_history_delete" on pack_generation_history for delete using (tenant_id = current_tenant_id());
