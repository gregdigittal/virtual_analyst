"use client";

import {
  api,
  ApiError,
  type DraftDetail,
  type PendingProposal,
} from "@/lib/api";
import {
  EvidenceChip,
  RiskBadge,
  StatePill,
  VAButton,
  VACard,
  VAConfirmDialog,
  VAInput,
  VASpinner,
  useToast,
} from "@/components/ui";
import { createClient } from "@/lib/supabase/client";
import { Nav } from "@/components/nav";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

function AssumptionTree({ data }: { data: unknown }) {
  if (data === null || data === undefined)
    return <span className="text-va-text2">—</span>;
  if (Array.isArray(data)) {
    return (
      <ul className="list-inside list-disc pl-4 text-sm text-va-text2">
        {data.map((item, i) => (
          <li
            key={
              typeof item === "object" && item !== null && "stream_id" in item
                ? (item as Record<string, unknown>).stream_id as string
                : `idx-${i}`
            }
          >
            <AssumptionTree data={item} />
          </li>
        ))}
      </ul>
    );
  }
  if (typeof data === "object") {
    const entries = Object.entries(data as Record<string, unknown>);
    const displayEntries = entries.filter(
      ([key]) => !key.endsWith("_confidence") && !key.endsWith("_evidence")
    );
    const record = data as Record<string, unknown>;
    return (
      <ul className="space-y-1 pl-2 text-sm">
        {displayEntries.map(([key, value]) => {
          const confidence = record[`${key}_confidence`] as
            | "high"
            | "medium"
            | "low"
            | undefined;
          const evidence = record[`${key}_evidence`] as string | undefined;
          return (
            <li key={key} className="border-l border-va-border pl-2">
              <span className="font-medium text-va-text">{key}:</span>{" "}
              {typeof value === "object" &&
              value !== null &&
              !Array.isArray(value) ? (
                <AssumptionTree data={value} />
              ) : (
                <>
                  <span className="text-va-text2">{String(value)}</span>
                  {confidence && (
                    <RiskBadge
                      level={
                        confidence === "high"
                          ? "low"
                          : confidence === "medium"
                            ? "medium"
                            : "high"
                      }
                      className="ml-1"
                    />
                  )}
                  {evidence && (
                    <EvidenceChip
                      source={evidence}
                      className="ml-1"
                    />
                  )}
                </>
              )}
            </li>
          );
        })}
      </ul>
    );
  }
  return <span className="text-va-text2">{String(data)}</span>;
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
  const { toast } = useToast();
  const [confirmAction, setConfirmAction] = useState<{ action: () => void; title: string; description: string } | null>(null);

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
      toast.success("Message sent");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast.error(e instanceof Error ? e.message : String(e));
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
      toast.success("Proposal accepted");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast.error(e instanceof Error ? e.message : String(e));
    }
  }

  async function rejectProposal(proposalId: string) {
    if (!tenantId) return;
    setError(null);
    try {
      await api.drafts.rejectProposal(tenantId, id, proposalId);
      await loadDraft();
      toast.success("Proposal rejected");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast.error(e instanceof Error ? e.message : String(e));
    }
  }

  async function markReady() {
    if (!tenantId) return;
    setMarkingReady(true);
    setError(null);
    try {
      await api.drafts.patch(tenantId, id, { status: "ready_to_commit" });
      await loadDraft();
      toast.success("Draft marked ready");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast.error(e instanceof Error ? e.message : String(e));
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
      toast.success("Draft abandoned");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      toast.error(e instanceof Error ? e.message : String(e));
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
      toast.success("Draft committed");
    } catch (e) {
      if (e instanceof ApiError && e.statusCode === 409) {
        const integrity = (e.body as { detail?: { integrity?: { checks: { check_id?: string; severity?: string; message?: string }[]; status: string } } })?.detail?.integrity;
        if (integrity?.checks) {
          setIntegrityDialog({ checks: integrity.checks, status: integrity.status });
          return;
        }
      }
      setError(e instanceof Error ? e.message : String(e));
      toast.error(e instanceof Error ? e.message : String(e));
    } finally {
      setCommitting(false);
    }
  }

  if (!tenantId && !loading) return null;

  const statePill =
    detail?.status === "active"
      ? "draft"
      : detail?.status === "ready_to_commit"
        ? "selected"
        : detail?.status === "committed"
          ? "committed"
          : null;

  return (
    <div className="flex min-h-screen flex-col bg-va-midnight">
      <Nav />
      <div className="mb-2 flex items-center gap-4 px-4 pt-4">
        <Link
          href="/drafts"
          className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
        >
          ← Drafts
        </Link>
      </div>
      {error && (
        <div
          className="mx-4 mb-2 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}
      {detail?.status === "committed" && (
        <div
          className="mx-4 mb-2 rounded-va-xs border border-va-success/50 bg-va-success/10 px-3 py-2 text-sm text-va-success"
          role="status"
        >
          This draft has been committed as a baseline.
        </div>
      )}
      {detail?.status === "abandoned" && (
        <div
          className="mx-4 mb-2 rounded-va-xs border border-va-border bg-va-panel/80 px-3 py-2 text-sm text-va-text2"
          role="status"
        >
          This draft has been abandoned.
        </div>
      )}
      {loading ? (
        <VASpinner label="Loading…" className="px-4" />
      ) : !detail ? (
        <p className="px-4 text-va-text2">Draft not found.</p>
      ) : (
        <>
          <div className="flex min-h-0 flex-1 gap-4 px-4">
            <VACard
              className="flex min-w-[60%] flex-1 flex-col overflow-hidden"
            >
              <div className="border-b border-va-border px-3 py-2 text-sm font-medium text-va-text">
                Assumptions
              </div>
              <div className="flex-1 overflow-auto p-3">
                <AssumptionTree data={detail.workspace?.assumptions ?? {}} />
              </div>
            </VACard>
            <VACard className="flex w-[40%] min-w-[280px] flex-col overflow-hidden">
              <div className="border-b border-va-border px-3 py-2 text-sm font-medium text-va-text">
                Chat
              </div>
              <div className="flex-1 space-y-3 overflow-auto p-3">
                {(detail.workspace?.chat_history ?? []).map((msg, i) => (
                  <div
                    key={i}
                    className={`rounded-va-sm px-3 py-2 text-sm ${
                      msg.role === "user"
                        ? "ml-4 bg-va-blue/20 text-va-text"
                        : "mr-4 bg-va-panel text-va-text2"
                    }`}
                  >
                    {msg.content}
                  </div>
                ))}
                <div ref={chatEndRef} />
              </div>
              <div className="flex gap-2 border-t border-va-border p-2">
                <VAInput
                  type="text"
                  value={chatMessage}
                  onChange={(e) => setChatMessage(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && sendChat()}
                  placeholder="Message…"
                  className="flex-1"
                  disabled={detail.status !== "active"}
                />
                <VAButton
                  type="button"
                  variant="primary"
                  onClick={sendChat}
                  disabled={
                    chatSending ||
                    detail.status !== "active" ||
                    !chatMessage.trim()
                  }
                >
                  Send
                </VAButton>
              </div>
            </VACard>
          </div>
          {(detail.workspace?.pending_proposals?.length ?? 0) > 0 && (
            <div className="mx-4 mt-2 rounded-va-lg border border-va-warning/40 bg-va-warning/10 p-3">
              <div className="mb-2 text-sm font-medium text-va-warning">
                Pending proposals
              </div>
              <ul className="space-y-2">
                {(detail.workspace.pending_proposals as PendingProposal[]).map(
                  (p) => (
                    <li
                      key={p.id}
                      className="rounded-va-sm border border-va-border bg-va-panel/80 p-2 text-sm text-va-text"
                    >
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs text-va-text2">
                          {p.path}
                        </span>
                        {p.confidence && (
                          <RiskBadge
                            level={
                              p.confidence === "high"
                                ? "low"
                                : p.confidence === "medium"
                                  ? "medium"
                                  : "high"
                            }
                          />
                        )}
                      </div>
                      <div className="mt-1">{String(p.value)}</div>
                      {p.evidence && (
                        <EvidenceChip
                          source={p.evidence}
                          className="mt-1"
                        />
                      )}
                      {p.reasoning && (
                        <div className="mt-1 text-xs italic text-va-text2">
                          {p.reasoning}
                        </div>
                      )}
                      <div className="mt-2 flex gap-2">
                        <VAButton
                          type="button"
                          variant="primary"
                          onClick={() => acceptProposal(p.id)}
                          disabled={detail.status !== "active"}
                          className="!py-1 !text-xs"
                        >
                          Accept
                        </VAButton>
                        <VAButton
                          type="button"
                          variant="danger"
                          onClick={() => rejectProposal(p.id)}
                          disabled={detail.status !== "active"}
                          className="!py-1 !text-xs"
                        >
                          Reject
                        </VAButton>
                      </div>
                    </li>
                  )
                )}
              </ul>
            </div>
          )}
          <div className="mx-4 mb-4 mt-2 flex items-center justify-between rounded-va-lg border border-va-border bg-va-panel/80 px-4 py-3">
            {statePill ? (
              <StatePill state={statePill} />
            ) : (
              <span className="rounded-va-xs bg-va-muted/20 px-2 py-1 text-sm text-va-text2">
                {detail.status}
              </span>
            )}
            <div className="flex gap-2">
              {(detail.status === "active" ||
                detail.status === "ready_to_commit") && (
                <VAButton
                  type="button"
                  variant="secondary"
                  onClick={() => setConfirmAction({
                    action: abandonDraft,
                    title: "Abandon this draft?",
                    description: "This action cannot be undone. The draft will be permanently deleted.",
                  })}
                  className="border-va-danger/50 text-va-danger hover:bg-va-danger/10"
                >
                  Abandon
                </VAButton>
              )}
              {detail.status === "active" && (
                <VAButton
                  type="button"
                  variant="secondary"
                  onClick={markReady}
                  disabled={markingReady}
                  className="border-va-violet text-va-violet hover:bg-va-violet/10"
                >
                  {markingReady ? "Updating…" : "Mark ready to commit"}
                </VAButton>
              )}
              {detail.status === "ready_to_commit" && (
                <VAButton
                  type="button"
                  variant="primary"
                  onClick={() => commit(false)}
                  disabled={committing}
                >
                  {committing ? "Committing…" : "Commit"}
                </VAButton>
              )}
            </div>
          </div>
        </>
      )}
      {integrityDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <VACard className="mx-4 max-h-[80vh] w-full max-w-lg overflow-auto p-4 shadow-va-md">
            <h3 className="font-semibold text-va-text">Integrity checks</h3>
            <p className="mt-1 text-sm text-va-text2">
              Please acknowledge warnings to proceed with commit.
            </p>
            <ul className="mt-3 space-y-2">
              {integrityDialog.checks.map(
                (
                  c: {
                    check_id?: string;
                    severity?: string;
                    message?: string;
                  },
                  i: number
                ) => (
                  <li
                    key={i}
                    className="rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
                  >
                    <span className="font-medium">{c.check_id ?? "—"}</span>{" "}
                    <span
                      className={
                        c.severity === "error"
                          ? "text-va-danger"
                          : "text-va-warning"
                      }
                    >
                      {c.severity}
                    </span>
                    : {c.message ?? ""}
                  </li>
                )
              )}
            </ul>
            <div className="mt-4 flex justify-end gap-2">
              <VAButton
                type="button"
                variant="secondary"
                onClick={() => setIntegrityDialog(null)}
              >
                Cancel
              </VAButton>
              <VAButton
                type="button"
                variant="primary"
                onClick={() => commit(true)}
                disabled={committing}
              >
                Acknowledge and commit
              </VAButton>
            </div>
          </VACard>
        </div>
      )}
      <VAConfirmDialog
        open={!!confirmAction}
        title={confirmAction?.title ?? ""}
        description={confirmAction?.description}
        confirmLabel="Confirm"
        onConfirm={() => { confirmAction?.action(); setConfirmAction(null); }}
        onCancel={() => setConfirmAction(null)}
      />
    </div>
  );
}
