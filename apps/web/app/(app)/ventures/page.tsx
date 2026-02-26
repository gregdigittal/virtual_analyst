"use client";

import { VAButton, VACard, VAInput } from "@/components/ui";
import { api } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function VenturesPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | undefined>(undefined);
  const [ventureId, setVentureId] = useState<string | null>(null);
  const [questionPlan, setQuestionPlan] = useState<Record<string, unknown>[]>([]);
  const [form, setForm] = useState({ template_id: "", entity_name: "" });
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draftId, setDraftId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      setUserId(ctx.userId);
    })();
  }, [router]);

  async function handleCreate() {
    if (!tenantId || !form.template_id) return;
    setError(null);
    try {
      const res = await api.ventures.create(tenantId, {
        template_id: form.template_id,
        entity_name: form.entity_name,
      });
      setVentureId(res.venture_id);
      setQuestionPlan(res.question_plan ?? []);
      setAnswers({});
      setDraftId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSaveAnswers() {
    if (!tenantId || !ventureId) return;
    setError(null);
    try {
      await api.ventures.submitAnswers(tenantId, ventureId, answers);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleGenerateDraft() {
    if (!tenantId || !ventureId) return;
    setError(null);
    try {
      const res = await api.ventures.generateDraft(tenantId, userId, ventureId);
      setDraftId(res.draft_session_id);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Ventures
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          Create a venture draft from a questionnaire template.
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
        <h2 className="text-lg font-medium text-va-text">New venture</h2>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          <VAInput
            placeholder="Template ID"
            value={form.template_id}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, template_id: e.target.value }))
            }
          />
          <VAInput
            placeholder="Entity name"
            value={form.entity_name}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, entity_name: e.target.value }))
            }
          />
        </div>
        <VAButton className="mt-3" onClick={handleCreate}>
          Create venture
        </VAButton>
      </VACard>

      {ventureId && (
        <div className="mt-6 space-y-4">
          <VACard className="p-5">
            <h2 className="text-lg font-medium text-va-text">Questionnaire</h2>
            {questionPlan.length === 0 ? (
              <p className="mt-2 text-sm text-va-text2">
                No question plan provided for this template.
              </p>
            ) : (
              <div className="mt-4 space-y-5">
                {questionPlan.map((section, sIdx) => {
                  const sectionName = String((section as Record<string, unknown>).section ?? `Section ${sIdx + 1}`);
                  const questions = Array.isArray((section as Record<string, unknown>).questions)
                    ? ((section as Record<string, unknown>).questions as string[])
                    : [];
                  return (
                    <div key={sIdx}>
                      <p className="mb-2 text-sm font-medium text-va-text">{sectionName}</p>
                      {questions.length > 0 ? (
                        <div className="space-y-2">
                          {questions.map((q, qIdx) => {
                            const key = `${sIdx}-${qIdx}`;
                            return (
                              <div key={key}>
                                <label className="mb-1 block text-xs text-va-text2">{q}</label>
                                <VAInput
                                  placeholder="Your answer…"
                                  value={answers[key] ?? ""}
                                  onChange={(e) =>
                                    setAnswers((prev) => ({ ...prev, [key]: e.target.value }))
                                  }
                                />
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <VAInput
                          placeholder={`Answer for ${sectionName}…`}
                          value={answers[String(sIdx)] ?? ""}
                          onChange={(e) =>
                            setAnswers((prev) => ({ ...prev, [String(sIdx)]: e.target.value }))
                          }
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            <div className="mt-4 flex flex-wrap gap-2">
              <VAButton variant="secondary" onClick={handleSaveAnswers}>
                Save answers
              </VAButton>
              <VAButton onClick={handleGenerateDraft}>
                Generate draft
              </VAButton>
            </div>
          </VACard>
        </div>
      )}

      {draftId && (
        <VACard className="mt-6 p-5">
          <h2 className="text-lg font-medium text-va-text">Draft created</h2>
          <p className="mt-2 text-sm text-va-text2">
            Draft session: <span className="text-va-text">{draftId}</span>
          </p>
        </VACard>
      )}
    </main>
  );
}
