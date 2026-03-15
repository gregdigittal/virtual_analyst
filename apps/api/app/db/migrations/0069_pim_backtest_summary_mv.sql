-- Migration 0069: pim_backtest_summary_mv materialised view (PIM-5.3, P-06)
-- Aggregates IC/ICIR/performance metrics per strategy per tenant.
-- Refreshed every 30 minutes by Celery task refresh_pim_backtest_summary_mv.
-- Uses CONCURRENTLY to allow reads during refresh (requires a unique index).

-- down:
-- DROP MATERIALIZED VIEW IF EXISTS pim_backtest_summary_mv;

CREATE MATERIALIZED VIEW IF NOT EXISTS pim_backtest_summary_mv AS
SELECT
    tenant_id,
    strategy_label,
    count(*)                    AS run_count,
    max(run_at)                 AS latest_run_at,
    avg(cumulative_return)      AS avg_cumulative_return,
    avg(annualised_return)      AS avg_annualised_return,
    avg(sharpe_ratio)           AS avg_sharpe_ratio,
    avg(max_drawdown)           AS avg_max_drawdown,
    avg(ic_mean)                AS avg_ic_mean,
    avg(ic_std)                 AS avg_ic_std,
    avg(icir)                   AS avg_icir,
    max(cumulative_return)      AS best_cumulative_return,
    min(cumulative_return)      AS worst_cumulative_return
FROM pim_backtest_results
GROUP BY tenant_id, strategy_label
WITH DATA;

-- refresh: every 30 minutes via Celery task refresh_pim_backtest_summary_mv

-- Unique index required for CONCURRENTLY refresh
CREATE UNIQUE INDEX IF NOT EXISTS pim_backtest_summary_mv_pk
    ON pim_backtest_summary_mv (tenant_id, strategy_label);
