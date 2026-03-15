-- 0066_pim_backtest_results.sql
-- PIM-4.6: Walk-forward backtest result storage.
--
-- pim_backtest_results: one record per completed backtest run. Stores strategy
--   configuration, aggregate performance statistics (return, Sharpe, drawdown),
--   IC/ICIR signal quality metrics, benchmark comparison, and per-period data
--   as JSONB for detailed inspection.
--
-- IC (Information Coefficient): Pearson correlation between predicted CIS ranks
--   and realised period returns. IC ∈ [-1, +1].
-- ICIR (IC Information Ratio): mean(IC) / std(IC). A robust strategy is
--   typically ICIR >= 0.5.
--
-- -- down
-- drop table if exists pim_backtest_results;

create table if not exists pim_backtest_results (
    tenant_id                       text             not null,
    backtest_id                     text             not null,
    run_at                          timestamptz      not null default now(),
    strategy_label                  text             not null default 'top_n_cis',
    config_json                     jsonb            not null default '{}',  -- BacktestConfig snapshot
    -- Date range
    start_date                      date,            -- first rebalance date (derived from periods)
    end_date                        date,            -- last rebalance date (derived from periods)
    n_periods                       integer          not null default 0,
    -- Strategy aggregate statistics
    cumulative_return               double precision not null default 0.0,
    annualised_return               double precision not null default 0.0,
    volatility                      double precision not null default 0.0,  -- annualised std
    sharpe_ratio                    double precision not null default 0.0,
    max_drawdown                    double precision not null default 0.0,  -- positive fraction
    -- IC / ICIR — signal quality metrics (PIM-4.8)
    ic_mean                         double precision,  -- null if insufficient data
    ic_std                          double precision,
    icir                            double precision,  -- null if < 2 IC observations
    -- Benchmark comparison
    benchmark_label                 text             not null default 'equal_weight',
    benchmark_cumulative_return     double precision not null default 0.0,
    benchmark_annualised_return     double precision not null default 0.0,
    -- Per-period detail (JSONB array of BacktestPeriod records)
    periods_json                    jsonb            not null default '[]',
    created_at                      timestamptz      not null default now(),
    primary key (tenant_id, backtest_id)
);

create index if not exists idx_pim_backtest_results_tenant_ts
    on pim_backtest_results (tenant_id, run_at desc);

create index if not exists idx_pim_backtest_results_strategy
    on pim_backtest_results (tenant_id, strategy_label, run_at desc);

alter table pim_backtest_results enable row level security;
create policy "tenant isolation" on pim_backtest_results
    using (tenant_id = current_setting('app.tenant_id', true));
