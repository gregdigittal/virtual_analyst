-- R8-07: Add UPDATE RLS policies for comments and document_attachments.

drop policy if exists "comments_update" on comments;
create policy "comments_update" on comments for update
  using (tenant_id = current_tenant_id());

drop policy if exists "document_attachments_update" on document_attachments;
create policy "document_attachments_update" on document_attachments for update
  using (tenant_id = current_tenant_id());
