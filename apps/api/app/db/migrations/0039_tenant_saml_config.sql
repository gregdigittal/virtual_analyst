-- VA-P8-02: SSO/SAML — per-tenant IdP config (optional).

create table if not exists tenant_saml_config (
  tenant_id text not null references tenants(id) on delete cascade,
  idp_metadata_url text,
  idp_metadata_xml text,
  entity_id text not null,
  acs_url text not null,
  idp_sso_url text,
  attribute_mapping_json jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (tenant_id),
  constraint chk_saml_config check (idp_metadata_url is not null or idp_metadata_xml is not null or idp_sso_url is not null)
);
comment on column tenant_saml_config.attribute_mapping_json is 'Maps IdP attribute names to tenant_id, email, name';

alter table tenant_saml_config enable row level security;
drop policy if exists "tenant_saml_config_select" on tenant_saml_config;
drop policy if exists "tenant_saml_config_insert" on tenant_saml_config;
drop policy if exists "tenant_saml_config_update" on tenant_saml_config;
drop policy if exists "tenant_saml_config_delete" on tenant_saml_config;
create policy "tenant_saml_config_select" on tenant_saml_config for select using (tenant_id = current_tenant_id());
create policy "tenant_saml_config_insert" on tenant_saml_config for insert with check (tenant_id = current_tenant_id());
create policy "tenant_saml_config_update" on tenant_saml_config for update using (tenant_id = current_tenant_id());
create policy "tenant_saml_config_delete" on tenant_saml_config for delete using (tenant_id = current_tenant_id());
