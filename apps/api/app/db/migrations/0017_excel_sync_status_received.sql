-- Allow 'received' status for excel_sync_events (push logged but not applied)
alter table excel_sync_events drop constraint if exists excel_sync_events_status_check;
alter table excel_sync_events add constraint excel_sync_events_status_check
  check (status in ('succeeded', 'failed', 'partial', 'received'));
