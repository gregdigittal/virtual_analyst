-- 0065_pim_portfolio_runs.sql
-- PIM-4.1: Portfolio construction run storage.
--
-- pim_portfolio_runs: one record per portfolio construction run (tenant-scoped,
--   versioned by run_at timestamp). Stores constraints used, aggregate statistics,
--   and optional LLM-generated narrative (pim_portfolio_narrative).
--
-- pim_portfolio_holdings: individual holdings within a run (FK to runs).
--   Stores CIS score, assigned weight, rank, and factor scores for audit.
--
-- -- down
-- drop table if exists pim_portfolio_holdings;
-- drop table if exists pim_portfolio_runs;

-- Portfolio construction runs
create table if not exists pim_portfolio_runs (
    tenant_id                   text             not null,
    run_id                      text             not null,
    run_at                      timestamptz      not null default now(),
    n_candidates                integer          not null default 0,
    n_holdings                  integer          not null default 0,
    avg_cis_score               double precision not null default 0.0,
    total_cis_score             double precision not null default 0.0,
    regime_at_run               text,            -- expansion | contraction | transition | null
    constraints_json            jsonb            not null default '{}',  -- PositionConstraints snapshot
    narrative                   text,            -- LLM portfolio overview (pim_portfolio_narrative)
    narrative_top_picks         text,            -- LLM rationale for top picks
    narrative_risk_note         text,            -- LLM risk note
    narrative_regime_context    text,            -- LLM regime context
    created_at                  timestamptz      not null default now(),
    updated_at                  timestamptz      not null default now(),
    primary key (tenant_id, run_id)
);

create index if not exists idx_pim_portfolio_runs_tenant_ts
    on pim_portfolio_runs (tenant_id, run_at desc);

alter table pim_portfolio_runs enable row level security;
create policy "tenant isolation" on pim_portfolio_runs
    using (tenant_id = current_setting('app.tenant_id', true));

-- Portfolio holdings: individual positions within a run
create table if not exists pim_portfolio_holdings (
    tenant_id                   text             not null,
    run_id                      text             not null,
    company_id                  text             not null,
    rank                        integer          not null check (rank >= 1),
    ticker                      text,
    name                        text,
    cis_score                   double precision not null check (cis_score >= 0.0 and cis_score <= 100.0),
    weight                      double precision not null check (weight >= 0.0 and weight <= 1.0),
    sector                      text,
    -- Factor scores (null = not available at run time)
    fundamental_quality         double precision,
    fundamental_momentum        double precision,
    idiosyncratic_sentiment     double precision,
    sentiment_momentum          double precision,
    sector_positioning          double precision,
    created_at                  timestamptz      not null default now(),
    primary key (tenant_id, run_id, company_id),
    foreign key (tenant_id, run_id)
        references pim_portfolio_runs (tenant_id, run_id) on delete cascade
);

create index if not exists idx_pim_portfolio_holdings_run
    on pim_portfolio_holdings (tenant_id, run_id, rank);

alter table pim_portfolio_holdings enable row level security;
create policy "tenant isolation" on pim_portfolio_holdings
    using (tenant_id = current_setting('app.tenant_id', true));
