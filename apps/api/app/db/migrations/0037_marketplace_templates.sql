-- VA-P8-03: Template marketplace — curated catalog (read-only for tenants).

create table if not exists marketplace_templates (
  template_id text primary key,
  name text not null,
  industry text not null default '',
  template_type text not null check (template_type in ('budget', 'model')),
  description text default '',
  created_at timestamptz not null default now()
);
create index if not exists idx_marketplace_templates_industry on marketplace_templates(industry);
create index if not exists idx_marketplace_templates_type on marketplace_templates(template_type);

-- No RLS: global read-only catalog; tenant context only for "use template" audit.
-- Seed budget templates (aligned with budget_templates.json).
insert into marketplace_templates (template_id, name, industry, template_type, description)
values
  ('manufacturing', 'Manufacturing', 'manufacturing', 'budget', 'Budget template for manufacturing: headcount, capacity, capex, revenue growth'),
  ('saas', 'SaaS', 'software', 'budget', 'Budget template for SaaS: ARR/MRR, headcount, infrastructure'),
  ('services', 'Services', 'services', 'budget', 'Budget template for professional services: billable headcount, utilization'),
  ('wholesale', 'Wholesale', 'wholesale', 'budget', 'Budget template for wholesale: inventory, margin, seasonality')
on conflict (template_id) do nothing;
