-- FIX-C01: Add IdP certificate column for SAML response signature verification.
-- Store PEM-formatted X.509 certificate from IdP metadata.

alter table tenant_saml_config
  add column if not exists idp_certificate text;

comment on column tenant_saml_config.idp_certificate is 'PEM-formatted X.509 certificate from IdP metadata; required for production SAML signature verification';
