-- 0063_pim_economic_snapshots.sql
-- PIM-2.1: Economic context snapshots (FRED indicator pulls + regime classification).
--
-- FR-2.1: Pull ≥ 5 FRED indicators (GDP, CPI, unemployment, yield curve, ISM PMI)
-- FR-2.2: Classify economic regime: expansion / contraction / transition
-- FR-2.4: Store snapshots with version history

create table if not exists pim_economic_snapshots (
  tenant_id           text not null,
  snapshot_id         text not null,
  fetched_at          timestamptz not null,
  -- FRED indicators (nullable: indicator may be unavailable at fetch time)
  gdp_growth_pct      double precision,       -- real GDP quarterly growth YoY (A191RL1Q225SBEA)
  cpi_yoy_pct         double precision,       -- CPI all-items YoY % (computed from CPIAUCSL)
  unemployment_rate   double precision,       -- civilian unemployment rate % (UNRATE)
  yield_spread_10y2y  double precision,       -- 10Y-2Y Treasury spread in % (T10Y2Y)
  ism_pmi             double precision,       -- ISM Manufacturing PMI (ISM/MAN_PMI or INDPRO proxy)
  -- Regime classification (statistical, not LLM)
  regime              text not null
    check (regime in ('expansion', 'contraction', 'transition')),
  regime_confidence   double precision not null
    check (regime_confidence >= 0.0 and regime_confidence <= 1.0),
  indicators_agreeing integer not null default 0,  -- count of indicators consistent with classified regime
  indicators_total    integer not null default 0,  -- total indicators with data at fetch time
  -- Raw FRED response payload for audit and replay
  indicators_raw      jsonb not null default '{}'::jsonb,
  created_at          timestamptz not null default now(),
  primary key (tenant_id, snapshot_id)
);

-- Most recent snapshot lookup
create index if not exists idx_pim_econ_tenant_fetched
  on pim_economic_snapshots (tenant_id, fetched_at desc);

-- Regime trend queries
create index if not exists idx_pim_econ_tenant_regime
  on pim_economic_snapshots (tenant_id, regime, fetched_at desc);

-- RLS: each tenant sees only their own economic snapshots
alter table pim_economic_snapshots enable row level security;

create policy pim_economic_snapshots_tenant_isolation on pim_economic_snapshots
  using (tenant_id = current_setting('app.tenant_id', true))
  with check (tenant_id = current_setting('app.tenant_id', true));

-- down:
-- drop table if exists pim_economic_snapshots;
