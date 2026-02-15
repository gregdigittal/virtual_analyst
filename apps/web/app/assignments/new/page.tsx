"use client";

import { api, type WorkflowTemplate } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import { VACard, VAButton, VAInput } from "@/components/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function NewAssignmentPage() {
  const router = useRouter();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [userId, setUserId] = useState<string | null>(null);
  const [templates, setTemplates] = useState<WorkflowTemplate[]>([]);
  const [entityType, setEntityType] = useState("draft");
  const [entityId, setEntityId] = useState("");
  const [assigneeUserId, setAssigneeUserId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [deadline, setDeadline] = useState("");
  const [workflowInstanceId, setWorkflowInstanceId] = useState("");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      try {
        const res = await api.workflows.listTemplates(ctx.tenantId);
        if (!cancelled) setTemplates(res.templates);
      } catch {
        if (!cancelled) setTemplates([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!tenantId || !userId) return;
    if (!entityId.trim()) {
      setError("Entity ID is required");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const deadlineIso = deadline.trim()
        ? new Date(deadline.trim()).toISOString()
        : null;
      await api.assignments.create(tenantId, userId, {
        entity_type: entityType,
        entity_id: entityId.trim(),
        assignee_user_id: assigneeUserId.trim() || null,
        instructions: instructions.trim() || null,
        deadline: deadlineIso,
        workflow_instance_id: workflowInstanceId.trim() || null,
      });
      router.push("/inbox");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  }

  if (!tenantId && !creating) return null;

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-4">
        <Link href="/inbox" className="text-sm text-va-blue hover:underline">
          ← Back to inbox
        </Link>
      </div>
      <h1 className="mb-6 font-brand text-2xl font-semibold tracking-tight text-va-text">
        New assignment
      </h1>

      {error && (
        <div
          className="mb-4 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger"
          role="alert"
        >
          {error}
        </div>
      )}

      <VACard className="p-6">
        <form onSubmit={handleCreate} className="space-y-4">
          <div>
            <label htmlFor="entity_type" className="mb-1 block text-sm font-medium text-va-text2">
              Entity type
            </label>
            <select
              id="entity_type"
              value={entityType}
              onChange={(e) => setEntityType(e.target.value)}
              className="w-full rounded-va-xs border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
            >
              <option value="draft">Draft</option>
              <option value="baseline">Baseline</option>
              <option value="run">Run</option>
            </select>
          </div>
          <div>
            <label htmlFor="entity_id" className="mb-1 block text-sm font-medium text-va-text2">
              Entity ID <span className="text-va-danger">*</span>
            </label>
            <VAInput
              id="entity_id"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="e.g. draft session or baseline ID"
              required
              className="w-full"
            />
          </div>
          <div>
            <label htmlFor="assignee" className="mb-1 block text-sm font-medium text-va-text2">
              Assignee (leave empty for team pool)
            </label>
            <VAInput
              id="assignee"
              value={assigneeUserId}
              onChange={(e) => setAssigneeUserId(e.target.value)}
              placeholder="User ID or leave blank for pool"
              className="w-full font-mono text-sm"
            />
          </div>
          <div>
            <label htmlFor="instructions" className="mb-1 block text-sm font-medium text-va-text2">
              Instructions
            </label>
            <textarea
              id="instructions"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={3}
              className="w-full rounded-va-xs border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-text2/70 focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
              placeholder="Task instructions for the assignee"
            />
          </div>
          <div>
            <label htmlFor="deadline" className="mb-1 block text-sm font-medium text-va-text2">
              Deadline (optional)
            </label>
            <VAInput
              id="deadline"
              type="datetime-local"
              value={deadline}
              onChange={(e) => setDeadline(e.target.value)}
              className="w-full"
            />
          </div>
          <div>
            <label htmlFor="workflow_instance" className="mb-1 block text-sm font-medium text-va-text2">
              Workflow instance ID (optional)
            </label>
            <VAInput
              id="workflow_instance"
              value={workflowInstanceId}
              onChange={(e) => setWorkflowInstanceId(e.target.value)}
              placeholder="wf_..."
              className="w-full font-mono text-sm"
            />
          </div>
          <div className="flex gap-2 pt-2">
            <VAButton type="submit" disabled={creating}>
              {creating ? "Creating…" : "Create assignment"}
            </VAButton>
            <Link href="/inbox">
              <VAButton type="button" variant="secondary" disabled={creating}>
                Cancel
              </VAButton>
            </Link>
          </div>
        </form>
      </VACard>

      {templates.length > 0 && (
        <VACard className="mt-6 p-6">
          <h2 className="text-sm font-medium text-va-text2">Workflow templates</h2>
          <p className="mt-1 text-sm text-va-text2">
            Create a workflow instance first, then attach its ID above. Available templates:
          </p>
          <ul className="mt-2 list-inside list-disc text-sm text-va-text">
            {templates.map((t) => (
              <li key={t.template_id}>
                <span className="font-medium">{t.name}</span>
                {t.description && ` — ${t.description}`}
              </li>
            ))}
          </ul>
        </VACard>
      )}
    </div>
  );
}
