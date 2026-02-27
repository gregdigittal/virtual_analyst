"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  type AFSTaxComputation,
  type AFSTemporaryDifference,
  type AFSEngagement,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VAInput,
  VABadge,
  VASpinner,
  VAEmptyState,
  useToast,
} from "@/components/ui";

const JURISDICTIONS = [
  { value: "ZA", label: "South Africa" },
  { value: "US", label: "United States" },
  { value: "GB", label: "United Kingdom" },
  { value: "AU", label: "Australia" },
];

function safeParseFloat(value: string, fallback = 0): number {
  const n = parseFloat(value);
  return Number.isNaN(n) ? fallback : n;
}

export default function TaxComputationPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const engagementId = params.id as string;

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [engagement, setEngagement] = useState<AFSEngagement | null>(null);
  const [computations, setComputations] = useState<AFSTaxComputation[]>([]);
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);
  const [generatingNote, setGeneratingNote] = useState(false);
  const [addingDiff, setAddingDiff] = useState(false);

  // Create computation form
  const [jurisdiction, setJurisdiction] = useState("ZA");
  const [statutoryRate, setStatutoryRate] = useState("0.27");
  const [taxableIncome, setTaxableIncome] = useState("");
  const [adjustments, setAdjustments] = useState<{ description: string; amount: string }[]>([]);

  // Temporary difference form
  const [showDiffForm, setShowDiffForm] = useState(false);
  const [diffDescription, setDiffDescription] = useState("");
  const [diffCarrying, setDiffCarrying] = useState("");
  const [diffTaxBase, setDiffTaxBase] = useState("");
  const [diffType, setDiffType] = useState("asset");

  // Tax note
  const [noteInstruction, setNoteInstruction] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) { router.replace("/login"); return; }
      api.setAccessToken(ctx.accessToken);
      if (!cancelled) setTenantId(ctx.tenantId);
      try {
        const [eng, taxRes] = await Promise.all([
          api.afs.getEngagement(ctx.tenantId, engagementId),
          api.afs.listTaxComputations(ctx.tenantId, engagementId),
        ]);
        if (!cancelled) {
          setEngagement(eng);
          setComputations(taxRes.items ?? []);
        }
      } catch {
        if (!cancelled) toast.error("Failed to load engagement");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [engagementId, router, toast]);

  const selectedComputation = computations.length > 0 ? computations[0] : null;

  function addAdjustmentRow() {
    setAdjustments((prev) => [...prev, { description: "", amount: "" }]);
  }
  function removeAdjustmentRow(index: number) {
    setAdjustments((prev) => prev.filter((_, i) => i !== index));
  }
  function updateAdjustment(index: number, field: "description" | "amount", value: string) {
    setAdjustments((prev) => prev.map((a, i) => (i === index ? { ...a, [field]: value } : a)));
  }

  async function handleComputeTax() {
    if (!tenantId || !taxableIncome.trim()) return;
    setComputing(true);
    try {
      const body = {
        jurisdiction,
        statutory_rate: safeParseFloat(statutoryRate, 0.27),
        taxable_income: safeParseFloat(taxableIncome),
        adjustments: adjustments
          .filter((a) => a.description.trim() && a.amount.trim())
          .map((a) => ({ description: a.description, amount: safeParseFloat(a.amount) })),
      };
      const computation = await api.afs.computeTax(tenantId, engagementId, body);
      setComputations((prev) => [computation, ...prev]);
      toast.success("Tax computation created");
    } catch {
      toast.error("Failed to compute tax");
    } finally {
      setComputing(false);
    }
  }

  async function handleAddTemporaryDifference() {
    if (!tenantId || !selectedComputation || !diffDescription.trim() || !diffCarrying.trim() || !diffTaxBase.trim()) return;
    setAddingDiff(true);
    try {
      const diff = await api.afs.addTemporaryDifference(tenantId, engagementId, selectedComputation.computation_id, {
        description: diffDescription,
        carrying_amount: safeParseFloat(diffCarrying),
        tax_base: safeParseFloat(diffTaxBase),
        diff_type: diffType,
      });
      setComputations((prev) =>
        prev.map((c) =>
          c.computation_id === selectedComputation.computation_id
            ? { ...c, temporary_differences: [...(c.temporary_differences ?? []), diff] }
            : c,
        ),
      );
      setDiffDescription(""); setDiffCarrying(""); setDiffTaxBase(""); setDiffType("asset");
      setShowDiffForm(false);
      toast.success("Temporary difference added");
    } catch {
      toast.error("Failed to add temporary difference");
    } finally {
      setAddingDiff(false);
    }
  }

  async function handleGenerateTaxNote() {
    if (!tenantId || !selectedComputation) return;
    setGeneratingNote(true);
    try {
      const updated = await api.afs.generateTaxNote(
        tenantId, engagementId, selectedComputation.computation_id,
        noteInstruction.trim() ? { nl_instruction: noteInstruction } : undefined,
      );
      setComputations((prev) => prev.map((c) => (c.computation_id === updated.computation_id ? updated : c)));
      setNoteInstruction("");
      toast.success("Tax note generated");
    } catch {
      toast.error("Failed to generate tax note");
    } finally {
      setGeneratingNote(false);
    }
  }

  const fmtNum = (v: number) => v.toLocaleString();
  const fmtPct = (v: number) => (v * 100).toFixed(2) + "%";

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
      <div className="flex items-center justify-between border-b border-va-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => router.push(`/afs/${engagementId}/sections`)} className="text-va-text2 hover:text-va-text">
            &larr;
          </button>
          <h1 className="text-lg font-semibold text-va-text">
            {engagement?.entity_name} — Tax Computation
          </h1>
        </div>
        <div className="flex gap-2">
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/sections`)}>
            Sections
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/review`)}>
            Review
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/consolidation`)}>
            Consolidation
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/output`)}>
            Output
          </VAButton>
          <VAButton variant="secondary" onClick={() => router.push(`/afs/${engagementId}/analytics`)}>
            Analytics
          </VAButton>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {!selectedComputation ? (
          /* Creation Form */
          <VACard className="mx-auto max-w-2xl p-6">
            <h2 className="text-lg font-semibold text-va-text">Create Tax Computation</h2>
            <div className="mt-4 space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">Jurisdiction</label>
                <select
                  value={jurisdiction}
                  onChange={(e) => setJurisdiction(e.target.value)}
                  className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text"
                >
                  {JURISDICTIONS.map((j) => (
                    <option key={j.value} value={j.value}>{j.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">Statutory Rate</label>
                <VAInput type="number" step="0.01" value={statutoryRate} onChange={(e) => setStatutoryRate(e.target.value)} placeholder="0.27" />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-va-text">Taxable Income</label>
                <VAInput type="number" value={taxableIncome} onChange={(e) => setTaxableIncome(e.target.value)} placeholder="e.g. 1500000" />
              </div>

              {/* Adjustments */}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label className="text-sm font-medium text-va-text">Adjustments</label>
                  <VAButton variant="secondary" onClick={addAdjustmentRow}>+ Add Row</VAButton>
                </div>
                {adjustments.length === 0 && <p className="text-sm text-va-muted">No adjustments added</p>}
                <div className="space-y-2">
                  {adjustments.map((adj, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <VAInput value={adj.description} onChange={(e) => updateAdjustment(i, "description", e.target.value)} placeholder="Description" className="flex-1" />
                      <VAInput type="number" value={adj.amount} onChange={(e) => updateAdjustment(i, "amount", e.target.value)} placeholder="Amount" className="w-40" />
                      <VAButton variant="secondary" onClick={() => removeAdjustmentRow(i)}>Remove</VAButton>
                    </div>
                  ))}
                </div>
              </div>

              <div className="flex justify-end">
                <VAButton variant="primary" onClick={handleComputeTax} disabled={computing || !taxableIncome.trim()}>
                  {computing ? "Computing..." : "Compute Tax"}
                </VAButton>
              </div>
            </div>
          </VACard>
        ) : (
          /* Computation Results */
          <div className="mx-auto max-w-4xl space-y-6">
            {/* Summary Card */}
            <VACard className="p-6">
              <h2 className="mb-4 text-lg font-semibold text-va-text">Tax Summary</h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                {[
                  { label: "Taxable Income", value: fmtNum(selectedComputation.taxable_income) },
                  { label: "Statutory Rate", value: fmtPct(selectedComputation.statutory_rate) },
                  { label: "Current Tax", value: fmtNum(selectedComputation.current_tax) },
                  { label: "Effective Rate", value: selectedComputation.taxable_income !== 0 ? fmtPct(selectedComputation.current_tax / selectedComputation.taxable_income) : "N/A" },
                ].map((m) => (
                  <div key={m.label} className="rounded-va-sm bg-va-surface p-3">
                    <p className="text-xs text-va-muted">{m.label}</p>
                    <p className="mt-1 text-lg font-semibold text-va-text">{m.value}</p>
                  </div>
                ))}
              </div>
            </VACard>

            {/* Reconciliation Table */}
            {selectedComputation.reconciliation_json && selectedComputation.reconciliation_json.length > 0 && (
              <VACard className="p-6">
                <h2 className="mb-4 text-lg font-semibold text-va-text">Tax Reconciliation</h2>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-va-border text-left">
                        <th className="pb-2 pr-4 font-medium text-va-text">Description</th>
                        <th className="pb-2 pr-4 text-right font-medium text-va-text">Amount</th>
                        <th className="pb-2 text-right font-medium text-va-text">Tax Effect</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedComputation.reconciliation_json.map((row, i) => (
                        <tr key={i} className="border-b border-va-border/50">
                          <td className="py-2 pr-4 text-va-text2">{row.description}</td>
                          <td className="py-2 pr-4 text-right text-va-text2">{fmtNum(row.amount)}</td>
                          <td className="py-2 text-right text-va-text2">{fmtNum(row.tax_effect)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </VACard>
            )}

            {/* Temporary Differences */}
            <VACard className="p-6">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-va-text">Temporary Differences</h2>
                <VAButton variant="secondary" onClick={() => setShowDiffForm((prev) => !prev)}>
                  {showDiffForm ? "Cancel" : "+ Add Temporary Difference"}
                </VAButton>
              </div>

              {(selectedComputation.temporary_differences ?? []).length > 0 ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-va-border text-left">
                          <th className="pb-2 pr-4 font-medium text-va-text">Description</th>
                          <th className="pb-2 pr-4 text-right font-medium text-va-text">Carrying Amount</th>
                          <th className="pb-2 pr-4 text-right font-medium text-va-text">Tax Base</th>
                          <th className="pb-2 pr-4 text-right font-medium text-va-text">Difference</th>
                          <th className="pb-2 pr-4 text-right font-medium text-va-text">Deferred Tax Effect</th>
                          <th className="pb-2 font-medium text-va-text">Type</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedComputation.temporary_differences!.map((td) => (
                          <tr key={td.difference_id} className="border-b border-va-border/50">
                            <td className="py-2 pr-4 text-va-text2">{td.description}</td>
                            <td className="py-2 pr-4 text-right text-va-text2">{fmtNum(td.carrying_amount)}</td>
                            <td className="py-2 pr-4 text-right text-va-text2">{fmtNum(td.tax_base)}</td>
                            <td className="py-2 pr-4 text-right text-va-text2">{fmtNum(td.difference)}</td>
                            <td className="py-2 pr-4 text-right text-va-text2">{fmtNum(td.deferred_tax_effect)}</td>
                            <td className="py-2">
                              <VABadge variant={td.diff_type === "asset" ? "success" : "warning"}>{td.diff_type}</VABadge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {/* Deferred Tax Summary */}
                  {(() => {
                    const diffs = selectedComputation.temporary_differences ?? [];
                    const totalDTA = diffs.filter((d) => d.diff_type === "asset").reduce((sum, d) => sum + d.deferred_tax_effect, 0);
                    const totalDTL = diffs.filter((d) => d.diff_type === "liability").reduce((sum, d) => sum + d.deferred_tax_effect, 0);
                    return (
                      <div className="mt-4 grid grid-cols-3 gap-4 border-t border-va-border pt-4">
                        <div>
                          <p className="text-xs text-va-muted">Total DTA</p>
                          <p className="text-sm font-semibold text-va-text">{fmtNum(totalDTA)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-va-muted">Total DTL</p>
                          <p className="text-sm font-semibold text-va-text">{fmtNum(totalDTL)}</p>
                        </div>
                        <div>
                          <p className="text-xs text-va-muted">Net</p>
                          <p className="text-sm font-semibold text-va-text">{fmtNum(totalDTA - totalDTL)}</p>
                        </div>
                      </div>
                    );
                  })()}
                </>
              ) : (
                !showDiffForm && (
                  <VAEmptyState icon="file-text" title="No temporary differences" description="Add temporary differences to compute deferred tax" actionLabel="Add Difference" onAction={() => setShowDiffForm(true)} />
                )
              )}

              {/* Add Temporary Difference Form */}
              {showDiffForm && (
                <div className="mt-4 rounded-va-sm border border-va-border bg-va-surface p-4">
                  <h3 className="mb-3 text-sm font-semibold text-va-text">Add Temporary Difference</h3>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="col-span-2">
                      <label className="mb-1 block text-xs font-medium text-va-text">Description</label>
                      <VAInput value={diffDescription} onChange={(e) => setDiffDescription(e.target.value)} placeholder="e.g. Property, Plant & Equipment" />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-va-text">Carrying Amount</label>
                      <VAInput type="number" value={diffCarrying} onChange={(e) => setDiffCarrying(e.target.value)} placeholder="0" />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-va-text">Tax Base</label>
                      <VAInput type="number" value={diffTaxBase} onChange={(e) => setDiffTaxBase(e.target.value)} placeholder="0" />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium text-va-text">Type</label>
                      <select value={diffType} onChange={(e) => setDiffType(e.target.value)} className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text">
                        <option value="asset">Asset</option>
                        <option value="liability">Liability</option>
                      </select>
                    </div>
                    <div className="flex items-end">
                      <VAButton variant="primary" onClick={handleAddTemporaryDifference} disabled={addingDiff || !diffDescription.trim() || !diffCarrying.trim() || !diffTaxBase.trim()}>
                        {addingDiff ? "Adding..." : "Add"}
                      </VAButton>
                    </div>
                  </div>
                </div>
              )}
            </VACard>

            {/* Tax Note */}
            <VACard className="p-6">
              <h2 className="mb-4 text-lg font-semibold text-va-text">Tax Note</h2>
              {selectedComputation.tax_note_json ? (
                <>
                  {selectedComputation.tax_note_json.paragraphs?.map((p, i) => (
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
                  {selectedComputation.tax_note_json.references && selectedComputation.tax_note_json.references.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {selectedComputation.tax_note_json.references.map((ref, i) => (
                        <VABadge key={i} variant="violet">{ref}</VABadge>
                      ))}
                    </div>
                  )}
                  <div className="mt-4 border-t border-va-border pt-4">
                    <p className="text-sm text-va-muted">Regenerate with new instructions:</p>
                  </div>
                </>
              ) : (
                <p className="mb-4 text-sm text-va-muted">No tax note generated yet. Optionally add instructions below, then generate.</p>
              )}
              <div className="mt-3 space-y-3">
                <textarea
                  value={noteInstruction}
                  onChange={(e) => setNoteInstruction(e.target.value)}
                  placeholder="Optional: e.g. 'Emphasise the capital allowance impact' or 'Include a deferred tax reconciliation table'"
                  rows={3}
                  className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text placeholder:text-va-muted"
                />
                <div className="flex justify-end">
                  <VAButton variant="primary" onClick={handleGenerateTaxNote} disabled={generatingNote}>
                    {generatingNote ? "Generating..." : selectedComputation.tax_note_json ? "Regenerate Tax Note" : "Generate Tax Note"}
                  </VAButton>
                </div>
              </div>
            </VACard>
          </div>
        )}
      </div>
    </div>
  );
}
