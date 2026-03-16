-- 0071: PIM peer benchmark universe for percentile ranking (PIM-7.1)
--
-- Stores external fund benchmark data used for peer comparison.
-- Fund managers compare their DPI/TVPI/IRR against peers in the same vintage year and strategy.

CREATE TABLE IF NOT EXISTS pim_peer_benchmarks (
    benchmark_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,

    -- Fund identification
    vintage_year    INTEGER NOT NULL CHECK (vintage_year >= 1980 AND vintage_year <= 2100),
    strategy        TEXT NOT NULL DEFAULT 'buyout',  -- buyout | venture | growth | real_assets | credit
    geography       TEXT NOT NULL DEFAULT 'global',  -- north_america | europe | asia_pacific | global

    -- Benchmark percentiles (sourced from Cambridge Associates / Preqin / PitchBook)
    dpi_p25         NUMERIC(10, 6),
    dpi_p50         NUMERIC(10, 6),
    dpi_p75         NUMERIC(10, 6),

    tvpi_p25        NUMERIC(10, 6),
    tvpi_p50        NUMERIC(10, 6),
    tvpi_p75        NUMERIC(10, 6),

    irr_p25         NUMERIC(10, 6),  -- annual rate, e.g. 0.12 = 12%
    irr_p50         NUMERIC(10, 6),
    irr_p75         NUMERIC(10, 6),

    -- Sample info
    fund_count      INTEGER,          -- number of funds in the benchmark cohort
    data_source     TEXT,             -- e.g. 'Cambridge Associates', 'Preqin'
    as_of_date      DATE,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Composite index: most queries filter by (tenant_id, vintage_year, strategy)
CREATE INDEX IF NOT EXISTS idx_pim_peer_benchmarks_lookup
    ON pim_peer_benchmarks (tenant_id, vintage_year, strategy, geography);

-- RLS
ALTER TABLE pim_peer_benchmarks ENABLE ROW LEVEL SECURITY;

CREATE POLICY pim_peer_benchmarks_tenant
    ON pim_peer_benchmarks
    USING (tenant_id::text = current_setting('app.tenant_id', true));

-- Updated-at trigger
CREATE OR REPLACE FUNCTION pim_peer_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE TRIGGER pim_peer_benchmarks_updated_at
    BEFORE UPDATE ON pim_peer_benchmarks
    FOR EACH ROW EXECUTE FUNCTION pim_peer_set_updated_at();

-- down:
-- DROP TABLE IF EXISTS pim_peer_benchmarks;
-- DROP FUNCTION IF EXISTS pim_peer_set_updated_at();
