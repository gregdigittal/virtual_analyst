"use client";

import { api, type FeedbackItem } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VAButton } from "@/components/ui";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

function FeedbackCard({
  item,
  tenantId,
  userId,
  onAcknowledge,
}: {
  item: FeedbackItem;
  tenantId: string;
  userId: string;
  onAcknowledge: (summaryId: string) => void;
}) {
  const isUnacknowledged = !item.acknowledged_at;
  const createdStr = item.created_at
    ? new Date(item.created_at).toLocaleString(undefined, {
        dateStyle: "short",
        timeStyle: "short",
      })
    : null;

  return (
    <div
      className={`rounded-va-lg border p-4 ${
        isUnacknowledged
          ? "border-va-amber/60 bg-va-panel/90 ring-1 ring-va-amber/30"
          : "border-va-border bg-va-panel/80"
      }`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/inbox/${item.assignment_id}`}
              className="font-medium text-va-text hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue rounded"
            >
              Assignment {item.assignment_id.slice(0, 12)}…
            </Link>
            {isUnacknowledged && (
              <span className="rounded bg-va-amber/20 px-2 py-0.5 text-xs font-medium text-va-amber">
                New feedback
              </span>
            )}
            {createdStr && (
              <span className="text-sm text-va-text2">{createdStr}</span>
            )}
          </div>
          <p className="mt-2 text-sm text-va-text2">Decision: {item.decision.replace("_", " ")}</p>
          <div className="mt-2 whitespace-pre-wrap text-sm text-va-text">{item.summary_text}</div>

          {item.corrections.length > 0 && (
            <div className="mt-3 rounded border border-va-border bg-va-midnight/50 p-3">
              <p className="mb-2 text-xs font-medium uppercase tracking-wide text-va-text2">
                Changes requested
              </p>
              <ul className="space-y-2">
                {item.corrections.map((c, i) => (
                  <li key={i} className="text-sm">
                    <span className="font-mono text-va-text2">{c.path}</span>
                    <div className="mt-1 flex flex-wrap gap-x-2 gap-y-1">
                      <span className="text-va-danger line-through">
                        {c.old_value ?? "(empty)"}
                      </span>
                      <span className="text-va-text2">→</span>
                      <span className="text-va-success">
                        {c.new_value ?? "(empty)"}
                      </span>
                    </div>
                    {c.reason && (
                      <p className="mt-1 text-va-text2/90 italic">Reason: {c.reason}</p>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {item.learning_points.length > 0 && (
            <div className="mt-3 rounded border border-va-border bg-va-midnight/30 p-3">
              <p className="mb-2 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-va-text2">
                Learning points
                <span className="rounded bg-va-blue/20 px-1.5 py-0.5 text-[10px] text-va-blue">
                  AI-generated
                </span>
              </p>
              <ul className="list-inside list-disc space-y-1 text-sm text-va-text">
                {item.learning_points.map((lp, i) => (
                  <li key={i}>
                    {typeof lp === "string" ? lp : lp.point}
                    {typeof lp === "object" && lp.category && (
                      <span className="ml-1 text-va-text2">({lp.category})</span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        {isUnacknowledged && (
          <VAButton
            onClick={() => onAcknowledge(item.summary_id)}
            aria-label="Mark as read"
            variant="secondary"
          >
            Acknowledge
          </VAButton>
        )}
      </div>
    </div>
  );
}

export default function FeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [unackOnly, setUnackOnly] = useState(false);

  const load = useCallback(async () => {
    if (!tenantId || !userId) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.feedback.list(tenantId, userId, {
        limit: 50,
        unacknowledgedOnly: unackOnly,
      });
      setItems(res.items);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, [tenantId, userId, unackOnly]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (cancelled) return;
      if (!ctx) {
        api.setAccessToken(null);
        return;
      }
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
      api.setAccessToken(ctx.accessToken);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (tenantId && userId) load();
  }, [tenantId, userId, load]);

  async function handleAcknowledge(summaryId: string) {
    if (!tenantId || !userId) return;
    try {
      await api.feedback.acknowledge(tenantId, userId, summaryId);
      setItems((prev) =>
        prev.map((it) =>
          it.summary_id === summaryId
            ? { ...it, acknowledged_at: new Date().toISOString() }
            : it
        )
      );
    } catch {
      // leave list as-is; could toast
    }
  }

  if (!tenantId || !userId) {
    return (
      <div className="flex items-center justify-center py-12 text-va-text2">
        Loading…
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-va-text">Learning feedback</h1>
          <p className="mt-1 text-sm text-va-text2">
            Review feedback and learning points from your submitted work.
          </p>
        </div>
        <Link href="/inbox">
          <VAButton variant="secondary">Back to Inbox</VAButton>
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <label className="flex cursor-pointer items-center gap-2 text-sm text-va-text2">
          <input
            type="checkbox"
            checked={unackOnly}
            onChange={(e) => setUnackOnly(e.target.checked)}
            className="rounded border-va-border"
          />
          Unacknowledged only
        </label>
      </div>

      {error && (
        <VACard className="border-va-danger/50 bg-va-danger/10 text-va-danger">
          {error}
        </VACard>
      )}

      {loading ? (
        <p className="py-8 text-center text-va-text2">Loading feedback…</p>
      ) : items.length === 0 ? (
        <VACard className="py-12 text-center text-va-text2">
          No feedback yet. Feedback appears here after a reviewer returns your work with
          corrections.
        </VACard>
      ) : (
        <ul className="space-y-4">
          {items.map((item) => (
            <li key={item.summary_id}>
              <FeedbackCard
                item={item}
                tenantId={tenantId}
                userId={userId}
                onAcknowledge={handleAcknowledge}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
