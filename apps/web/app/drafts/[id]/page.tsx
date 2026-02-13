"use client";

import {
  api,
  ApiError,
  type DraftDetail,
  type PendingProposal,
} from "@/lib/api";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

function AssumptionTree({ data }: { data: unknown }) {
  if (data === null || data === undefined) return <span className="text-muted-foreground">—</span>;
  if (Array.isArray(data)) {
    return (
      <ul className="list-inside list-disc pl-4 text-sm">
        {data.map((item, i) => (
          <li key={typeof item === "object" && item !== null && "stream_id" in item ? (item as Record<string, unknown>).stream_id as string : `idx-${i}`}>
            <AssumptionTree data={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof data === "object") {
    const entries = Object.entries(data as Record<string, unknown>);
    const displayEntries = entries.filter(([key]) => !key.endsWith("_confidence") && !key.endsWith("_evidence"));
    const record = data as Record<string, unknown>;
    return (
      <ul className="space-y-1 pl-2 text-sm">
        {displayEntries.map(([key, value]) => {
          const confidence = record[`${key}_confidence`] as string | undefined;
          const evidence = record[`${key}_evidence`] as string | undefined;
          return (
            <li key={key} className="border-l border-border pl-2">
              <span className="font-medium text-foreground">{key}:</span>{" "}
              {typeof value === "object" && value !== null && !Array.isArray(value) ? (
                <AssumptionTree data={value} />
              ) : (
                <>
                  <span className="text-muted-foreground">{String(value)}</span>
                  {confidence && (
                    <span
                      className={`ml-1 inline-block rounded-full px-1.5 py-0.5 text-[10px] font-medium ${
                        confidence === "high"
                          ? "bg-green-100 text-green-800"
                          : confidence === "medium"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-red-100 text-red-800"
                      }`}
                    >
                      {confidence}
                    </span>
                  )}
                  {evidence && (
                    <span className="ml-1 text-[10px] text-muted-foreground italic">
                      ({evidence})
                    </span>
                  )}
                </>
              )}
            </li>
          );
        })}
      </ul>
    );
  }
  return <span className="text-muted-foreground">{String(data)}</span>;
}

export default function DraftWorkspacePage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [detail, setDetail] = useState<DraftDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [chatMessage, setChatMessage] = useState("");
  const [chatSending, setChatSending] = useState(false);
  const [markingReady, setMarkingReady] = useState(false);
  const [committing, setCommitting] = useState(false);
  const [integrityDialog, setIntegrityDialog] = useState<{
    checks: { check_id?: string; severity?: string; message?: string }[];
    status: string;
  } | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const loadDraft = useCallback(async () => {
    if (!tenantId) return;
    try {
      const res = await api.drafts.get(tenantId, id);
      setDetail(res);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, id]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const supabase = createClient();
      const {
        data: { session },
      } = await supabase.auth.getSession();
      if (!session?.user?.id) return;
      setTenantId(session.user.id);
      if (!cancelled) setLoading(true);
      try {
        const res = await api.drafts.get(session.user.id, id);
        if (!cancelled) {
          setDetail(res);
          setError(null);
        }
      } catch (e) {
        if (!cancelled)
          setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail]);

  async function sendChat() {
    if (!tenantId || !chatMessage.trim()) return;
    setChatSending(true);
    setError(null);
    try {
      await api.drafts.chat(tenantId, id, chatMessage.trim());
      setChatMessage("");
      await loadDraft();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setChatSending(false);
    }
  }

  async function acceptProposal(proposalId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.drafts.acceptProposal(tenantId, id, proposalId);
      await loadDraft();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function rejectProposal(proposalId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.drafts.rejectProposal(tenantId, id, proposalId);
      await loadDraft();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function markReady() {
    if (!tenantId) return;
    setMarkingReady(true);
    setError(null);
    try {
      await api.drafts.patch(tenantId, id, { status: "ready_to_commit" });
      await loadDraft();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setMarkingReady(false);
    }
  }

  async function abandonDraft() {
    if (!tenantId) return;
    setError(null);
    try {
      await api.drafts.delete(tenantId, id);
      router.push("/drafts");
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function commit(acknowledgeWarnings: boolean) {
    if (!tenantId) return;
    setCommitting(true);
    setError(null);
    setIntegrityDialog(null);
    try {
      const result = await api.drafts.commit(tenantId, id, acknowledgeWarnings);
      router.push(`/baselines/${result.baseline_id}`);
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError && e.statusCode === 409) {
        const integrity = (e.body as { detail?: { integrity?: { checks: { check_id?: string; severity?: string; message?: string }[]; status: string } } })?.detail?.integrity;
        if (integrity?.checks) {
          setIntegrityDialog({ checks: integrity.checks, status: integrity.status });
          return;
        }
      }
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCommitting(false);
    }
  }

  if (!tenantId && !loading) return null;

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Nav />
      <div className="mb-2 flex items-center gap-4 px-4 pt-4">
        <Link
          href="/drafts"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Drafts
        </Link>
      </div>
      {error && (
        <div
          className="mx-4 mb-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800"
          role="alert"
        >
          {error}
        </div>
      )}
      {detail && detail.status === "committed" && (
        <div className="mx-4 mb-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800" role="status">
          This draft has been committed as a baseline.
        </div>
      )}
      {detail && detail.status === "abandoned" && (
        <div className="mx-4 mb-2 rounded-md border border-muted bg-muted/50 px-3 py-2 text-sm text-muted-foreground" role="status">
          This draft has been abandoned.
        </div>
      )}
      {loading ? (
        <p className="px-4 text-muted-foreground">Loading…</p>
      ) : !detail ? (
        <p className="px-4 text-muted-foreground">Draft not found.</p>
      ) : (
        <>
          <div className="flex flex-1 min-h-0 px-4 gap-4">
            <div className="flex-1 min-w-0 flex flex-col rounded-lg border border-border bg-card overflow-hidden" style={{ minWidth: "60%" }}>
              <div className="px-3 py-2 border-b border-border font-medium text-sm">
                Assumptions
              </div>
              <div className="flex-1 overflow-auto p-3">
                <AssumptionTree data={detail.workspace?.assumptions ?? {}} />
              </div>
            </div>
            <div className="w-[40%] min-w-[280px] flex flex-col rounded-lg border border-border bg-card overflow-hidden">
              <div className="px-3 py-2 border-b border-border font-medium text-sm">
                Chat
              </div>
              <div className="flex-1 overflow-auto p-3 space-y-3">
                {(detail.workspace?.chat_history ?? []).map((msg, i) => (
                  <div
                    key={i}
                    className={`rounded-lg px-3 py-2 text-sm ${
                      msg.role === "user"
                        ? "ml-4 bg-blue-100 text-blue-900"
                        : "mr-4 bg-muted text-foreground"
                    }`}
                  >
                    {msg.content}
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
              <div className="p-2 border-t border-border flex gap-2">
                <input
                  type="text"
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendChat()}
                  placeholder="Message…"
                  className="flex-1 rounded border border-border px-3 py-2 text-sm"
                  disabled={detail.status !== "active"}
                />
                <button
                  type="button"
                  onClick={sendChat}
                  disabled={chatSending || detail.status !== "active" || !chatMessage.trim()}
                  className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
          {(detail.workspace?.pending_proposals?.length ?? 0) > 0 && (
            <div className="mx-4 mt-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="text-sm font-medium text-amber-900 mb-2">Pending proposals</div>
              <ul className="space-y-2">
                {(detail.workspace.pending_proposals as PendingProposal[]).map((p) => (
                  <li
                    key={p.id}
                    className="rounded border border-amber-200 bg-white p-2 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs text-muted-foreground">{p.path}</span>
                      {p.confidence && (
                        <span
                          className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${
                            p.confidence === "high"
                              ? "bg-green-100 text-green-800"
                              : p.confidence === "medium"
                                ? "bg-amber-100 text-amber-800"
                                : "bg-red-100 text-red-800"
                          }`}
                        >
                          {p.confidence}
                        </span>
                      )}
                    </div>
                    <div className="mt-1">{String(p.value)}</div>
                    {p.evidence && (
                      <div className="mt-1 text-xs text-muted-foreground">{p.evidence}</div>
                    )}
                    {p.reasoning && (
                      <div className="mt-1 text-xs italic text-muted-foreground">{p.reasoning}</div>
                    )}
                    <div className="mt-2 flex gap-2">
                      <button
                        type="button"
                        onClick={() => acceptProposal(p.id)}
                        disabled={detail.status !== "active"}
                        className="rounded bg-green-600 px-2 py-1 text-xs text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        Accept
                      </button>
                      <button
                        type="button"
                        onClick={() => rejectProposal(p.id)}
                        disabled={detail.status !== "active"}
                        className="rounded bg-red-600 px-2 py-1 text-xs text-white hover:bg-red-700 disabled:opacity-50"
                      >
                        Reject
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
          <div className="mx-4 mt-2 mb-4 flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3">
            <span
              className={`rounded px-2 py-1 text-sm ${
                detail.status === "active"
                  ? "bg-blue-100 text-blue-800"
                  : detail.status === "ready_to_commit"
                    ? "bg-amber-100 text-amber-800"
                    : "bg-muted text-muted-foreground"
              }`}
            >
              {detail.status}
            </span>
            <div className="flex gap-2">
              {(detail.status === "active" || detail.status === "ready_to_commit") && (
                <button
                  type="button"
                  onClick={abandonDraft}
                  className="rounded border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
                >
                  Abandon
                </button>
              )}
              {detail.status === "active" && (
                <button
                  type="button"
                  onClick={markReady}
                  disabled={markingReady}
                  className="rounded bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                >
                  {markingReady ? "Updating…" : "Mark ready to commit"}
                </button>
              )}
              {detail.status === "ready_to_commit" && (
                <button
                  type="button"
                  onClick={() => commit(false)}
                  disabled={committing}
                  className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  {committing ? "Committing…" : "Commit"}
                </button>
              )}
            </div>
          </div>
        </>
      )}
      {integrityDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="mx-4 max-h-[80vh] w-full max-w-lg rounded-lg border border-border bg-card p-4 shadow-lg overflow-auto">
            <h3 className="font-semibold text-foreground">Integrity checks</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Please acknowledge warnings to proceed with commit.
            </p>
            <ul className="mt-3 space-y-2">
              {integrityDialog.checks.map((c: { check_id?: string; severity?: string; message?: string }, i: number) => (
                <li key={i} className="rounded border border-border bg-muted/50 px-3 py-2 text-sm">
                  <span className="font-medium">{c.check_id ?? "—"}</span>{" "}
                  <span className={c.severity === "error" ? "text-red-600" : "text-amber-600"}>
                    {c.severity}
                  </span>
                  : {c.message ?? ""}
                </li>
              ))}
            </ul>
            <div className="mt-4 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIntegrityDialog(null)}
                className="rounded border border-border px-4 py-2 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={() => commit(true)}
                disabled={committing}
                className="rounded bg-green-600 px-4 py-2 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
              >
                Acknowledge and commit
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
