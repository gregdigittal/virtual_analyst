"use client";

import { VAButton, VACard, VAEmptyState, VAInput, VAListToolbar, VASelect, VASpinner, useToast } from "@/components/ui";
import { api, type CommentItem, type DocumentItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";
import { useCallback, useEffect, useState } from "react";

const ENTITY_TYPES = [
  "run",
  "draft_session",
  "memo_pack",
  "baseline",
  "scenario",
  "venture",
];

export default function DocumentsPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [docs, setDocs] = useState<DocumentItem[]>([]);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [entityType, setEntityType] = useState(ENTITY_TYPES[0]);
  const [entityId, setEntityId] = useState("");
  const [commentBody, setCommentBody] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docSearch, setDocSearch] = useState("");
  const { toast } = useToast();

  const loadDocuments = useCallback(async () => {
    if (!tenantId) return;
    if (!entityId.trim()) { toast.error("Enter an entity ID to load documents"); return; }
    setLoading(true);
    setError(null);
    try {
      const res = await api.documents.list(tenantId, {
        entity_type: entityType,
        entity_id: entityId,
        limit: 50,
        offset: 0,
      });
      setDocs(res.items ?? []);
      const commentsRes = await api.comments.list(tenantId, {
        entity_type: entityType,
        entity_id: entityId,
        limit: 100,
        offset: 0,
      });
      setComments(commentsRes.items ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, entityType, entityId]);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, []);

  async function handleUpload() {
    if (!tenantId) return;
    if (!entityId.trim()) { toast.error("Enter an entity ID"); return; }
    if (!file) { toast.error("Select a file to upload"); return; }
    setError(null);
    try {
      await api.documents.upload(tenantId, userId, {
        entity_type: entityType,
        entity_id: entityId,
        file,
      });
      setFile(null);
      await loadDocuments();
      toast.success("Document uploaded");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  async function handleAddComment() {
    if (!tenantId) return;
    if (!entityId.trim()) { toast.error("Enter an entity ID first"); return; }
    if (!commentBody.trim()) { toast.error("Enter a comment"); return; }
    setError(null);
    try {
      await api.comments.create(tenantId, userId, {
        entity_type: entityType,
        entity_id: entityId,
        body: commentBody.trim(),
      });
      setCommentBody("");
      await loadDocuments();
      toast.success("Comment added");
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
      toast.error(msg);
    }
  }

  const filteredDocs = docs.filter((doc) => {
    if (!docSearch) return true;
    const q = docSearch.toLowerCase();
    return (
      doc.filename.toLowerCase().includes(q) ||
      (doc.content_type ?? "").toLowerCase().includes(q)
    );
  });

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Documents & Comments
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Upload attachments and capture discussion threads for any entity.
        </p>
      </div>

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      <VACard className="p-5">
        <div className="grid gap-3 md:grid-cols-3">
          <VASelect
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
          >
            {ENTITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </VASelect>
          <VAInput
            placeholder="Entity ID"
            value={entityId}
            onChange={(e) => setEntityId(e.target.value)}
          />
          <VAButton variant="secondary" onClick={loadDocuments}>
            Load
          </VAButton>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            type="file"
            className="text-sm text-va-text2"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <VAButton onClick={handleUpload} disabled={!file}>
            Upload document
          </VAButton>
        </div>
      </VACard>

      {loading ? (
        <VASpinner label="Loading documents…" className="mt-4" />
      ) : docs.length === 0 ? (
        <VAEmptyState
          icon="folder"
          title="No documents yet"
          description="Upload documents using the form above."
          className="mt-4"
        />
      ) : (
        <>
          <VAListToolbar
            searchValue={docSearch}
            onSearchChange={setDocSearch}
            searchPlaceholder="Search documents..."
            className="mt-4"
          />
          {filteredDocs.length === 0 ? (
            <VAEmptyState
              variant="no-results"
              title="No matching documents"
              description="Try a different search term."
            />
          ) : (
            <div className="overflow-x-auto rounded-va-lg border border-va-border">
              <table className="w-full text-sm text-va-text">
                <thead>
                  <tr className="border-b border-va-border bg-va-surface">
                    <th className="px-3 py-2 text-left font-medium">Filename</th>
                    <th className="px-3 py-2 text-left font-medium">Type</th>
                    <th className="px-3 py-2 text-left font-medium">Size</th>
                    <th className="px-3 py-2" />
                  </tr>
                </thead>
                <tbody>
                  {filteredDocs.map((doc) => (
                    <tr key={doc.document_id} className="border-b border-va-border/50">
                      <td className="px-3 py-2">{doc.filename}</td>
                      <td className="px-3 py-2 text-va-text2">{doc.content_type}</td>
                      <td className="px-3 py-2 text-va-text2">
                        {doc.file_size ? `${Math.round(doc.file_size / 1024)} KB` : "—"}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <a
                          className="text-va-blue hover:underline"
                          href={api.documents.downloadUrl(doc.document_id)}
                          target="_blank"
                          rel="noreferrer"
                        >
                          Download
                        </a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <VACard className="mt-6 p-5">
        <h2 className="text-lg font-medium text-va-text">Comments</h2>
        {comments.length === 0 ? (
          <p className="mt-2 text-sm text-va-text2">
            No comments yet for this entity.
          </p>
        ) : (
          <ul className="mt-3 space-y-2 text-sm text-va-text2">
            {comments.map((c) => (
              <li key={c.comment_id} className="rounded-va-xs border border-va-border/60 p-3">
                <p className="text-va-text">{c.body}</p>
                <p className="mt-1 text-xs text-va-text2">
                  {formatDateTime(c.created_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
        <div className="mt-4 flex flex-col gap-3">
          <textarea
            className="min-h-[80px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
            placeholder="Add a comment"
            value={commentBody}
            onChange={(e) => setCommentBody(e.target.value)}
          />
          <VAButton onClick={handleAddComment}>Add comment</VAButton>
        </div>
      </VACard>
    </main>
  );
}
