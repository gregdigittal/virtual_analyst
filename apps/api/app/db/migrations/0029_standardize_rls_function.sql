-- R8-04: Standardize all RLS policies to use current_tenant_id() function for consistency.

-- notifications
drop policy if exists "notifications_select" on notifications;
create policy "notifications_select" on notifications for select
  using (tenant_id = current_tenant_id());
drop policy if exists "notifications_insert" on notifications;
create policy "notifications_insert" on notifications for insert
  with check (tenant_id = current_tenant_id());
drop policy if exists "notifications_update" on notifications;
create policy "notifications_update" on notifications for update
  using (tenant_id = current_tenant_id());
drop policy if exists "notifications_delete" on notifications;
create policy "notifications_delete" on notifications for delete
  using (tenant_id = current_tenant_id());

-- scenarios
drop policy if exists "scenarios_select" on scenarios;
create policy "scenarios_select" on scenarios for select using (tenant_id = current_tenant_id());
drop policy if exists "scenarios_insert" on scenarios;
create policy "scenarios_insert" on scenarios for insert with check (tenant_id = current_tenant_id());
drop policy if exists "scenarios_update" on scenarios;
create policy "scenarios_update" on scenarios for update using (tenant_id = current_tenant_id());
drop policy if exists "scenarios_delete" on scenarios;
create policy "scenarios_delete" on scenarios for delete using (tenant_id = current_tenant_id());

