-- ############################################################################
-- 0045_org_structures.sql (VA-P9-02: Organization Hierarchy & Consolidation)
-- ############################################################################

-- Top-level org structure (group)
CREATE TABLE IF NOT EXISTS org_structures (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    group_name text NOT NULL,
    reporting_currency text NOT NULL DEFAULT 'USD',
    status text NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'active', 'archived')),
    consolidation_method text NOT NULL DEFAULT 'full'
        CHECK (consolidation_method IN ('full', 'proportional', 'equity_method')),
    eliminate_intercompany boolean NOT NULL DEFAULT true,
    minority_interest_treatment text NOT NULL DEFAULT 'proportional'
        CHECK (minority_interest_treatment IN ('proportional', 'full_goodwill')),
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text REFERENCES users(id) ON DELETE SET NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id)
);

CREATE INDEX IF NOT EXISTS idx_org_structures_tenant_status
    ON org_structures(tenant_id, status);

-- Entities within an org structure
CREATE TABLE IF NOT EXISTS org_entities (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    entity_id text NOT NULL,
    name text NOT NULL,
    entity_type text NOT NULL
        CHECK (entity_type IN ('holding', 'operating', 'spv', 'jv', 'associate', 'branch')),
    currency text NOT NULL DEFAULT 'USD',
    country_iso text NOT NULL DEFAULT 'US',
    tax_jurisdiction text,
    tax_rate numeric CHECK (tax_rate IS NULL OR (tax_rate >= 0 AND tax_rate <= 1)),
    withholding_tax_rate numeric DEFAULT 0
        CHECK (withholding_tax_rate >= 0 AND withholding_tax_rate <= 1),
    is_root boolean NOT NULL DEFAULT false,
    baseline_id text,
    status text NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'dormant', 'disposed')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id, entity_id),
    FOREIGN KEY (tenant_id, org_id)
        REFERENCES org_structures(tenant_id, org_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_org_entities_org ON org_entities(tenant_id, org_id);
CREATE INDEX IF NOT EXISTS idx_org_entities_baseline ON org_entities(tenant_id, baseline_id)
    WHERE baseline_id IS NOT NULL;

-- Ownership links (parent-child relationships)
CREATE TABLE IF NOT EXISTS org_ownership_links (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    parent_entity_id text NOT NULL,
    child_entity_id text NOT NULL,
    ownership_pct numeric NOT NULL CHECK (ownership_pct > 0 AND ownership_pct <= 100),
    voting_pct numeric CHECK (voting_pct IS NULL OR (voting_pct >= 0 AND voting_pct <= 100)),
    consolidation_method text NOT NULL DEFAULT 'full'
        CHECK (consolidation_method IN ('full', 'proportional', 'equity_method', 'not_consolidated')),
    effective_date date,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id, parent_entity_id, child_entity_id),
    FOREIGN KEY (tenant_id, org_id, parent_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, org_id, child_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    CHECK (parent_entity_id != child_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_org_ownership_parent
    ON org_ownership_links(tenant_id, org_id, parent_entity_id);
CREATE INDEX IF NOT EXISTS idx_org_ownership_child
    ON org_ownership_links(tenant_id, org_id, child_entity_id);

-- Intercompany transaction links
CREATE TABLE IF NOT EXISTS org_intercompany_links (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    org_id text NOT NULL,
    link_id text NOT NULL,
    from_entity_id text NOT NULL,
    to_entity_id text NOT NULL,
    link_type text NOT NULL
        CHECK (link_type IN ('management_fee', 'royalty', 'loan', 'trade', 'dividend')),
    description text,
    driver_ref text,
    amount_or_rate numeric,
    frequency text DEFAULT 'monthly'
        CHECK (frequency IN ('monthly', 'quarterly', 'annual', 'one_time')),
    withholding_tax_applicable boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, org_id, link_id),
    FOREIGN KEY (tenant_id, org_id, from_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, org_id, to_entity_id)
        REFERENCES org_entities(tenant_id, org_id, entity_id) ON DELETE CASCADE,
    CHECK (from_entity_id != to_entity_id)
);

CREATE INDEX IF NOT EXISTS idx_org_intercompany_org
    ON org_intercompany_links(tenant_id, org_id);

-- Consolidated run results
CREATE TABLE IF NOT EXISTS consolidated_runs (
    tenant_id text NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    consolidated_run_id text NOT NULL,
    org_id text NOT NULL,
    status text NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
    entity_run_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    consolidation_adjustments_json jsonb DEFAULT '{}'::jsonb,
    fx_rates_used_json jsonb DEFAULT '{}'::jsonb,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now(),
    created_by text REFERENCES users(id) ON DELETE SET NULL,
    completed_at timestamptz,
    PRIMARY KEY (tenant_id, consolidated_run_id),
    FOREIGN KEY (tenant_id, org_id)
        REFERENCES org_structures(tenant_id, org_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_consolidated_runs_org
    ON consolidated_runs(tenant_id, org_id);

-- RLS for all tables
ALTER TABLE org_structures ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_ownership_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE org_intercompany_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE consolidated_runs ENABLE ROW LEVEL SECURITY;

-- org_structures policies
DROP POLICY IF EXISTS "org_structures_select" ON org_structures;
DROP POLICY IF EXISTS "org_structures_insert" ON org_structures;
DROP POLICY IF EXISTS "org_structures_update" ON org_structures;
DROP POLICY IF EXISTS "org_structures_delete" ON org_structures;
CREATE POLICY "org_structures_select" ON org_structures FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_structures_insert" ON org_structures FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_structures_update" ON org_structures FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_structures_delete" ON org_structures FOR DELETE USING (tenant_id = current_tenant_id());

-- org_entities policies
DROP POLICY IF EXISTS "org_entities_select" ON org_entities;
DROP POLICY IF EXISTS "org_entities_insert" ON org_entities;
DROP POLICY IF EXISTS "org_entities_update" ON org_entities;
DROP POLICY IF EXISTS "org_entities_delete" ON org_entities;
CREATE POLICY "org_entities_select" ON org_entities FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_entities_insert" ON org_entities FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_entities_update" ON org_entities FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_entities_delete" ON org_entities FOR DELETE USING (tenant_id = current_tenant_id());

-- org_ownership_links policies
DROP POLICY IF EXISTS "org_ownership_links_select" ON org_ownership_links;
DROP POLICY IF EXISTS "org_ownership_links_insert" ON org_ownership_links;
DROP POLICY IF EXISTS "org_ownership_links_update" ON org_ownership_links;
DROP POLICY IF EXISTS "org_ownership_links_delete" ON org_ownership_links;
CREATE POLICY "org_ownership_links_select" ON org_ownership_links FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_ownership_links_insert" ON org_ownership_links FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_ownership_links_update" ON org_ownership_links FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_ownership_links_delete" ON org_ownership_links FOR DELETE USING (tenant_id = current_tenant_id());

-- org_intercompany_links policies
DROP POLICY IF EXISTS "org_intercompany_links_select" ON org_intercompany_links;
DROP POLICY IF EXISTS "org_intercompany_links_insert" ON org_intercompany_links;
DROP POLICY IF EXISTS "org_intercompany_links_update" ON org_intercompany_links;
DROP POLICY IF EXISTS "org_intercompany_links_delete" ON org_intercompany_links;
CREATE POLICY "org_intercompany_links_select" ON org_intercompany_links FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "org_intercompany_links_insert" ON org_intercompany_links FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "org_intercompany_links_update" ON org_intercompany_links FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "org_intercompany_links_delete" ON org_intercompany_links FOR DELETE USING (tenant_id = current_tenant_id());

-- consolidated_runs policies
DROP POLICY IF EXISTS "consolidated_runs_select" ON consolidated_runs;
DROP POLICY IF EXISTS "consolidated_runs_insert" ON consolidated_runs;
DROP POLICY IF EXISTS "consolidated_runs_update" ON consolidated_runs;
DROP POLICY IF EXISTS "consolidated_runs_delete" ON consolidated_runs;
CREATE POLICY "consolidated_runs_select" ON consolidated_runs FOR SELECT USING (tenant_id = current_tenant_id());
CREATE POLICY "consolidated_runs_insert" ON consolidated_runs FOR INSERT WITH CHECK (tenant_id = current_tenant_id());
CREATE POLICY "consolidated_runs_update" ON consolidated_runs FOR UPDATE USING (tenant_id = current_tenant_id());
CREATE POLICY "consolidated_runs_delete" ON consolidated_runs FOR DELETE USING (tenant_id = current_tenant_id());
