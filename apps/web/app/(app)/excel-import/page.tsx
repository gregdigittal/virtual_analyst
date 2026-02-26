"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useAgentStream } from "@/hooks/useAgentStream";

import { VAButton, VACard, VASpinner } from "@/components/ui";
import { ImportStepper } from "@/components/excel-import/ImportStepper";
import { ChatThread } from "@/components/excel-import/ChatThread";
import { QuestionCard } from "@/components/excel-import/QuestionCard";
import { MappingPreview, type MappingData } from "@/components/excel-import/MappingPreview";
import { ReviewPanel, type ReviewMapping } from "@/components/excel-import/ReviewPanel";

/* ------------------------------------------------------------------ */
/*  SSE stream reader helper                                           */
/* ------------------------------------------------------------------ */

async function consumeSSE(
  resp: Response,
  onEvent: (data: Record<string, unknown>) => void,
) {
  const reader = resp.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      if (part.startsWith("data: ")) {
        try {
          onEvent(JSON.parse(part.slice(6)));
        } catch {
          /* skip malformed events */
        }
      }
    }
  }
}

/* ------------------------------------------------------------------ */
/*  Mapping payload shape (from backend)                               */
/* ------------------------------------------------------------------ */

interface MappingPayload {
  revenue_streams?: { label?: string; source_row_label?: string }[];
  cost_items?: { label?: string }[];
  capex_items?: { label?: string }[];
  unmapped?: (string | { label?: string })[];
}

