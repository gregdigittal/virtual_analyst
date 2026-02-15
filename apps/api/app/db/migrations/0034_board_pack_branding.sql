-- VA-P7-07 optional / Phase 10: Board pack branding (tenant logo, colours, T&C footer).

alter table board_packs add column if not exists branding_json jsonb not null default '{}'::jsonb;
comment on column board_packs.branding_json is 'Optional branding: logo_url, primary_color, terms_footer; applied on export (Phase 10).';
