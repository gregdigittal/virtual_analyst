-- R11-10: Security-definer function for SAML ACS to resolve tenant_id by entity_id
-- without requiring app.tenant_id (RLS would otherwise block the lookup).

create or replace function lookup_saml_tenant_by_entity_id(p_entity_id text)
returns text
language sql security definer stable as $$
  select tenant_id from tenant_saml_config where entity_id = p_entity_id limit 1;
$$;
comment on function lookup_saml_tenant_by_entity_id(text) is 'Used by SAML ACS to resolve tenant from IdP Issuer entity_id; SECURITY DEFINER bypasses RLS';

create unique index if not exists uq_tenant_saml_config_entity_id on tenant_saml_config(entity_id);
