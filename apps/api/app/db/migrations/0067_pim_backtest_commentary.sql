-- Migration 0067: Add LLM commentary columns to pim_backtest_results (PIM-5.2)
-- Adds optional commentary and commentary_risks text fields.
-- Populated on-demand by the GET /pim/backtest/{backtest_id}/commentary endpoint.
-- ON CONFLICT DO NOTHING on persist_backtest means existing rows can receive
-- commentary via UPDATE without re-running the backtest.

-- down: ALTER TABLE pim_backtest_results DROP COLUMN IF EXISTS commentary, DROP COLUMN IF EXISTS commentary_risks;

ALTER TABLE pim_backtest_results
    ADD COLUMN IF NOT EXISTS commentary       TEXT,
    ADD COLUMN IF NOT EXISTS commentary_risks TEXT;
