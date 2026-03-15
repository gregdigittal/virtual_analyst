-- 0062_pim_billing_feature.sql
-- Add 'pim' feature flag to billing plans for PIM access gate.
-- Enterprise plan gets pim: true; starter and professional remain false.

UPDATE billing_plans
SET features_json = features_json || '{"pim": true}'::jsonb
WHERE plan_id = 'plan_enterprise';

-- down:
-- UPDATE billing_plans SET features_json = features_json - 'pim' WHERE plan_id = 'plan_enterprise';
