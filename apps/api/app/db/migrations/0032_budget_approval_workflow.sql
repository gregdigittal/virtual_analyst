-- VA-P7-06: Budget approval workflow integration
-- Add workflow_instance_id to budgets; seed Budget Approval template.

alter table budgets add column if not exists workflow_instance_id text;

comment on column budgets.workflow_instance_id is 'Set when budget is submitted for approval; links to workflow_instances(instance_id) for entity_type=budget.';

-- Seed Budget Approval template: department_head_review -> finance_review -> cfo_approval -> board_presentation
insert into workflow_templates (tenant_id, template_id, name, description, stages_json)
select t.id, v.template_id, v.name, v.description, v.stages_json::jsonb
from tenants t
cross join (values
  ('tpl_budget_approval', 'Budget Approval', 'Department head -> Finance -> CFO -> Board presentation',
   '[{"stage_id":"s1","name":"Department head review","assignee_rule":"reports_to","assignee_config":{}},{"stage_id":"s2","name":"Finance review","assignee_rule":"reports_to","assignee_config":{}},{"stage_id":"s3","name":"CFO approval","assignee_rule":"reports_to_chain","assignee_config":{}},{"stage_id":"s4","name":"Board presentation","assignee_rule":"team_pool","assignee_config":{}}]')
) as v(template_id, name, description, stages_json)
on conflict (tenant_id, template_id) do nothing;
