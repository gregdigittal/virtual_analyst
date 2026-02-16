-- VA-P8-06: Workflow analytics — per-stage timing (optional events for cycle time and bottlenecks).

create table if not exists workflow_events (
  tenant_id text not null references tenants(id) on delete cascade,
  instance_id text not null,
  stage_index integer not null,
  entered_at timestamptz not null,
  exited_at timestamptz,
  outcome text check (outcome is null or outcome in ('submitted', 'approved', 'returned', 'completed')),
  primary key (tenant_id, instance_id, stage_index, entered_at),
  foreign key (tenant_id, instance_id) references workflow_instances(tenant_id, instance_id) on delete cascade
);
create index if not exists idx_workflow_events_tenant_entered on workflow_events(tenant_id, entered_at);

alter table workflow_events enable row level security;
drop policy if exists "workflow_events_select" on workflow_events;
drop policy if exists "workflow_events_insert" on workflow_events;
drop policy if exists "workflow_events_update" on workflow_events;
drop policy if exists "workflow_events_delete" on workflow_events;
create policy "workflow_events_select" on workflow_events for select using (tenant_id = current_tenant_id());
create policy "workflow_events_insert" on workflow_events for insert with check (tenant_id = current_tenant_id());
create policy "workflow_events_update" on workflow_events for update using (tenant_id = current_tenant_id());
create policy "workflow_events_delete" on workflow_events for delete using (tenant_id = current_tenant_id());
