-- 0070_pim_pe_assessments.sql
-- PIM-6.1: Private equity fund assessment records.
--
-- Stores PE fund metadata, cash-flow schedules, and cached performance metrics
-- (DPI, TVPI, IRR, MOIC) computed by the `services/pim/pe_benchmarks.py` engine.
--
-- FR-7.1: Fund name, vintage year, commitment, drawdowns, distributions.
-- FR-7.2: DPI, TVPI, IRR stored as computed columns (refreshed on engine run).
-- FR-7.3: J-curve data stored as JSONB for charting without recomputation.
--
-- -- down
-- drop table if exists pim_pe_assessments;

create table if not exists pim_pe_assessments (
    assessment_id   text        not null default gen_random_uuid()::text,
    tenant_id       text        not null,

    -- Fund identity
    fund_name       text        not null,
    vintage_year    integer     not null check (vintage_year >= 1980 and vintage_year <= 2100),
    currency        text        not null default 'USD',
    commitment_usd  double precision not null check (commitment_usd > 0),

    -- Cash flows: array of objects [{date, amount_usd, cf_type}]
    -- cf_type IN ('drawdown', 'distribution', 'recallable_distribution')
    -- amount_usd: positive for drawdowns (capital called), positive for distributions (capital returned)
    -- Sign convention enforced at application layer, not DB (avoids complexity with JSONB checks)
    cash_flows      jsonb       not null default '[]'::jsonb,

    -- Current NAV (user-supplied residual value for TVPI calculation)
    nav_usd         double precision,
    nav_date        date,

    -- Cached computed metrics — null until engine run
    paid_in_capital double precision,   -- total drawdowns (positive)
    distributed     double precision,   -- total distributions (positive)
    dpi             double precision,   -- Distributed to Paid-In = distributed / paid_in
    tvpi            double precision,   -- Total Value to Paid-In = (distributed + nav) / paid_in
    moic            double precision,   -- Multiple on Invested Capital (alias for TVPI at fund level)
    irr             double precision,   -- Internal Rate of Return (Newton-Raphson, annualised)
    irr_computed_at timestamptz,        -- when IRR was last computed (stale if cash_flows updated after)

    -- J-curve representation: [{period_months, cumulative_return}] for charting
    j_curve_json    jsonb,

    -- Audit
    notes           text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now(),

    primary key (tenant_id, assessment_id)
);

-- Index for tenant listing sorted by vintage year
create index if not exists idx_pim_pe_assessments_tenant_vintage
    on pim_pe_assessments (tenant_id, vintage_year desc, fund_name);

-- Index for fund name search within tenant
create index if not exists idx_pim_pe_assessments_tenant_name
    on pim_pe_assessments (tenant_id, lower(fund_name));

-- Row-level security
alter table pim_pe_assessments enable row level security;
create policy "tenant isolation" on pim_pe_assessments
    using (tenant_id = current_setting('app.tenant_id', true));

-- Trigger: auto-update updated_at
create or replace function pim_pe_set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger pim_pe_assessments_updated_at
    before update on pim_pe_assessments
    for each row execute function pim_pe_set_updated_at();
