"use client";

import { api, type AFSFramework } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VAInput,
  VASpinner,
  VABadge,
  useToast,
} from "@/components/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function CustomFrameworkPage() {
  const router = useRouter();
  const { toast } = useToast();
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Mode toggle
  const [mode, setMode] = useState<"ai" | "manual">("ai");

  // AI mode state
  const [description, setDescription] = useState("");
  const [jurisdiction, setJurisdiction] = useState("");
  const [entityType, setEntityType] = useState("");
  const [inferring, setInferring] = useState(false);
  const [preview, setPreview] = useState<
    (AFSFramework & { items_count: number }) | null
  >(null);

  // Manual mode state
  const [manualName, setManualName] = useState("");
  const [manualJurisdiction, setManualJurisdiction] = useState("");
  const [manualVersion, setManualVersion] = useState("1.0");
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      if (!cancelled) {
        setTenantId(ctx.tenantId);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router]);

  async function handleInfer() {
    if (!tenantId || !description.trim()) return;
    setInferring(true);
    try {
      const result = await api.afs.inferFramework(tenantId, {
        description: description.trim(),
        jurisdiction: jurisdiction.trim() || undefined,
        entity_type: entityType.trim() || undefined,
      });
      setPreview(result);
      toast.success(
        `Framework "${result.name}" generated with ${result.items_count} disclosure items`,
      );
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to infer framework",
      );
    } finally {
      setInferring(false);
    }
  }

  async function handleManualCreate() {
    if (!tenantId || !manualName.trim()) return;
    setCreating(true);
    try {
      const result = await api.afs.createFramework(tenantId, {
        name: manualName.trim(),
        standard: "custom",
        version: manualVersion,
        jurisdiction: manualJurisdiction.trim() || null,
      });
      toast.success(`Framework "${result.name}" created`);
      router.push("/afs");
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to create framework",
      );
    } finally {
      setCreating(false);
    }
  }

  if (loading) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="flex justify-center py-16">
          <VASpinner />
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Create Custom Framework
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Define a custom accounting framework using AI or build one manually.
          </p>
        </div>
        <Link href="/afs">
          <VAButton variant="secondary">Back to AFS</VAButton>
        </Link>
      </div>

      {/* Mode toggle */}
      <div className="mb-6 flex gap-2">
        <VAButton
          variant={mode === "ai" ? "primary" : "secondary"}
          onClick={() => setMode("ai")}
        >
          AI-Assisted
        </VAButton>
        <VAButton
          variant={mode === "manual" ? "primary" : "secondary"}
          onClick={() => setMode("manual")}
        >
          Manual
        </VAButton>
      </div>

      {/* AI mode */}
      {mode === "ai" && (
        <VACard className="p-6">
          <h2 className="text-lg font-semibold text-va-text">
            AI Framework Inference
          </h2>
          <p className="mt-1 text-sm text-va-text2">
            Describe your entity&apos;s reporting requirements and we&apos;ll
            generate a complete disclosure framework with appropriate standard
            references.
          </p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                Description
              </label>
              <textarea
                className="w-full rounded-va-sm border border-va-border bg-va-surface px-3 py-2 text-sm text-va-text placeholder:text-va-muted focus:border-va-blue focus:outline-none focus:ring-1 focus:ring-va-blue"
                rows={4}
                placeholder="e.g. South African private company using IFRS for SMEs with mining-specific disclosures and BEE reporting requirements"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Jurisdiction (optional)
                </label>
                <VAInput
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                  placeholder="e.g. South Africa"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Entity Type (optional)
                </label>
                <VAInput
                  value={entityType}
                  onChange={(e) => setEntityType(e.target.value)}
                  placeholder="e.g. Private company, Listed entity"
                />
              </div>
            </div>

            <div className="flex justify-end">
              <VAButton
                variant="primary"
                disabled={inferring || !description.trim()}
                onClick={handleInfer}
              >
                {inferring ? "Generating..." : "Generate Framework"}
              </VAButton>
            </div>
          </div>

          {/* AI result preview */}
          {preview && (
            <div className="mt-6 border-t border-va-border pt-4">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold text-va-text">
                  Generated: {preview.name}
                </h3>
                <VABadge variant="success">
                  {preview.items_count} disclosure items
                </VABadge>
              </div>

              {/* Show disclosure schema sections if available */}
              {preview.disclosure_schema_json && (
                <div className="mt-3">
                  <h4 className="text-xs font-medium uppercase text-va-muted">
                    Sections
                  </h4>
                  <div className="mt-2 space-y-1">
                    {(
                      (preview.disclosure_schema_json as Record<string, unknown> & { sections?: unknown[] })
                        ?.sections ?? []
                    ).map((section: unknown, i: number) => {
                      const s = section as {
                        type?: string;
                        title?: string;
                        reference?: string;
                      };
                      return (
                        <div
                          key={i}
                          className="flex items-center gap-2 rounded-va-xs bg-va-surface px-3 py-1.5 text-sm"
                        >
                          <VABadge
                            variant={
                              s.type === "statement"
                                ? "violet"
                                : s.type === "accounting_policy"
                                  ? "warning"
                                  : "default"
                            }
                          >
                            {s.type}
                          </VABadge>
                          <span className="text-va-text">{s.title}</span>
                          {s.reference && (
                            <span className="text-xs text-va-muted">
                              ({s.reference})
                            </span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="mt-4 flex justify-end">
                <VAButton variant="primary" onClick={() => router.push("/afs")}>
                  Done — Back to AFS
                </VAButton>
              </div>
            </div>
          )}
        </VACard>
      )}

      {/* Manual mode */}
      {mode === "manual" && (
        <VACard className="p-6">
          <h2 className="text-lg font-semibold text-va-text">
            Manual Framework
          </h2>
          <p className="mt-1 text-sm text-va-text2">
            Create a custom framework manually. You can add disclosure items
            after creating the framework.
          </p>

          <div className="mt-4 space-y-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-va-text">
                Framework Name
              </label>
              <VAInput
                value={manualName}
                onChange={(e) => setManualName(e.target.value)}
                placeholder="e.g. Custom IFRS for Mining (SA)"
                required
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Jurisdiction (optional)
                </label>
                <VAInput
                  value={manualJurisdiction}
                  onChange={(e) => setManualJurisdiction(e.target.value)}
                  placeholder="e.g. South Africa"
                />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">
                  Version
                </label>
                <VAInput
                  value={manualVersion}
                  onChange={(e) => setManualVersion(e.target.value)}
                  placeholder="1.0"
                />
              </div>
            </div>

            <div className="flex justify-end">
              <VAButton
                variant="primary"
                disabled={creating || !manualName.trim()}
                onClick={handleManualCreate}
              >
                {creating ? "Creating..." : "Create Framework"}
              </VAButton>
            </div>
          </div>
        </VACard>
      )}
    </main>
  );
}