interface ClassificationPayload {
  entity_name?: string;
  model_summary?: { entity_name?: string };
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function authHeaders(tenantId: string, userId: string | null): Record<string, string> {
  return {
    "X-Tenant-Id": tenantId,
    ...(userId ? { "X-User-Id": userId } : {}),
  };
}

function arrayLen(arr: unknown): number {
  return Array.isArray(arr) ? arr.length : 0;
}

function extractLabels(
  items: Record<string, unknown>[] | undefined,
  ...keys: string[]
): string[] {
  if (!Array.isArray(items)) return [];
  return items.map((item) => {
    for (const k of keys) {
      if (item[k] != null) return String(item[k]);
    }
    return "Unknown";
  });
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ExcelImportPage() {
  const router = useRouter();

  /* ---- auth state ---- */
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);

  /* ---- upload state ---- */
  const [ingestionId, setIngestionId] = useState<string | null>(null);
  const [streaming, setStreaming] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [draftLoading, setDraftLoading] = useState(false);
  const [answering, setAnswering] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  /* ---- agent stream (destructure stable callbacks) ---- */
  const {
    messages,
    currentStep,
    isComplete,
    isPaused,
    pendingQuestion,
    classification,
    mapping,
    error: streamError,
    startStream,
    answerQuestion,
    processEvent,
  } = useAgentStream();

  /* ---------------------------------------------------------------- */
  /*  Auth init                                                        */
  /* ---------------------------------------------------------------- */

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (cancelled) return;
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Upload handler (POST SSE)                                        */
  /* ---------------------------------------------------------------- */

  const handleUpload = useCallback(
    async (file: File) => {
      if (!tenantId) return;
      if (!file.name.toLowerCase().endsWith(".xlsx")) return;

      setUploading(true);

      const formData = new FormData();
      formData.append("file", file);
      const url = api.excelIngestion.getUploadStreamUrl();

      try {
        const resp = await fetch(url, {
          method: "POST",
          body: formData,
          headers: authHeaders(tenantId, userId),
        });

        if (!resp.ok) {
          processEvent({
            type: "error",
            message: `Upload failed (${resp.status})`,
            recoverable: false,
          });
          setUploading(false);
          return;
        }

        const id = resp.headers.get("X-Ingestion-Id") ?? "";
        setIngestionId(id);
        startStream(id, url);
        setStreaming(true);
        setUploading(false);

        await consumeSSE(resp, processEvent);
      } catch (err) {
        processEvent({
          type: "error",
          message: err instanceof Error ? err.message : String(err),
          recoverable: false,
        });
        setUploading(false);
      }
    },
    [tenantId, userId, processEvent, startStream],
  );

  /* ---------------------------------------------------------------- */
  /*  Answer a question (resume stream)                                */
  /* ---------------------------------------------------------------- */

  const handleAnswer = useCallback(
    async (questionId: string, answer: string) => {
      if (!tenantId || !ingestionId) return;

      answerQuestion(questionId, answer);
      setAnswering(true);

      try {
        const url = api.excelIngestion.getAnswerStreamUrl(ingestionId);
        const resp = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...authHeaders(tenantId, userId),
          },
          body: JSON.stringify({
            answers: [{ question: questionId, answer }],
          }),
        });

        await consumeSSE(resp, processEvent);
      } catch (err) {
        processEvent({
          type: "error",
          message: err instanceof Error ? err.message : String(err),
          recoverable: false,
        });
      } finally {
        setAnswering(false);
      }
    },
    [tenantId, userId, ingestionId, answerQuestion, processEvent],
  );

  /* ---------------------------------------------------------------- */
  /*  Create draft                                                     */
  /* ---------------------------------------------------------------- */

  const handleCreateDraft = useCallback(async () => {
    if (!tenantId || !ingestionId) return;
    setDraftLoading(true);
    try {
      const res = await api.excelIngestion.createDraft(tenantId, userId ?? undefined, ingestionId);
      router.push(`/drafts/${res.draft_session_id}`);
    } catch (err) {
      processEvent({
        type: "error",
        message: err instanceof Error ? err.message : String(err),
        recoverable: false,
      });
    } finally {
      setDraftLoading(false);
    }
  }, [tenantId, userId, ingestionId, router, processEvent]);

  /* ---------------------------------------------------------------- */
  /*  Drag-and-drop handlers                                           */
  /* ---------------------------------------------------------------- */

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [handleUpload],
  );

  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  /* ---------------------------------------------------------------- */
  /*  Derive mapping preview data                                      */
  /* ---------------------------------------------------------------- */

  const m = mapping as MappingPayload | null;

  const mappingPreviewData: MappingData | null = m
    ? {
        revenue: arrayLen(m.revenue_streams),
        cost: arrayLen(m.cost_items),
        capex: arrayLen(m.capex_items),
        unmapped: arrayLen(m.unmapped),
      }
    : null;

  /* ---------------------------------------------------------------- */
  /*  Derive review mapping data                                       */
  /* ---------------------------------------------------------------- */

  const cls = classification as ClassificationPayload | null;

  const reviewMapping: ReviewMapping | null =
    isComplete && m
      ? {
          entityName: cls?.entity_name ?? cls?.model_summary?.entity_name ?? "Imported Model",
          revenueStreams: extractLabels(m.revenue_streams as Record<string, unknown>[] | undefined, "label", "source_row_label"),
          costItems: extractLabels(m.cost_items as Record<string, unknown>[] | undefined, "label"),
          capexItems: extractLabels(m.capex_items as Record<string, unknown>[] | undefined, "label"),
          unmapped: Array.isArray(m.unmapped)
            ? m.unmapped.map((u) =>
                typeof u === "object" && u !== null && "label" in u
                  ? String((u as { label: string }).label)
                  : String(u),
              )
            : [],
        }
      : null;

  /* ---------------------------------------------------------------- */
  /*  Render guard                                                     */
  /* ---------------------------------------------------------------- */

  if (!tenantId) return null;

  /* ---------------------------------------------------------------- */
  /*  UI                                                               */
  /* ---------------------------------------------------------------- */

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      {/* Heading */}
      <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text mb-6">
        Import Excel Model
      </h1>

      {/* Stepper */}
      <div className="mb-6">
        <ImportStepper currentStep={currentStep} />
      </div>

      {/* Error banner */}
      {streamError && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {streamError}
        </div>
      )}

      {/* Upload drop zone (before streaming starts) */}
      {!streaming && !uploading && (
        <VACard className="p-6">
          <p className="text-va-text2 mb-4">
            Upload an existing .xlsx financial model. The AI agent will classify
            sheets, map line items, and ask clarifying questions in a chat
            interface.
          </p>
          <div
            onDrop={onDrop}
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            className={`rounded-va-lg border-2 border-dashed p-12 text-center transition ${
              dragOver
                ? "border-va-blue bg-va-blue/10"
                : "border-va-border bg-va-panel/50"
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx"
              className="sr-only"
              aria-label="Select Excel file"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUpload(f);
              }}
            />
            <p className="text-va-text2 mb-2">
              Drop your file here or click to browse
            </p>
            <VAButton
              type="button"
              variant="secondary"
              onClick={() => fileInputRef.current?.click()}
            >
              Select .xlsx file
            </VAButton>
          </div>
        </VACard>
      )}

      {/* Uploading spinner */}
      {uploading && (
        <VACard className="flex items-center justify-center p-12">
          <VASpinner label="Uploading and parsing..." />
        </VACard>
      )}

      {/* Chat thread (during/after streaming) */}
      {streaming && !uploading && (
        <div className="space-y-4">
          {/* Mapping preview bar */}
          {mappingPreviewData && currentStep !== "upload" && !isComplete && (
            <VACard className="px-4 py-3">
              <MappingPreview mapping={mappingPreviewData} />
            </VACard>
          )}

          {/* Chat thread with optional inline QuestionCard */}
          <VACard className="h-[28rem] p-0">
            <ChatThread messages={messages}>
              {isPaused && pendingQuestion && (
                <QuestionCard
                  question={pendingQuestion}
                  onAnswer={handleAnswer}
                  disabled={answering}
                />
              )}
            </ChatThread>
          </VACard>

          {/* Review panel (when stream is complete) */}
          {isComplete && reviewMapping && (
            <ReviewPanel
              mapping={reviewMapping}
              onCreateDraft={handleCreateDraft}
              loading={draftLoading}
            />
          )}
        </div>
      )}
    </main>
  );
}
