"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  type AFSFramework,
  type AFSDisclosureItem,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VABadge,
  VASpinner,
  VAEmptyState,
  VABreadcrumb,
  VAInput,
  useToast,
} from "@/components/ui";

export default function FrameworkDetailPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const frameworkId = params.id as string;

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [framework, setFramework] = useState<AFSFramework | null>(null);
  const [checklist, setChecklist] = useState<AFSDisclosureItem[]>([]);
  const [loading, setLoading] = useState(true);

  // Add item form (custom frameworks only)
  const [showAddForm, setShowAddForm] = useState(false);
  const [newSection, setNewSection] = useState("");
  const [newReference, setNewReference] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newRequired, setNewRequired] = useState(true);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      if (!cancelled) setTenantId(ctx.tenantId);
      try {
        const [fw, cl] = await Promise.all([
          api.afs.getFramework(ctx.tenantId, frameworkId),
          api.afs.getChecklist(ctx.tenantId, frameworkId),
        ]);
        if (!cancelled) {
          setFramework(fw);
          setChecklist(cl.items ?? []);
        }
      } catch {
        if (!cancelled) toast.error("Failed to load framework");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [frameworkId, router, toast]);

  async function handleAddItem() {
    if (!tenantId || !newSection.trim() || !newDescription.trim()) return;
    setAdding(true);
    try {
      const item = await api.afs.addDisclosureItem(tenantId, frameworkId, {
        section: newSection.trim(),
        reference: newReference.trim() || undefined,
        description: newDescription.trim(),
        required: newRequired,
      });
      setChecklist((prev) => [...prev, item]);
      setShowAddForm(false);
      setNewSection("");
      setNewReference("");
      setNewDescription("");
      setNewRequired(true);
      toast.success("Disclosure item added");
    } catch {
      toast.error("Failed to add disclosure item");
    } finally {
      setAdding(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <VASpinner />
      </div>
    );
  }

  if (!framework) {
    return (
      <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
        <VAEmptyState
          icon="alert-circle"
          title="Framework not found"
          description="This framework does not exist or you don't have access."
          actionLabel="Back to AFS"
          onAction={() => router.push("/afs")}
        />
      </div>
    );
  }

  // Group checklist items by section
  const bySection = checklist.reduce<Record<string, AFSDisclosureItem[]>>(
    (acc, item) => {
      const key = item.section || "General";
      if (!acc[key]) acc[key] = [];
      acc[key].push(item);
      return acc;
    },
    {}
  );

  const sectionKeys = Object.keys(bySection).sort();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <VABreadcrumb
        items={[
          { label: "AFS", href: "/afs" },
          { label: "Frameworks", href: "/afs/frameworks" },
          { label: framework.name },
        ]}
      />

      {/* Framework header */}
      <div className="mt-6 flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold font-sora text-va-text">
            {framework.name}
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            {framework.version && `v${framework.version}`}
            {framework.jurisdiction && ` · ${framework.jurisdiction}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {framework.is_builtin ? (
            <VABadge variant="success">Built-in</VABadge>
          ) : (
            <VABadge variant="default">Custom</VABadge>
          )}
          <VABadge variant="default">{framework.standard.toUpperCase().replace("_", " ")}</VABadge>
        </div>
      </div>

      {/* Disclosure checklist */}
      <VACard className="mt-8 p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-va-text">
            Disclosure Checklist
            <span className="ml-2 text-sm font-normal text-va-text2">
              ({checklist.length} item{checklist.length !== 1 ? "s" : ""})
            </span>
          </h2>
          {!framework.is_builtin && (
            <VAButton
              variant="secondary"
              onClick={() => setShowAddForm((v) => !v)}
            >
              {showAddForm ? "Cancel" : "+ Add Item"}
            </VAButton>
          )}
        </div>

        {/* Add item form */}
        {showAddForm && !framework.is_builtin && (
          <div className="mt-4 rounded-va-sm border border-va-border bg-va-panel p-4">
            <h3 className="mb-3 text-sm font-medium text-va-text">New Disclosure Item</h3>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Section <span className="text-red-400">*</span>
                </label>
                <VAInput
                  value={newSection}
                  onChange={(e) => setNewSection(e.target.value)}
                  placeholder="e.g. Revenue"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Reference
                </label>
                <VAInput
                  value={newReference}
                  onChange={(e) => setNewReference(e.target.value)}
                  placeholder="e.g. IFRS 15.1"
                />
              </div>
              <div className="sm:col-span-2">
                <label className="mb-1 block text-xs font-medium text-va-text2">
                  Description <span className="text-red-400">*</span>
                </label>
                <VAInput
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Describe this disclosure requirement"
                />
              </div>
              <div className="flex items-center gap-2">
                <input
                  id="required-toggle"
                  type="checkbox"
                  checked={newRequired}
                  onChange={(e) => setNewRequired(e.target.checked)}
                  className="h-4 w-4 rounded border-va-border accent-va-blue"
                />
                <label
                  htmlFor="required-toggle"
                  className="text-sm text-va-text"
                >
                  Required disclosure
                </label>
              </div>
            </div>
            <div className="mt-3 flex justify-end gap-2">
              <VAButton
                variant="secondary"
                onClick={() => setShowAddForm(false)}
              >
                Cancel
              </VAButton>
              <VAButton
                variant="primary"
                onClick={handleAddItem}
                disabled={adding || !newSection.trim() || !newDescription.trim()}
              >
                {adding ? "Adding..." : "Add Item"}
              </VAButton>
            </div>
          </div>
        )}

        {/* Empty state */}
        {checklist.length === 0 && !showAddForm && (
          <VAEmptyState
            icon="list"
            title="No checklist items"
            description={
              framework.is_builtin
                ? "This built-in framework has no checklist items seeded yet."
                : "Add disclosure items to define this framework's requirements."
            }
            actionLabel={framework.is_builtin ? undefined : "+ Add Item"}
            onAction={
              framework.is_builtin ? undefined : () => setShowAddForm(true)
            }
          />
        )}

        {/* Checklist grouped by section */}
        {sectionKeys.length > 0 && (
          <div className="mt-4 space-y-6">
            {sectionKeys.map((section) => (
              <div key={section}>
                <h3 className="mb-2 text-sm font-semibold text-va-text2 uppercase tracking-wide">
                  {section}
                </h3>
                <div className="divide-y divide-va-border rounded-va-sm border border-va-border">
                  {bySection[section].map((item) => (
                    <div
                      key={item.item_id}
                      className="flex items-start justify-between px-4 py-3"
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm text-va-text">{item.description}</p>
                        {item.reference && (
                          <p className="mt-0.5 text-xs text-va-text2 font-mono">
                            {item.reference}
                          </p>
                        )}
                      </div>
                      <div className="ml-3 flex-shrink-0">
                        {item.required ? (
                          <VABadge variant="default">Required</VABadge>
                        ) : (
                          <VABadge variant="default">Optional</VABadge>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </VACard>

      {/* Statement templates preview (if any) */}
      {framework.statement_templates_json &&
        Object.keys(framework.statement_templates_json).length > 0 && (
          <VACard className="mt-6 p-6">
            <h2 className="text-lg font-semibold text-va-text">
              Statement Templates
            </h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              {Object.entries(framework.statement_templates_json).map(
                ([key, tmpl]) => {
                  const t = tmpl as { title?: string; line_items?: string[] };
                  return (
                    <div
                      key={key}
                      className="rounded-va-sm border border-va-border bg-va-panel p-4"
                    >
                      <p className="text-sm font-medium text-va-text">
                        {t.title ?? key}
                      </p>
                      {Array.isArray(t.line_items) &&
                        t.line_items.length > 0 && (
                          <ul className="mt-2 space-y-1">
                            {t.line_items.slice(0, 6).map((li) => (
                              <li
                                key={li}
                                className="text-xs text-va-text2"
                              >
                                • {li}
                              </li>
                            ))}
                            {t.line_items.length > 6 && (
                              <li className="text-xs text-va-text2">
                                +{t.line_items.length - 6} more
                              </li>
                            )}
                          </ul>
                        )}
                    </div>
                  );
                }
              )}
            </div>
          </VACard>
        )}

      <div className="mt-6 flex justify-start">
        <VAButton variant="secondary" onClick={() => router.push("/afs")}>
          ← Back to AFS
        </VAButton>
      </div>
    </div>
  );
}
