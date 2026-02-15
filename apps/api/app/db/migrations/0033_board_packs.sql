-- VA-P7-07: Board pack composer — configurable sections, LLM narrative, sources from run/budget.

create table if not exists board_packs (
  tenant_id text not null references tenants(id) on delete cascade,
  pack_id text not null,
  label text not null,
  run_id text,
  budget_id text,
  section_order jsonb not null default '["executive_summary","income_statement","balance_sheet","cash_flow","budget_variance","kpi_dashboard","scenario_comparison","strategic_commentary"]'::jsonb,
  status text not null default 'draft' check (status in ('draft', 'generating', 'ready', 'error')),
  narrative_json jsonb default '{}'::jsonb,
  error_message text,
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  primary key (tenant_id, pack_id)
);
create index if not exists idx_board_packs_tenant on board_packs(tenant_id);
create index if not exists idx_board_packs_status on board_packs(tenant_id, status);

alter table board_packs enable row level security;
drop policy if exists "board_packs_select" on board_packs;
drop policy if exists "board_packs_insert" on board_packs;
drop policy if exists "board_packs_update" on board_packs;
drop policy if exists "board_packs_delete" on board_packs;
create policy "board_packs_select" on board_packs for select using (tenant_id = current_tenant_id());
create policy "board_packs_insert" on board_packs for insert with check (tenant_id = current_tenant_id());
create policy "board_packs_update" on board_packs for update using (tenant_id = current_tenant_id());
create policy "board_packs_delete" on board_packs for delete using (tenant_id = current_tenant_id());
