-- Migration 0068: pim_transaction_costs table (PIM-5.5, SR-7)
-- Stores per-rebalance transaction cost assumptions (estimated and actual)
-- associated with a backtest run, enabling net-of-cost return reporting.
-- SR-7: Backtest results must report transaction cost assumptions.

-- down:
-- DROP TABLE IF EXISTS pim_transaction_costs;

CREATE TABLE IF NOT EXISTS pim_transaction_costs (
    cost_id      TEXT        NOT NULL DEFAULT 'tc_' || gen_random_uuid()::TEXT,
    tenant_id    UUID        NOT NULL,
    backtest_id  TEXT        NOT NULL,
    cost_type    TEXT        NOT NULL CHECK (cost_type IN ('commission', 'spread', 'slippage')),
    estimated_bps NUMERIC(10, 4) NOT NULL CHECK (estimated_bps >= 0),
    actual_bps   NUMERIC(10, 4)  CHECK (actual_bps >= 0),
    n_rebalances INTEGER     NOT NULL DEFAULT 0 CHECK (n_rebalances >= 0),
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id, cost_id),
    FOREIGN KEY (tenant_id, backtest_id)
        REFERENCES pim_backtest_results (tenant_id, backtest_id)
        ON DELETE CASCADE
);

-- RLS: tenants can only access their own transaction cost records
ALTER TABLE pim_transaction_costs ENABLE ROW LEVEL SECURITY;

CREATE POLICY pim_transaction_costs_tenant_isolation
    ON pim_transaction_costs
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

CREATE INDEX IF NOT EXISTS pim_transaction_costs_backtest_idx
    ON pim_transaction_costs (tenant_id, backtest_id);