-- integration_connections
drop policy if exists "integration_connections_select" on integration_connections;
create policy "integration_connections_select" on integration_connections for select using (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_insert" on integration_connections;
create policy "integration_connections_insert" on integration_connections for insert with check (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_update" on integration_connections;
create policy "integration_connections_update" on integration_connections for update using (tenant_id = current_tenant_id());
drop policy if exists "integration_connections_delete" on integration_connections;
create policy "integration_connections_delete" on integration_connections for delete using (tenant_id = current_tenant_id());

-- integration_sync_runs
drop policy if exists "integration_sync_runs_select" on integration_sync_runs;
create policy "integration_sync_runs_select" on integration_sync_runs for select using (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_insert" on integration_sync_runs;
create policy "integration_sync_runs_insert" on integration_sync_runs for insert with check (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_update" on integration_sync_runs;
create policy "integration_sync_runs_update" on integration_sync_runs for update using (tenant_id = current_tenant_id());
drop policy if exists "integration_sync_runs_delete" on integration_sync_runs;
create policy "integration_sync_runs_delete" on integration_sync_runs for delete using (tenant_id = current_tenant_id());

-- canonical_sync_snapshots
drop policy if exists "canonical_snapshots_select" on canonical_sync_snapshots;
create policy "canonical_snapshots_select" on canonical_sync_snapshots for select using (tenant_id = current_tenant_id());
drop policy if exists "canonical_snapshots_insert" on canonical_sync_snapshots;
create policy "canonical_snapshots_insert" on canonical_sync_snapshots for insert with check (tenant_id = current_tenant_id());
drop policy if exists "canonical_snapshots_delete" on canonical_sync_snapshots;
create policy "canonical_snapshots_delete" on canonical_sync_snapshots for delete using (tenant_id = current_tenant_id());

-- billing_subscriptions
drop policy if exists "billing_subscriptions_select" on billing_subscriptions;
create policy "billing_subscriptions_select" on billing_subscriptions for select using (tenant_id = current_tenant_id());
drop policy if exists "billing_subscriptions_insert" on billing_subscriptions;
create policy "billing_subscriptions_insert" on billing_subscriptions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "billing_subscriptions_update" on billing_subscriptions;
create policy "billing_subscriptions_update" on billing_subscriptions for update using (tenant_id = current_tenant_id());

-- usage_meters
drop policy if exists "usage_meters_select" on usage_meters;
create policy "usage_meters_select" on usage_meters for select using (tenant_id = current_tenant_id());
drop policy if exists "usage_meters_insert" on usage_meters;
create policy "usage_meters_insert" on usage_meters for insert with check (tenant_id = current_tenant_id());
drop policy if exists "usage_meters_update" on usage_meters;
create policy "usage_meters_update" on usage_meters for update using (tenant_id = current_tenant_id());

-- llm_call_logs
drop policy if exists "llm_call_logs_select" on llm_call_logs;
create policy "llm_call_logs_select" on llm_call_logs for select using (tenant_id = current_tenant_id());
drop policy if exists "llm_call_logs_insert" on llm_call_logs;
create policy "llm_call_logs_insert" on llm_call_logs for insert with check (tenant_id = current_tenant_id());

-- llm_routing_policies (special: tenant_id can be null for defaults)
drop policy if exists "llm_routing_policies_select" on llm_routing_policies;
create policy "llm_routing_policies_select" on llm_routing_policies for select using (
  tenant_id = current_tenant_id() or tenant_id is null
);

-- audit_log (note: no UPDATE policy per R8-03)
drop policy if exists "audit_log_insert" on audit_log;
create policy "audit_log_insert" on audit_log for insert with check (tenant_id = current_tenant_id());
drop policy if exists "audit_log_select" on audit_log;
create policy "audit_log_select" on audit_log for select using (tenant_id = current_tenant_id());

-- covenant_definitions
drop policy if exists "covenant_definitions_select" on covenant_definitions;
create policy "covenant_definitions_select" on covenant_definitions for select using (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_insert" on covenant_definitions;
create policy "covenant_definitions_insert" on covenant_definitions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_update" on covenant_definitions;
create policy "covenant_definitions_update" on covenant_definitions for update using (tenant_id = current_tenant_id());
drop policy if exists "covenant_definitions_delete" on covenant_definitions;
create policy "covenant_definitions_delete" on covenant_definitions for delete using (tenant_id = current_tenant_id());

-- excel_connections
drop policy if exists "excel_connections_select" on excel_connections;
create policy "excel_connections_select" on excel_connections for select using (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_insert" on excel_connections;
create policy "excel_connections_insert" on excel_connections for insert with check (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_update" on excel_connections;
create policy "excel_connections_update" on excel_connections for update using (tenant_id = current_tenant_id());
drop policy if exists "excel_connections_delete" on excel_connections;
create policy "excel_connections_delete" on excel_connections for delete using (tenant_id = current_tenant_id());

-- excel_sync_events
drop policy if exists "excel_sync_events_select" on excel_sync_events;
create policy "excel_sync_events_select" on excel_sync_events for select using (tenant_id = current_tenant_id());
drop policy if exists "excel_sync_events_insert" on excel_sync_events;
create policy "excel_sync_events_insert" on excel_sync_events for insert with check (tenant_id = current_tenant_id());

-- memo_packs
drop policy if exists "memo_packs_select" on memo_packs;
create policy "memo_packs_select" on memo_packs for select using (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_insert" on memo_packs;
create policy "memo_packs_insert" on memo_packs for insert with check (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_update" on memo_packs;
create policy "memo_packs_update" on memo_packs for update using (tenant_id = current_tenant_id());
drop policy if exists "memo_packs_delete" on memo_packs;
create policy "memo_packs_delete" on memo_packs for delete using (tenant_id = current_tenant_id());

-- document_attachments
drop policy if exists "document_attachments_select" on document_attachments;
create policy "document_attachments_select" on document_attachments for select using (tenant_id = current_tenant_id());
drop policy if exists "document_attachments_insert" on document_attachments;
create policy "document_attachments_insert" on document_attachments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "document_attachments_delete" on document_attachments;
create policy "document_attachments_delete" on document_attachments for delete using (tenant_id = current_tenant_id());

-- comments
drop policy if exists "comments_select" on comments;
create policy "comments_select" on comments for select using (tenant_id = current_tenant_id());
drop policy if exists "comments_insert" on comments;
create policy "comments_insert" on comments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "comments_delete" on comments;
create policy "comments_delete" on comments for delete using (tenant_id = current_tenant_id());

-- job_functions
drop policy if exists "job_functions_select" on job_functions;
create policy "job_functions_select" on job_functions for select using (tenant_id = current_tenant_id());
drop policy if exists "job_functions_insert" on job_functions;
create policy "job_functions_insert" on job_functions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "job_functions_update" on job_functions;
create policy "job_functions_update" on job_functions for update using (tenant_id = current_tenant_id());
drop policy if exists "job_functions_delete" on job_functions;
create policy "job_functions_delete" on job_functions for delete using (tenant_id = current_tenant_id());

-- teams
drop policy if exists "teams_select" on teams;
create policy "teams_select" on teams for select using (tenant_id = current_tenant_id());
drop policy if exists "teams_insert" on teams;
create policy "teams_insert" on teams for insert with check (tenant_id = current_tenant_id());
drop policy if exists "teams_update" on teams;
create policy "teams_update" on teams for update using (tenant_id = current_tenant_id());
drop policy if exists "teams_delete" on teams;
create policy "teams_delete" on teams for delete using (tenant_id = current_tenant_id());

-- team_members
drop policy if exists "team_members_select" on team_members;
create policy "team_members_select" on team_members for select using (tenant_id = current_tenant_id());
drop policy if exists "team_members_insert" on team_members;
create policy "team_members_insert" on team_members for insert with check (tenant_id = current_tenant_id());
drop policy if exists "team_members_update" on team_members;
create policy "team_members_update" on team_members for update using (tenant_id = current_tenant_id());
drop policy if exists "team_members_delete" on team_members;
create policy "team_members_delete" on team_members for delete using (tenant_id = current_tenant_id());

-- workflow_templates
drop policy if exists "workflow_templates_select" on workflow_templates;
create policy "workflow_templates_select" on workflow_templates for select using (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_insert" on workflow_templates;
create policy "workflow_templates_insert" on workflow_templates for insert with check (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_update" on workflow_templates;
create policy "workflow_templates_update" on workflow_templates for update using (tenant_id = current_tenant_id());
drop policy if exists "workflow_templates_delete" on workflow_templates;
create policy "workflow_templates_delete" on workflow_templates for delete using (tenant_id = current_tenant_id());

-- workflow_instances
drop policy if exists "workflow_instances_select" on workflow_instances;
create policy "workflow_instances_select" on workflow_instances for select using (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_insert" on workflow_instances;
create policy "workflow_instances_insert" on workflow_instances for insert with check (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_update" on workflow_instances;
create policy "workflow_instances_update" on workflow_instances for update using (tenant_id = current_tenant_id());
drop policy if exists "workflow_instances_delete" on workflow_instances;
create policy "workflow_instances_delete" on workflow_instances for delete using (tenant_id = current_tenant_id());

-- task_assignments
drop policy if exists "task_assignments_select" on task_assignments;
create policy "task_assignments_select" on task_assignments for select using (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_insert" on task_assignments;
create policy "task_assignments_insert" on task_assignments for insert with check (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_update" on task_assignments;
create policy "task_assignments_update" on task_assignments for update using (tenant_id = current_tenant_id());
drop policy if exists "task_assignments_delete" on task_assignments;
create policy "task_assignments_delete" on task_assignments for delete using (tenant_id = current_tenant_id());

-- reviews
drop policy if exists "reviews_select" on reviews;
create policy "reviews_select" on reviews for select using (tenant_id = current_tenant_id());
drop policy if exists "reviews_insert" on reviews;
create policy "reviews_insert" on reviews for insert with check (tenant_id = current_tenant_id());
drop policy if exists "reviews_update" on reviews;
create policy "reviews_update" on reviews for update using (tenant_id = current_tenant_id());
drop policy if exists "reviews_delete" on reviews;
create policy "reviews_delete" on reviews for delete using (tenant_id = current_tenant_id());

-- change_summaries
drop policy if exists "change_summaries_select" on change_summaries;
create policy "change_summaries_select" on change_summaries for select using (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_insert" on change_summaries;
create policy "change_summaries_insert" on change_summaries for insert with check (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_update" on change_summaries;
create policy "change_summaries_update" on change_summaries for update using (tenant_id = current_tenant_id());
drop policy if exists "change_summaries_delete" on change_summaries;
create policy "change_summaries_delete" on change_summaries for delete using (tenant_id = current_tenant_id());

-- budgets
drop policy if exists "budgets_select" on budgets;
create policy "budgets_select" on budgets for select using (tenant_id = current_tenant_id());
drop policy if exists "budgets_insert" on budgets;
create policy "budgets_insert" on budgets for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budgets_update" on budgets;
create policy "budgets_update" on budgets for update using (tenant_id = current_tenant_id());
drop policy if exists "budgets_delete" on budgets;
create policy "budgets_delete" on budgets for delete using (tenant_id = current_tenant_id());

-- budget_versions
drop policy if exists "budget_versions_select" on budget_versions;
create policy "budget_versions_select" on budget_versions for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_insert" on budget_versions;
create policy "budget_versions_insert" on budget_versions for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_update" on budget_versions;
create policy "budget_versions_update" on budget_versions for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_versions_delete" on budget_versions;
create policy "budget_versions_delete" on budget_versions for delete using (tenant_id = current_tenant_id());

-- budget_periods
drop policy if exists "budget_periods_select" on budget_periods;
create policy "budget_periods_select" on budget_periods for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_insert" on budget_periods;
create policy "budget_periods_insert" on budget_periods for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_update" on budget_periods;
create policy "budget_periods_update" on budget_periods for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_periods_delete" on budget_periods;
create policy "budget_periods_delete" on budget_periods for delete using (tenant_id = current_tenant_id());

-- budget_line_items
drop policy if exists "budget_line_items_select" on budget_line_items;
create policy "budget_line_items_select" on budget_line_items for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_insert" on budget_line_items;
create policy "budget_line_items_insert" on budget_line_items for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_update" on budget_line_items;
create policy "budget_line_items_update" on budget_line_items for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_items_delete" on budget_line_items;
create policy "budget_line_items_delete" on budget_line_items for delete using (tenant_id = current_tenant_id());

-- budget_line_item_amounts
drop policy if exists "budget_line_item_amounts_select" on budget_line_item_amounts;
create policy "budget_line_item_amounts_select" on budget_line_item_amounts for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_insert" on budget_line_item_amounts;
create policy "budget_line_item_amounts_insert" on budget_line_item_amounts for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_update" on budget_line_item_amounts;
create policy "budget_line_item_amounts_update" on budget_line_item_amounts for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_line_item_amounts_delete" on budget_line_item_amounts;
create policy "budget_line_item_amounts_delete" on budget_line_item_amounts for delete using (tenant_id = current_tenant_id());

-- budget_department_allocations
drop policy if exists "budget_department_allocations_select" on budget_department_allocations;
create policy "budget_department_allocations_select" on budget_department_allocations for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_insert" on budget_department_allocations;
create policy "budget_department_allocations_insert" on budget_department_allocations for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_update" on budget_department_allocations;
create policy "budget_department_allocations_update" on budget_department_allocations for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_department_allocations_delete" on budget_department_allocations;
create policy "budget_department_allocations_delete" on budget_department_allocations for delete using (tenant_id = current_tenant_id());

-- budget_actuals
drop policy if exists "budget_actuals_select" on budget_actuals;
create policy "budget_actuals_select" on budget_actuals for select using (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_insert" on budget_actuals;
create policy "budget_actuals_insert" on budget_actuals for insert with check (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_update" on budget_actuals;
create policy "budget_actuals_update" on budget_actuals for update using (tenant_id = current_tenant_id());
drop policy if exists "budget_actuals_delete" on budget_actuals;
create policy "budget_actuals_delete" on budget_actuals for delete using (tenant_id = current_tenant_id());
