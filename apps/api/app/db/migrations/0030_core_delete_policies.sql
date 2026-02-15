-- R8-05: Add DELETE RLS policies to core tables that were missing them in 0002.

drop policy if exists "model_baselines_delete" on model_baselines;
create policy "model_baselines_delete" on model_baselines for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "model_changesets_delete" on model_changesets;
create policy "model_changesets_delete" on model_changesets for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "ventures_delete" on ventures;
create policy "ventures_delete" on ventures for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "venture_artifacts_delete" on venture_artifacts;
create policy "venture_artifacts_delete" on venture_artifacts for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "runs_delete" on runs;
create policy "runs_delete" on runs for delete
  using (tenant_id = current_tenant_id());

drop policy if exists "run_artifacts_delete" on run_artifacts;
create policy "run_artifacts_delete" on run_artifacts for delete
  using (tenant_id = current_tenant_id());

-- Also add missing UPDATE policies for venture_artifacts and run_artifacts
drop policy if exists "venture_artifacts_update" on venture_artifacts;
create policy "venture_artifacts_update" on venture_artifacts for update
  using (tenant_id = current_tenant_id());

drop policy if exists "run_artifacts_update" on run_artifacts;
create policy "run_artifacts_update" on run_artifacts for update
  using (tenant_id = current_tenant_id());
