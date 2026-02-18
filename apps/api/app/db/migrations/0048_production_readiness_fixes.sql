-- 0048: Production readiness fixes
-- Fixes: function search_path, duplicate RLS policies, duplicate indexes, unindexed FKs

-- A-06: Fix function search_path security (skip gracefully if function doesn't exist)
DO $$ BEGIN
  ALTER FUNCTION current_tenant_id() SET search_path = public;
EXCEPTION WHEN undefined_function THEN NULL;
END $$;

DO $$ BEGIN
  ALTER FUNCTION generate_id(text) SET search_path = public;
EXCEPTION WHEN undefined_function THEN NULL;
END $$;

DO $$ BEGIN
  ALTER FUNCTION update_workflow_instances_updated_at() SET search_path = public;
EXCEPTION WHEN undefined_function THEN NULL;
END $$;

DO $$ BEGIN
  ALTER FUNCTION lookup_saml_tenant_by_entity_id(text) SET search_path = public;
EXCEPTION WHEN undefined_function THEN NULL;
END $$;

-- A-07: Remove duplicate RLS policies on canonical_sync_snapshots
DROP POLICY IF EXISTS canonical_sync_snapshots_insert ON canonical_sync_snapshots;
DROP POLICY IF EXISTS canonical_sync_snapshots_select ON canonical_sync_snapshots;

-- B-08: Remove duplicate indexes on excel_sync_events
DROP INDEX IF EXISTS idx_sync_events_connection;
DROP INDEX IF EXISTS idx_sync_events_timestamp;

-- B-09: Add indexes for unindexed foreign keys
-- Only for columns/tables that exist in the schema.
-- Tables with composite PKs (runs, draft_sessions, budget_line_items) already have composite indexes.

-- notifications.user_id
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id)
    WHERE user_id IS NOT NULL;

-- audit_log.tenant_id (already has idx_audit_tenant_time but adding plain tenant_id)
-- Skipped: idx_audit_tenant_time already covers tenant_id lookups

-- workflow_instances.template_id
DO $$ BEGIN
  CREATE INDEX IF NOT EXISTS idx_workflow_instances_template ON workflow_instances(template_id);
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

-- task_assignments.workflow_instance_id
CREATE INDEX IF NOT EXISTS idx_task_assignments_wf_instance ON task_assignments(workflow_instance_id)
    WHERE workflow_instance_id IS NOT NULL;

-- reviews.assignment_id (already indexed via idx_reviews_assignment — skip)

-- board_packs sections: no separate board_pack_sections table exists — board_packs has section_order jsonb

-- pack_generation_history.schedule_id (already indexed via idx_pack_history_schedule — skip)

-- canonical_sync_snapshots.connection_id
DO $$ BEGIN
  CREATE INDEX IF NOT EXISTS idx_canonical_snapshots_conn ON canonical_sync_snapshots(connection_id);
EXCEPTION WHEN undefined_column THEN NULL;
END $$;

-- llm_usage_log.tenant_id (already indexed via idx_llm_usage_log_tenant_period — skip)

-- budget_actuals: composite PK covers (tenant_id, budget_id, period_ordinal, account_ref, department_ref)
-- No standalone line_item_id column exists
