"use client";

import { api, type CommentItem } from "@/lib/api";
import { VAButton, VACard } from "@/components/ui";
import { formatDateTime } from "@/lib/format";
import { useCallback, useEffect, useState } from "react";

interface CommentThreadProps {
  tenantId: string;
  userId: string;
  entityType: string;
  entityId: string;
}

export function CommentThread({
  tenantId,
  userId,
  entityType,
  entityId,
}: CommentThreadProps) {
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [posting, setPosting] = useState(false);

  const loadComments = useCallback(async () => {
    try {
      const res = await api.comments.list(tenantId, {
        entity_type: entityType,
        entity_id: entityId,
        limit: 100,
      });
      setComments(res.items ?? []);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, entityType, entityId]);

  useEffect(() => {
    loadComments();
  }, [loadComments]);

  async function handlePost() {
    if (!body.trim()) return;
    setPosting(true);
    setError(null);
    try {
      await api.comments.create(tenantId, userId, {
        entity_type: entityType,
        entity_id: entityId,
        body: body.trim(),
      });
      setBody("");
      await loadComments();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setPosting(false);
    }
  }

  async function handleDelete(commentId: string) {
    setError(null);
    try {
      await api.comments.delete(tenantId, userId, commentId);
      await loadComments();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-3">
      {error && (
        <p className="text-sm text-va-danger">{error}</p>
      )}

      {loading ? (
        <p className="text-sm text-va-text2">Loading comments\u2026</p>
      ) : comments.length === 0 ? (
        <p className="text-sm text-va-text2">No comments yet.</p>
      ) : (
        <div className="space-y-2">
          {comments.map((c) => (
            <VACard key={c.comment_id} className="p-3">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-va-text whitespace-pre-wrap">
                    {c.body}
                  </p>
                  <div className="mt-1 flex items-center gap-2 text-xs text-va-text2">
                    {c.created_by && (
                      <span className="font-mono">
                        {c.created_by.slice(0, 8)}
                      </span>
                    )}
                    <span>{formatDateTime(c.created_at)}</span>
                  </div>
                </div>
                {c.created_by === userId && (
                  <button
                    type="button"
                    onClick={() => handleDelete(c.comment_id)}
                    className="shrink-0 rounded px-1.5 py-0.5 text-xs text-va-danger hover:bg-va-danger/10 focus:outline-none focus-visible:ring-2 focus-visible:ring-va-danger"
                  >
                    Delete
                  </button>
                )}
              </div>
            </VACard>
          ))}
        </div>
      )}

      {/* Compose box */}
      <div className="flex gap-2">
        <textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Add a comment\u2026"
          rows={2}
          className="flex-1 resize-none rounded-va-sm border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text placeholder-va-text2 focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
        />
        <VAButton
          type="button"
          variant="primary"
          onClick={handlePost}
          disabled={posting || !body.trim()}
          className="self-end"
        >
          {posting ? "Posting\u2026" : "Post"}
        </VAButton>
      </div>
    </div>
  );
}
