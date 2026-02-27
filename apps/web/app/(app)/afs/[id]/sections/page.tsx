"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  type AFSSection,
  type AFSEngagement,
  type AFSValidationResult,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VAInput,
  VABadge,
  VASpinner,
  VAEmptyState,
  VABreadcrumb,
  useToast,
} from "@/components/ui";

const SECTION_TYPES = [
  { value: "note", label: "Note" },
  { value: "statement", label: "Statement" },
  { value: "directors_report", label: "Directors' Report" },
  { value: "accounting_policy", label: "Accounting Policy" },
];

export default function SectionEditorPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const engagementId = params.id as string;

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [engagement, setEngagement] = useState<AFSEngagement | null>(null);
  const [sections, setSections] = useState<AFSSection[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [drafting, setDrafting] = useState(false);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<AFSValidationResult | null>(null);
  const [mobileShowContent, setMobileShowContent] = useState(false);

  // New section form
  const [showNewForm, setShowNewForm] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newType, setNewType] = useState("note");
  const [newInstruction, setNewInstruction] = useState("");

  // Re-draft form
  const [feedbackText, setFeedbackText] = useState("");

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
        const [eng, secs] = await Promise.all([
          api.afs.getEngagement(ctx.tenantId, engagementId),
          api.afs.listSections(ctx.tenantId, engagementId),
        ]);
        if (!cancelled) {
          setEngagement(eng);
          setSections(secs.items ?? []);
          if ((secs.items ?? []).length > 0) {
            setSelectedId(secs.items[0].section_id);
          }
        }
      } catch {
        if (!cancelled) toast.error("Failed to load engagement");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [engagementId, router, toast]);

  const selectedSection = sections.find((s) => s.section_id === selectedId) || null;

  async function handleDraftNew() {
    if (!tenantId || !newTitle.trim() || !newInstruction.trim()) return;
    setDrafting(true);
    try {
      const section = await api.afs.draftSection(tenantId, engagementId, {
        section_type: newType,
        title: newTitle,
        nl_instruction: newInstruction,
      });
      setSections((prev) => [...prev, section]);
      setSelectedId(section.section_id);
      setShowNewForm(false);
      setNewTitle("");
      setNewInstruction("");
      toast.success("Section drafted successfully");
    } catch {
      toast.error("Failed to draft section");
    } finally {
      setDrafting(false);
    }
  }

  async function handleRedraft() {
    if (!tenantId || !selectedSection || !feedbackText.trim()) return;
    setDrafting(true);
    try {
      const updated = await api.afs.updateSection(tenantId, engagementId, selectedSection.section_id, {
        nl_instruction: feedbackText,
      });
      setSections((prev) => prev.map((s) => (s.section_id === updated.section_id ? updated : s)));
      setFeedbackText("");
      toast.success("Section re-drafted");
    } catch {
      toast.error("Failed to re-draft section");
    } finally {
      setDrafting(false);
    }
  }

  async function handleLock(sectionId: string) {
    if (!tenantId) return;
    try {
      const updated = await api.afs.lockSection(tenantId, engagementId, sectionId);
      setSections((prev) => prev.map((s) => (s.section_id === updated.section_id ? updated : s)));
      toast.success("Section locked");
    } catch {
      toast.error("Failed to lock section");
    }
  }

  async function handleUnlock(sectionId: string) {
    if (!tenantId) return;
    try {
      const updated = await api.afs.unlockSection(tenantId, engagementId, sectionId);
      setSections((prev) => prev.map((s) => (s.section_id === updated.section_id ? updated : s)));
      toast.success("Section unlocked");
    } catch {
      toast.error("Failed to unlock section");
    }
  }

  async function handleValidate() {
    if (!tenantId) return;
    setValidating(true);
    try {
      const result = await api.afs.validateSections(tenantId, engagementId);
      setValidationResult(result);
      if (result.compliant) {
        toast.success("All disclosures are compliant");
      } else {
        toast.error(`${result.missing_disclosures.length} missing disclosure(s) found`);
      }
    } catch {
      toast.error("Validation failed");
    } finally {
      setValidating(false);
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <VASpinner />
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="flex flex-col gap-2 border-b border-va-border px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-6">
        <VABreadcrumb items={[
          { label: "AFS", href: "/afs" },
          { label: engagement?.entity_name ?? "…", href: `/afs/${engagementId}/setup` },
          { label: "Sections" },
        ]} />
        <div className="flex flex-wrap gap-2">
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/tax`)}>
            Tax
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/review`)}>
            Review
          </VAButton>
          <VAButton variant="secondary" className="hidden sm:inline-flex" onClick={() => router.push(`/afs/${engagementId}/consolidation`)}>
            Consolidation
          </VAButton>
          <VAButton variant="secondary" className="hidden sm:inline-flex" onClick={() => router.push(`/afs/${engagementId}/output`)}>
            Output
          </VAButton>
          <VAButton variant="secondary" className="hidden sm:inline-flex" onClick={() => router.push(`/afs/${engagementId}/analytics`)}>
            Analytics
          </VAButton>
          <VAButton variant="secondary" onClick={handleValidate} disabled={validating || sections.length === 0}>
            {validating ? "Validating..." : "Validate"}
          </VAButton>
          <VAButton variant="primary" onClick={() => setShowNewForm(true)}>
            + New
          </VAButton>
        </div>
      </div>

      {/* Split panel */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left: Section list */}
        <div className={`w-full flex-shrink-0 overflow-y-auto border-r border-va-border bg-va-surface p-4 md:w-80 ${mobileShowContent ? "hidden md:block" : ""}`}>
          {sections.length === 0 ? (
            <VAEmptyState
              icon="file-text"
              title="No sections yet"
              description="Draft your first section using AI"
              actionLabel="New Section"
              onAction={() => { setShowNewForm(true); setMobileShowContent(true); }}
            />
          ) : (
            <div className="space-y-2">
              {sections.map((s) => (
                <button
                  key={s.section_id}
                  onClick={() => { setSelectedId(s.section_id); setFeedbackText(""); setMobileShowContent(true); }}
                  className={`w-full rounded-va-sm border p-3 text-left transition-colors ${
                    selectedId === s.section_id
                      ? "border-va-blue bg-va-blue/10"
                      : "border-va-border bg-va-panel hover:border-va-text2 cursor-pointer"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-va-text">{s.title}</span>
                    <div className="flex items-center gap-1">
                      {s.rolled_forward_from && (
                        <VABadge variant="violet">Carried Forward</VABadge>
                      )}
                      <VABadge variant={s.status === "locked" ? "success" : s.status === "reviewed" ? "violet" : "default"}>
                        {s.status}
                      </VABadge>
                    </div>
                  </div>
                  <span className="mt-1 block text-xs text-va-text2">
                    {s.section_type} · v{s.version}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Right: Content + feedback */}
        <div className={`flex flex-1 flex-col overflow-y-auto p-4 sm:p-6 ${!mobileShowContent ? "hidden md:flex" : ""}`}>
          {/* Mobile back button */}
          {mobileShowContent && (
            <button
              onClick={() => setMobileShowContent(false)}
              className="mb-3 inline-flex items-center gap-1 text-sm text-va-text2 hover:text-va-text md:hidden"
            >
              &larr; Back to sections
            </button>
          )}
          {showNewForm ? (
            <VACard className="mx-auto max-w-2xl p-6">
              <h2 className="text-lg font-semibold text-va-text">Draft New Section</h2>
              <div className="mt-4 space-y-4">
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Section Type</label>
                  <select
                    value={newType}
                    onChange={(e) => setNewType(e.target.value)}
                    className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text"
                  >
                    {SECTION_TYPES.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Title</label>
                  <VAInput
                    value={newTitle}
                    onChange={(e) => setNewTitle(e.target.value)}
                    placeholder="e.g. Revenue Recognition"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">Instruction (natural language)</label>
                  <textarea
                    value={newInstruction}
                    onChange={(e) => setNewInstruction(e.target.value)}
                    placeholder="Describe what this section should contain. E.g. 'Revenue increased 15% due to new mining contracts. We adopted IFRS 15 this year.'"
                    rows={5}
                    className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-muted"
                  />
                </div>
                <div className="flex justify-end gap-3">
                  <VAButton variant="secondary" onClick={() => setShowNewForm(false)}>Cancel</VAButton>
                  <VAButton variant="primary" onClick={handleDraftNew} disabled={drafting || !newTitle.trim() || !newInstruction.trim()}>
                    {drafting ? "Drafting with AI..." : "Generate Draft"}
                  </VAButton>
                </div>
              </div>
            </VACard>
          ) : selectedSection ? (
            <>
              {/* Section content */}
              <div className="mb-6">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-xl font-semibold text-va-text">{selectedSection.title}</h2>
                  <div className="flex gap-2">
                    {selectedSection.status === "locked" ? (
                      <VAButton variant="secondary" onClick={() => handleUnlock(selectedSection.section_id)}>
                        Unlock
                      </VAButton>
                    ) : (
                      <VAButton variant="primary" onClick={() => handleLock(selectedSection.section_id)}>
                        Lock Section
                      </VAButton>
                    )}
                  </div>
                </div>

                {selectedSection.content_json?.warnings && selectedSection.content_json.warnings.length > 0 && (
                  <div className="mb-4 rounded-va-sm border border-yellow-500/30 bg-yellow-500/10 p-3">
                    <p className="text-sm font-medium text-yellow-400">Warnings:</p>
                    <ul className="mt-1 list-disc pl-5 text-sm text-yellow-300/80">
                      {selectedSection.content_json.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <VACard className="p-6">
                  {selectedSection.content_json?.paragraphs?.map((p, i) => (
                    <div key={i} className="mb-4">
                      {p.type === "heading" ? (
                        <h3 className="text-lg font-semibold text-va-text">{p.content}</h3>
                      ) : p.type === "table" ? (
                        <div className="overflow-x-auto">
                          <pre className="whitespace-pre-wrap text-sm text-va-text2">{p.content}</pre>
                        </div>
                      ) : (
                        <p className="text-sm leading-relaxed text-va-text2">{p.content}</p>
                      )}
                    </div>
                  ))}
                </VACard>

                {selectedSection.content_json?.references && selectedSection.content_json.references.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {selectedSection.content_json.references.map((ref, i) => (
                      <VABadge key={i} variant="violet">{ref}</VABadge>
                    ))}
                  </div>
                )}

                <p className="mt-2 text-xs text-va-muted">
                  Version {selectedSection.version} · {selectedSection.section_type}
                </p>
              </div>

              {/* Feedback / re-draft */}
              {selectedSection.status !== "locked" && (
                <div className="border-t border-va-border pt-4">
                  <h3 className="mb-2 text-sm font-medium text-va-text">Provide Feedback (AI will re-draft)</h3>
                  <div className="flex gap-3">
                    <textarea
                      value={feedbackText}
                      onChange={(e) => setFeedbackText(e.target.value)}
                      placeholder="E.g. 'Add more detail about the lease modifications' or 'The revenue figure should be R1.2m not R1.5m'"
                      rows={3}
                      className="flex-1 rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-muted"
                    />
                    <VAButton
                      variant="primary"
                      onClick={handleRedraft}
                      disabled={drafting || !feedbackText.trim()}
                      className="self-end"
                    >
                      {drafting ? "Re-drafting..." : "Re-draft"}
                    </VAButton>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-va-muted">Select a section from the list or create a new one</p>
            </div>
          )}

          {/* Validation results */}
          {validationResult && (
            <div className="mt-6 border-t border-va-border pt-4">
              <h3 className="mb-3 text-sm font-semibold text-va-text">
                Disclosure Validation {validationResult.compliant ? "✓" : "!"}
              </h3>
              {validationResult.missing_disclosures.length > 0 && (
                <div className="space-y-2">
                  {validationResult.missing_disclosures.map((d, i) => (
                    <div key={i} className="rounded-va-sm border border-va-border bg-va-panel p-3">
                      <div className="flex items-center gap-2">
                        <VABadge variant={d.severity === "critical" ? "danger" : d.severity === "important" ? "warning" : "default"}>
                          {d.severity}
                        </VABadge>
                        <span className="text-sm font-medium text-va-text">{d.reference}</span>
                      </div>
                      <p className="mt-1 text-sm text-va-text2">{d.description}</p>
                    </div>
                  ))}
                </div>
              )}
              {validationResult.suggestions.length > 0 && (
                <div className="mt-3">
                  <p className="text-sm font-medium text-va-text">Suggestions:</p>
                  <ul className="mt-1 list-disc pl-5 text-sm text-va-text2">
                    {validationResult.suggestions.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
