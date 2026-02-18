-- ############################################################################
-- 0046_fix_llm_usage_log_rls.sql — Use current_tenant_id() for RLS (Round 12 H-03)
-- ############################################################################
-- Fix RLS policies on llm_usage_log to use standardized current_tenant_id() function
-- instead of current_setting('app.tenant_id', true).
-- Safe to run even if llm_usage_log does not exist yet (e.g. 0043 not applied): no-op in that case.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'llm_usage_log') THEN
    DROP POLICY IF EXISTS llm_usage_log_select ON llm_usage_log;
    DROP POLICY IF EXISTS llm_usage_log_insert ON llm_usage_log;
    CREATE POLICY "llm_usage_log_select" ON llm_usage_log
      FOR SELECT USING (tenant_id = current_tenant_id());
    CREATE POLICY "llm_usage_log_insert" ON llm_usage_log
      FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
  END IF;
END $$;
