-- Auto-update updated_at on workflow_instances (R5-11)

create or replace function update_workflow_instances_updated_at()
returns trigger as $$
begin
  NEW.updated_at = now();
  return NEW;
end;
$$ language plpgsql;

drop trigger if exists trg_workflow_instances_updated_at on workflow_instances;
create trigger trg_workflow_instances_updated_at
  before update on workflow_instances
  for each row execute function update_workflow_instances_updated_at();
