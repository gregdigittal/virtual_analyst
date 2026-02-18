-- ############################################################################
-- 0047_order_by_indexes.sql — Covering indexes for list ORDER BY created_at DESC (Round 13 L-03)
-- ############################################################################

CREATE INDEX IF NOT EXISTS idx_excel_ingestion_tenant_created
    ON excel_ingestion_sessions(tenant_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_consolidated_runs_org_created
    ON consolidated_runs(tenant_id, org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_org_structures_tenant_created
    ON org_structures(tenant_id, created_at DESC);
