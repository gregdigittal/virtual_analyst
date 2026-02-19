"use client";

import { Nav } from "@/components/nav";
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
  const [answersJson, setAnswersJson] = useState("{}");
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
      setDraftId(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleSaveAnswers() {
    if (!tenantId || !ventureId) return;
    setError(null);
    try {
      const answers = JSON.parse(answersJson || "{}");
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
    <div className="min-h-screen bg-va-midnight">
      <Nav />
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
              <h2 className="text-lg font-medium text-va-text">
                Questionnaire
              </h2>
              {questionPlan.length === 0 ? (
                <p className="mt-2 text-sm text-va-text2">
                  No question plan provided for this template.
                </p>
              ) : (
                <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-va-text2">
                  {questionPlan.map((section, idx) => (
                    <li key={idx}>
                      {String((section as Record<string, unknown>).section ?? "Section")}
                    </li>
                  ))}
                </ul>
              )}
            </VACard>

            <VACard className="p-5">
              <h2 className="text-lg font-medium text-va-text">
                Answers (JSON)
              </h2>
              <textarea
                className="mt-3 min-h-[140px] w-full rounded-va-xs border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text"
                value={answersJson}
                onChange={(e) => setAnswersJson(e.target.value)}
              />
              <div className="mt-3 flex flex-wrap gap-2">
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
    </div>
  );
}
