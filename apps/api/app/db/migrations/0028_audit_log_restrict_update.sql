-- R8-03: Remove general UPDATE policy on audit_log. Append-only: no direct updates.
-- GDPR anonymization uses a SECURITY DEFINER function instead.

drop policy if exists "audit_log_update" on audit_log;

-- SECURITY DEFINER function for GDPR anonymization only
create or replace function anonymize_audit_user(
  p_tenant_id text,
  p_user_id text,
  p_replacement text default 'anonymized'
) returns integer
language plpgsql security definer set search_path = public
as $$
declare
  affected integer;
begin
  update audit_log
  set user_id = p_replacement,
      event_data = event_data - 'user_email' - 'user_name'
  where tenant_id = p_tenant_id and user_id = p_user_id;
  GET DIAGNOSTICS affected = ROW_COUNT;
  return affected;
end;
$$;
