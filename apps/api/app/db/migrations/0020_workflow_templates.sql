-- VA-P6-03: Workflow template engine (workflow_templates, workflow_instances)
-- Stage rules: explicit, reports_to, reports_to_chain, team_pool

-- ============================================================
-- WORKFLOW TEMPLATES (per-tenant)
-- stages_json: array of {stage_id, name, assignee_rule, assignee_config}
-- assignee_rule: explicit | reports_to | reports_to_chain | team_pool
-- assignee_config: optional {user_id?, team_id?} for explicit/team_pool
-- ============================================================
create table if not exists workflow_templates (
  tenant_id text not null references tenants(id) on delete cascade,
  template_id text not null,
  name text not null,
  description text,
  stages_json jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now(),
  primary key (tenant_id, template_id)
);
create index if not exists idx_workflow_templates_tenant on workflow_templates(tenant_id);

-- ============================================================
-- WORKFLOW INSTANCES (one per entity e.g. draft/baseline/run)
-- current_stage_index: 0-based into template.stages_json
-- status: pending | in_progress | submitted | approved | returned | completed
-- ============================================================
create table if not exists workflow_instances (
  tenant_id text not null references tenants(id) on delete cascade,
  instance_id text not null,
  template_id text not null,
  entity_type text not null,
  entity_id text not null,
  current_stage_index integer not null default 0,
  status text not null default 'pending'
    check (status in ('pending','in_progress','submitted','approved','returned','completed')),
  created_at timestamptz not null default now(),
  created_by text references users(id) on delete set null,
  updated_at timestamptz not null default now(),
  primary key (tenant_id, instance_id),
  foreign key (tenant_id, template_id) references workflow_templates(tenant_id, template_id) on delete restrict
);
create index if not exists idx_workflow_instances_tenant on workflow_instances(tenant_id);
create index if not exists idx_workflow_instances_entity on workflow_instances(tenant_id, entity_type, entity_id);
create index if not exists idx_workflow_instances_status on workflow_instances(tenant_id, status);

-- ============================================================
-- RLS
-- ============================================================
alter table workflow_templates enable row level security;
drop policy if exists "workflow_templates_select" on workflow_templates;
drop policy if exists "workflow_templates_insert" on workflow_templates;
drop policy if exists "workflow_templates_update" on workflow_templates;
drop policy if exists "workflow_templates_delete" on workflow_templates;
create policy "workflow_templates_select" on workflow_templates for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_templates_insert" on workflow_templates for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_templates_update" on workflow_templates for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_templates_delete" on workflow_templates for delete using (tenant_id = current_setting('app.tenant_id', true));

alter table workflow_instances enable row level security;
drop policy if exists "workflow_instances_select" on workflow_instances;
drop policy if exists "workflow_instances_insert" on workflow_instances;
drop policy if exists "workflow_instances_update" on workflow_instances;
drop policy if exists "workflow_instances_delete" on workflow_instances;
create policy "workflow_instances_select" on workflow_instances for select using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_instances_insert" on workflow_instances for insert with check (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_instances_update" on workflow_instances for update using (tenant_id = current_setting('app.tenant_id', true));
create policy "workflow_instances_delete" on workflow_instances for delete using (tenant_id = current_setting('app.tenant_id', true));

-- ============================================================
-- Seed default templates for existing tenants
-- Self-Service: 1 stage, team_pool
-- Standard Review: 2 stages (assignee -> reports_to)
-- Full Approval: 3 stages (assignee -> reports_to -> reports_to_chain)
-- ============================================================
insert into workflow_templates (tenant_id, template_id, name, description, stages_json)
select t.id, v.template_id, v.name, v.description, v.stages_json::jsonb
from tenants t
cross join (values
  ('tpl_self_service', 'Self-Service', 'Single stage; any team member can claim',
   '[{"stage_id":"s1","name":"Complete","assignee_rule":"team_pool","assignee_config":{}}]'),
  ('tpl_standard_review', 'Standard Review', 'Assignee works; manager reviews',
   '[{"stage_id":"s1","name":"Prepare","assignee_rule":"explicit","assignee_config":{}},{"stage_id":"s2","name":"Review","assignee_rule":"reports_to","assignee_config":{}}]'),
  ('tpl_full_approval', 'Full Approval', 'Analyst -> Manager -> Director/CFO',
   '[{"stage_id":"s1","name":"Prepare","assignee_rule":"explicit","assignee_config":{}},{"stage_id":"s2","name":"Manager Review","assignee_rule":"reports_to","assignee_config":{}},{"stage_id":"s3","name":"Director Approval","assignee_rule":"reports_to_chain","assignee_config":{}}]')
) as v(template_id, name, description, stages_json)
on conflict (tenant_id, template_id) do nothing;
