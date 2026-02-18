"use client";

import { api, ApiError } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VAButton, VACard } from "@/components/ui";
import { Nav } from "@/components/nav";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

type Step = 1 | 2 | 3 | 4;

interface SheetClassification {
  sheet_name: string;
  classification: string;
  role?: string;
  confidence?: string;
  is_financial_core?: boolean;
}

interface ClassificationResponse {
  sheets?: SheetClassification[];
  model_summary?: Record<string, unknown>;
}

export default function ExcelImportPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>(1);
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [ingestionId, setIngestionId] = useState<string | null>(null);
  const [filename, setFilename] = useState<string>("");
  const [sheetCount, setSheetCount] = useState<number | null>(null);
  const [classification, setClassification] = useState<ClassificationResponse | null>(null);
  const [mapping, setMapping] = useState<Record<string, unknown> | null>(null);
  const [unmappedItems, setUnmappedItems] = useState<unknown[]>([]);
  const [questions, setQuestions] = useState<unknown[]>([]);
  const [answers, setAnswers] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) return;
      api.setAccessToken(ctx.accessToken);
      if (!cancelled) {
        setTenantId(ctx.tenantId);
        setUserId(ctx.userId);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleUpload = useCallback(
    async (file: File) => {
      if (!tenantId || !file.name.toLowerCase().endsWith(".xlsx")) {
        setError("Please select a .xlsx file.");
        return;
      }
      setError(null);
      setLoading(true);
      try {
        const res = await api.excelIngestion.upload(tenantId, userId ?? undefined, file);
        setIngestionId(res.ingestion_id);
        setFilename(file.name);
        setSheetCount(res.sheet_count ?? null);
        setClassification({
          sheets: (res.classification?.sheets as SheetClassification[]) ?? [],
          model_summary: (res.model_summary as Record<string, unknown>) ?? {},
        });
        setStep(2);
      } catch (e) {
        setError(e instanceof ApiError ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    [tenantId, userId]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) handleUpload(file);
    },
    [handleUpload]
  );
  const onDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);
  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  }, []);

  const onAnalyze = useCallback(async () => {
    if (!tenantId || !ingestionId) return;
    setError(null);
    setLoading(true);
    try {
      const res = await api.excelIngestion.analyze(tenantId, ingestionId);
      setQuestions((res.questions as unknown[]) ?? []);
      setStep(3);
      const detail = await api.excelIngestion.get(tenantId, ingestionId);
      setMapping(detail.mapping ?? null);
      setUnmappedItems(detail.unmapped_items ?? []);
      setQuestions(detail.questions ?? []);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, ingestionId]);

  const onSubmitAnswers = useCallback(async () => {
    if (!tenantId || !ingestionId) return;
    const answerList = Object.entries(answers)
      .filter(([, v]) => v.trim())
      .map(([k, v]) => ({ question_index: Number(k), answer: v }));
    if (answerList.length === 0) {
      setStep(4);
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await api.excelIngestion.answer(tenantId, ingestionId, answerList);
      setMapping(res.mapping ?? null);
      setQuestions((res.questions as unknown[]) ?? []);
      setUnmappedItems((res.mapping?.unmapped_items as unknown[]) ?? []);
      setStep(4);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, ingestionId, answers]);

  const onCreateDraft = useCallback(async () => {
    if (!tenantId || !ingestionId) return;
    setError(null);
    setLoading(true);
    try {
      const res = await api.excelIngestion.createDraft(tenantId, userId ?? undefined, ingestionId);
      router.push(`/drafts/${res.draft_session_id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [tenantId, userId, ingestionId, router]);

  if (!tenantId) return null;

  return (
    <div className="min-h-screen bg-va-midnight">
      <Nav />
      <main className="mx-auto max-w-4xl px-4 py-8">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text mb-6">
          Import Excel Model
        </h1>

        <div className="mb-6 flex items-center gap-2 text-sm text-va-text2">
          <StepIndicator n={1} current={step} label="Upload" />
          <span className="text-va-border">→</span>
          <StepIndicator n={2} current={step} label="Classification" />
          <span className="text-va-border">→</span>
          <StepIndicator n={3} current={step} label="Mapping" />
          <span className="text-va-border">→</span>
          <StepIndicator n={4} current={step} label="Create Draft" />
        </div>

        {error && (
          <div
            className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
            role="alert"
          >
            {error}
          </div>
        )}

        {/* Step 1: Upload */}
        {step === 1 && (
          <VACard className="p-6">
            <p className="text-va-text2 mb-4">Upload an existing .xlsx financial model. Max 10MB.</p>
            <div
              onDrop={onDrop}
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              className={`rounded-va-lg border-2 border-dashed p-12 text-center transition ${
                dragOver ? "border-va-blue bg-va-blue/10" : "border-va-border bg-va-panel/50"
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
              <p className="text-va-text2 mb-2">Drop your file here or click to browse</p>
              <VAButton
                type="button"
                variant="secondary"
                onClick={() => fileInputRef.current?.click()}
              >
                Select .xlsx file
              </VAButton>
            </div>
            {loading && (
              <p className="mt-4 text-sm text-va-text2">Parsing and classifying…</p>
            )}
          </VACard>
        )}

        {/* Step 2: Review Classification */}
        {step === 2 && (
          <VACard className="p-6">
            <h2 className="font-semibold text-va-text mb-2">Review classification</h2>
            <p className="text-sm text-va-text2 mb-4">
              {filename} — {sheetCount ?? 0} sheets detected.
            </p>
            {classification?.model_summary && (
              <div className="mb-4 rounded-va-xs bg-va-muted/20 p-3 text-sm">
                <p className="text-va-text">
                  Entity: {String(classification.model_summary.entity_name ?? "—")} · Industry:{" "}
                  {String(classification.model_summary.industry ?? "—")} · Currency:{" "}
                  {String(classification.model_summary.currency_guess ?? "—")}
                </p>
              </div>
            )}
            <ul className="space-y-1 mb-6">
              {(classification?.sheets ?? []).map((s) => (
                <li key={s.sheet_name} className="flex items-center gap-2 text-sm">
                  <span className="font-medium text-va-text w-48 truncate" title={s.sheet_name}>
                    {s.sheet_name}
                  </span>
                  <span className="rounded-va-xs bg-va-muted/30 px-2 py-0.5 text-va-text2">
                    {s.classification}
                  </span>
                  {s.is_financial_core && (
                    <span className="text-va-blue text-xs">core</span>
                  )}
                </li>
              ))}
            </ul>
            <VAButton variant="primary" onClick={onAnalyze} disabled={loading}>
              {loading ? "Analyzing…" : "Analyze model"}
            </VAButton>
          </VACard>
        )}

        {/* Step 3: Review Mapping */}
        {step === 3 && (
          <VACard className="p-6">
            <h2 className="font-semibold text-va-text mb-4">Review mapping</h2>
            {mapping?.revenue_streams && Array.isArray(mapping.revenue_streams) && (
              <section className="mb-6">
                <h3 className="text-sm font-medium text-va-text2 mb-2">Revenue streams</h3>
                <ul className="list-disc pl-5 text-sm text-va-text">
                  {(mapping.revenue_streams as Record<string, unknown>[]).map((r, i) => (
                    <li key={i}>
                      {String(r.label ?? r.source_row_label ?? "—")} ({String(r.stream_type ?? "—")})
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {mapping?.cost_items && Array.isArray(mapping.cost_items) && (
              <section className="mb-6">
                <h3 className="text-sm font-medium text-va-text2 mb-2">Cost items</h3>
                <ul className="list-disc pl-5 text-sm text-va-text">
                  {(mapping.cost_items as Record<string, unknown>[]).map((c, i) => (
                    <li key={i}>
                      {String(c.label ?? "—")} ({String(c.category ?? "—")})
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {unmappedItems.length > 0 && (
              <section className="mb-6 rounded-va-xs border border-amber-500/50 bg-amber-500/10 p-3">
                <h3 className="text-sm font-medium text-amber-700 dark:text-amber-400 mb-2">Unmapped items</h3>
                <ul className="list-disc pl-5 text-sm text-va-text">
                  {unmappedItems.map((u, i) => (
                    <li key={i}>
                      {typeof u === "object" && u !== null && "label" in u
                        ? String((u as Record<string, unknown>).label)
                        : String(u)}
                    </li>
                  ))}
                </ul>
              </section>
            )}
            {questions.length > 0 && (
              <section className="mb-6">
                <h3 className="text-sm font-medium text-va-text2 mb-2">Questions</h3>
                <div className="space-y-3">
                  {(questions as Record<string, unknown>[]).map((q, i) => (
                    <div key={i}>
                      <p className="text-sm text-va-text mb-1">{String(q.question)}</p>
                      <input
                        type="text"
                        className="w-full rounded-va-xs border border-va-border bg-va-midnight px-2 py-1 text-va-text text-sm"
                        placeholder="Your answer"
                        value={answers[i] ?? ""}
                        onChange={(e) => setAnswers((prev) => ({ ...prev, [i]: e.target.value }))}
                      />
                    </div>
                  ))}
                </div>
                <div className="mt-3 flex gap-2">
                  <VAButton variant="secondary" onClick={onSubmitAnswers} disabled={loading}>
                    {loading ? "Updating…" : "Submit answers & continue"}
                  </VAButton>
                  <VAButton variant="secondary" onClick={() => setStep(4)}>
                    Skip to create draft
                  </VAButton>
                </div>
              </section>
            )}
            <div className="mt-4">
              <VAButton variant="primary" onClick={() => setStep(4)}>
                Continue to create draft
              </VAButton>
            </div>
          </VACard>
        )}

        {/* Step 4: Create Draft */}
        {step === 4 && (
          <VACard className="p-6">
            <h2 className="font-semibold text-va-text mb-2">Create draft</h2>
            <p className="text-sm text-va-text2 mb-4">
              A draft session will be created with the mapped assumptions. You can refine it in the draft
              workspace and then commit to a baseline.
            </p>
            <VAButton variant="primary" onClick={onCreateDraft} disabled={loading}>
              {loading ? "Creating…" : "Create draft"}
            </VAButton>
          </VACard>
        )}
      </main>
    </div>
  );
}

function StepIndicator({
  n,
  current,
  label,
}: {
  n: Step;
  current: Step;
  label: string;
}) {
  const active = current === n;
  const done = current > n;
  return (
    <span
      className={
        active ? "font-medium text-va-blue" : done ? "text-va-text2" : "text-va-text2"
      }
    >
      {label}
    </span>
  );
}
