-- 0050_expanded_marketplace_templates.sql
-- Seed 10 additional industry templates into the marketplace catalog.
-- Aligns with the expanded budget_templates.json.

INSERT INTO marketplace_templates (template_id, name, industry, template_type, description)
VALUES
  ('consulting',            'Consulting Services',              'consulting',    'budget', 'Utilization-based consulting: bill rates, project mix, and overhead management.'),
  ('legal',                 'Legal Practice',                   'legal',         'budget', 'Law firm budgeting: billable hours, practice areas, associate/partner ratios.'),
  ('software_dev',          'Software Development',             'software',      'budget', 'Software dev shop: sprint capacity, project revenue, and technology costs.'),
  ('staffing',              'Staffing Agency',                  'staffing',      'budget', 'Staffing agency: placement fees, fill rates, and contractor management.'),
  ('wholesale_import',      'Wholesale (Import)',               'distribution',  'budget', 'Import-focused wholesale: FX exposure, shipping, tariffs, and lead times.'),
  ('retail',                'Retail',                           'retail',        'budget', 'Retail operations: store-level P&L, foot traffic, inventory, seasonality.'),
  ('construction_gc',       'Construction (General Contractor)','construction',  'budget', 'General contractor budgeting: project pipeline, completion %, subcontractors.'),
  ('construction_specialty','Construction (Specialty Trade)',    'construction',  'budget', 'Specialty trade: crew capacity, materials pricing, and project backlog.'),
  ('healthcare_practice',   'Medical Practice',                 'healthcare',    'budget', 'Medical practice: patient volume, reimbursement rates, and payer mix.'),
  ('healthcare_services',   'Healthcare Services',              'healthcare',    'budget', 'Healthcare facility: staffing ratios, regulatory compliance, and capital planning.')
ON CONFLICT (template_id) DO NOTHING;
