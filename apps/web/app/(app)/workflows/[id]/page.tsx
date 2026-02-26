"use client";

import { api, type WorkflowInstance, type WorkflowTemplate, type WorkflowTemplateStage } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VASpinner } from "@/components/ui";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

function StageStepper({
  stages,
  currentStageIndex,
  status,
}: {
  stages: WorkflowTemplateStage[];
  currentStageIndex: number;
  status: string;
}) {
  return (
    <div className="space-y-3">
      {stages.map((stage, i) => {
        const isComplete = status === "completed" || i < currentStageIndex;
        const isCurrent = status === "active" && i === currentStageIndex;
        return (
          <div key={i} className="flex items-center gap-3">
            <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-medium ${
              isComplete ? "bg-green-600 text-white" :
              isCurrent ? "bg-va-blue text-white" :
              "border border-va-border text-va-text2"
            }`}>
              {isComplete ? "✓" : i + 1}
            </div>
            <div>
              <p className={`text-sm font-medium ${isCurrent ? "text-va-blue" : "text-va-text"}`}>
                {stage.name}
              </p>
              <p className="text-xs text-va-text2">
                Assignee: {stage.assignee_rule}
                {isCurrent && " — awaiting action"}
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function WorkflowDetailPage() {
  const params = useParams();
  const router = useRouter();
  const instanceId = params.id as string;
  const [instance, setInstance] = useState<WorkflowInstance | null>(null);
  const [template, setTemplate] = useState<WorkflowTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      try {
        const inst = await api.workflows.getInstance(ctx.tenantId, instanceId);
        if (cancelled) return;
        setInstance(inst);
        const tpl = await api.workflows.getTemplate(ctx.tenantId, inst.template_id);
        if (!cancelled) setTemplate(tpl);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [router, instanceId]);

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-6 flex items-center gap-4">
        <Link
          href="/workflows"
          className="text-sm text-va-text2 hover:text-va-text focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight rounded"
        >
          ← Workflows
        </Link>
      </div>
      {error && (
        <div className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger" role="alert">
          {error}
        </div>
      )}
      {loading ? (
        <VASpinner label="Loading workflow…" />
      ) : instance ? (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
              Workflow {instanceId}
            </h1>
            <span className={`rounded-full px-3 py-1 text-sm ${
              instance.status === "completed" ? "bg-green-900/40 text-green-300" :
              instance.status === "cancelled" ? "bg-red-900/40 text-red-300" :
              "bg-yellow-900/40 text-yellow-300"
            }`}>
              {instance.status}
            </span>
          </div>

          <VACard className="p-4">
            <dl className="grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-va-text2">Template</dt>
                <dd className="font-medium text-va-text">{template?.name ?? instance.template_id}</dd>
              </div>
              <div>
                <dt className="text-va-text2">Entity</dt>
                <dd className="font-medium text-va-text">{instance.entity_type}: {instance.entity_id}</dd>
              </div>
              <div>
                <dt className="text-va-text2">Current stage</dt>
                <dd className="font-medium text-va-text">
                  {template?.stages[instance.current_stage_index]?.name ?? `Stage ${instance.current_stage_index + 1}`}
                </dd>
              </div>
              <div>
                <dt className="text-va-text2">Created</dt>
                <dd className="font-medium text-va-text">
                  {instance.created_at ? new Date(instance.created_at).toLocaleDateString() : "—"}
                </dd>
              </div>
            </dl>
          </VACard>

          {template && (
            <VACard className="p-4">
              <h2 className="mb-4 font-brand text-lg font-medium text-va-text">Stage progress</h2>
              <StageStepper
                stages={template.stages}
                currentStageIndex={instance.current_stage_index}
                status={instance.status}
              />
            </VACard>
          )}
        </div>
      ) : (
        <p className="text-va-text2">Workflow instance not found.</p>
      )}
    </main>
  );
}
