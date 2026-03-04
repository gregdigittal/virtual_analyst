-- 0058_finservices_fintech_templates.sql
-- Seed Financial Services and Fintech budget templates into the marketplace catalog.
-- Matches the templates added to budget_templates.json and default_catalog.json.

INSERT INTO marketplace_templates (template_id, name, industry, template_type, description)
VALUES
  ('financial_services',  'Financial Services',  'financial_services',  'budget', 'Fee-based revenue, AUM management, net interest income, credit provisioning, and compensation-to-revenue budgeting.'),
  ('fintech',             'Fintech',             'fintech',             'budget', 'Multi-stream fintech: transaction revenue, device rental, token sales, customer acquisition, and fraud/risk costs.')
ON CONFLICT (template_id) DO NOTHING;
