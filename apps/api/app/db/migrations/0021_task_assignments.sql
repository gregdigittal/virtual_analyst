-- VA-P6-04: Task assignment system (task_assignments)
-- Status: draft | assigned | in_progress | submitted | approved | returned | completed

create table if not exists task_assignments (
  tenant_id text not null references tenants(id) on delete cascade,
  assignment_id text not null,
  workflow_instance_id text,
  entity_type text not null,
  entity_id text not null,
  assignee_user_id text references users(id) on delete cascade,
  assigned_by_user_id text references users(id) on delete set null,
  status text not null default 'draft'
    check (status in ('draft','assigned','in_progress','submitted','approved','returned','completed')),
  deadline timestamptz,
  instructions text,
  created_at timestamptz not null default now(),
  submitted_at timestamptz,
  primary key (tenant_id, assignment_id)
);
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'fk_task_assignments_workflow') then
    alter table task_assignments
      add constraint fk_task_assignments_workflow
      foreign key (tenant_id, workflow_instance_id) references workflow_instances(tenant_id, instance_id) on delete set null;
  end if;
end $$;
create index if not exists idx_task_assignments_tenant on task_assignments(tenant_id);
create index if not exists idx_task_assignments_assignee on task_assignments(tenant_id, assignee_user_id);
create index if not exists idx_task_assignments_status on task_assignments(tenant_id, status);
create index if not exists idx_task_assignments_entity on task_assignments(tenant_id, entity_type, entity_id);
create index if not exists idx_task_assignments_deadline on task_assignments(tenant_id, deadline) where deadline is not null;

alter table task_assignments enable row level security;
drop policy if exists "task_assignments_select" on task_assignments;
drop policy if exists "task_assignments_insert" on task_assignments;
drop policy if exists "task_assignments_update" on task_assignments;
drop policy if exists "task_assignments_delete" on task_assignments;
create policy "task_assignments_select" on task_assignments for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "task_assignments_insert" on task_assignments for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "task_assignments_update" on task_assignments for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "task_assignments_delete" on task_assignments for delete using (tenant_id = current_setting('app.tenant_id', true));
