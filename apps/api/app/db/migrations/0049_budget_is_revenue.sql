-- Migration 0049: Add is_revenue flag to budget_line_items
-- Replaces heuristic-based revenue detection with an explicit flag per line item.

ALTER TABLE budget_line_items
  ADD COLUMN IF NOT EXISTS is_revenue BOOLEAN NOT NULL DEFAULT FALSE;

-- Backfill existing line items using the same name heuristic that was previously
-- applied at query time, so the explicit flag is correct from the start.
UPDATE budget_line_items
SET is_revenue = TRUE
WHERE is_revenue = FALSE
  AND (LOWER(account_ref) LIKE 'revenue%'
    OR LOWER(account_ref) LIKE 'income%'
    OR LOWER(account_ref) LIKE 'subscription%'
    OR LOWER(account_ref) LIKE 'fee%'
    OR LOWER(account_ref) LIKE 'gain%');
