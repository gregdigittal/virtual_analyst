-- Migration 0049: Add is_revenue flag to budget_line_items
-- Replaces heuristic-based revenue detection with an explicit flag per line item.

ALTER TABLE budget_line_items
  ADD COLUMN IF NOT EXISTS is_revenue BOOLEAN NOT NULL DEFAULT FALSE;
