-- VA-P6-06: Acknowledgment tracking for learning feedback (author marks as read)

alter table change_summaries
  add column if not exists acknowledged_at timestamptz;

create index if not exists idx_change_summaries_acknowledged
  on change_summaries(tenant_id, acknowledged_at) where acknowledged_at is null;
