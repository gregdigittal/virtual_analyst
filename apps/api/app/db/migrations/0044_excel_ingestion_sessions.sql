-- ############################################################################
-- 0044_excel_ingestion_sessions.sql (VA-P9-01: Excel Model Ingestion)
-- ############################################################################

CREATE TABLE IF NOT EXISTS excel_ingestion_sessions (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    ingestion_id text NOT NULL,
    filename text NOT NULL,
    file_size_bytes bigint NOT NULL,
    status text NOT NULL DEFAULT 'uploaded'
        CHECK (status IN ('uploaded', 'parsing', 'parsed', 'analyzing', 'analyzed', 'mapping', 'draft_created', 'failed')),
    sheet_count integer,
    formula_count integer,
    cross_ref_count integer,
    classification_json jsonb DEFAULT '{}'::jsonb,
    mapping_json jsonb DEFAULT '{}'::jsonb,
    unmapped_items_json jsonb DEFAULT '[]'::jsonb,
    draft_session_id text,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, ingestion_id)
);

CREATE INDEX IF NOT EXISTS idx_excel_ingestion_tenant_status
    ON excel_ingestion_sessions(tenant_id, status);

ALTER TABLE excel_ingestion_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "excel_ingestion_sessions_select" ON excel_ingestion_sessions;
DROP POLICY IF EXISTS "excel_ingestion_sessions_insert" ON excel_ingestion_sessions;
DROP POLICY IF EXISTS "excel_ingestion_sessions_update" ON excel_ingestion_sessions;
DROP POLICY IF EXISTS "excel_ingestion_sessions_delete" ON excel_ingestion_sessions;

CREATE POLICY "excel_ingestion_sessions_select" ON excel_ingestion_sessions
    FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "excel_ingestion_sessions_insert" ON excel_ingestion_sessions
    FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "excel_ingestion_sessions_update" ON excel_ingestion_sessions
    FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "excel_ingestion_sessions_delete" ON excel_ingestion_sessions
    FOR DELETE USING (tenant_id = current_tenant_id());
