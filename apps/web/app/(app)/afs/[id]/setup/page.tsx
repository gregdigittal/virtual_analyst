"use client";

import {
  api,
  type AFSEngagement,
  type AFSFramework,
  type AFSTrialBalance,
  type AFSPriorAFS,
  type AFSDiscrepancy,
  type AFSProjection,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VABadge,
  VACard,
  VAInput,
  VASelect,
  VASpinner,
  useToast,
} from "@/components/ui";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const STEPS = [
  { num: 1, label: "Framework & Entity" },
  { num: 2, label: "Upload Data" },
  { num: 3, label: "Reconciliation" },
  { num: 4, label: "YTD Projection" },
];

const MONTHS = [
  "01",
  "02",
  "03",
  "04",
  "05",
  "06",
  "07",
  "08",
  "09",
  "10",
  "11",
  "12",
];

export default function AFSSetupPage() {
  const params = useParams();
  const engagementId = params.id as string;
  const router = useRouter();
  const { toast } = useToast();

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [step, setStep] = useState(1);

  // Data
  const [engagement, setEngagement] = useState<AFSEngagement | null>(null);
  const [framework, setFramework] = useState<AFSFramework | null>(null);
  const [frameworks, setFrameworks] = useState<AFSFramework[]>([]);
  const [trialBalances, setTrialBalances] = useState<AFSTrialBalance[]>([]);
  const [priorAFS, setPriorAFS] = useState<AFSPriorAFS[]>([]);
  const [discrepancies, setDiscrepancies] = useState<AFSDiscrepancy[]>([]);
  const [projections, setProjections] = useState<AFSProjection[]>([]);

  // Roll-forward state
  const [rollingForward, setRollingForward] = useState(false);
  const [rolledForward, setRolledForward] = useState(false);

  // Upload state
  const [uploading, setUploading] = useState(false);

  // Step 3 state
  const [baseSource, setBaseSource] = useState<string>("");

  // Step 4 state
  const [projectionInputs, setProjectionInputs] = useState<
    Record<string, string>
  >({});

  /* ------------------------------------------------------------------ */
  /*  Data loading                                                       */
  /* ------------------------------------------------------------------ */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);
      try {
        const [eng, fwRes, tbRes, paRes, discRes, projRes] = await Promise.all(
          [
            api.afs.getEngagement(ctx.tenantId, engagementId),
            api.afs.listFrameworks(ctx.tenantId),
            api.afs.listTrialBalances(ctx.tenantId, engagementId),
            api.afs.listPriorAFS(ctx.tenantId, engagementId),
            api.afs.listDiscrepancies(ctx.tenantId, engagementId),
            api.afs.listProjections(ctx.tenantId, engagementId),
          ],
        );
        if (!cancelled) {
          setEngagement(eng);
          setFrameworks(fwRes.items ?? []);
          const fw = (fwRes.items ?? []).find(
            (f) => f.framework_id === eng.framework_id,
          );
          setFramework(fw ?? null);
          setTrialBalances(tbRes.items ?? []);
          setPriorAFS(paRes.items ?? []);
          setDiscrepancies(discRes.items ?? []);
          setProjections(projRes.items ?? []);
          if (eng.base_source) setBaseSource(eng.base_source);
        }
      } catch (e) {
        if (!cancelled)
          toast.error(
            e instanceof Error ? e.message : "Failed to load engagement",
          );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [engagementId, router, toast]);

  /* ------------------------------------------------------------------ */
  /*  Loading state                                                      */
  /* ------------------------------------------------------------------ */
  if (loading) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8">
        <div className="flex justify-center py-16">
          <VASpinner />
        </div>
      </main>
    );
  }

  if (!engagement) {
    return (
      <main className="mx-auto max-w-4xl px-4 py-8">
        <p className="text-va-text2">Engagement not found.</p>
      </main>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Derived state                                                      */
  /* ------------------------------------------------------------------ */
  const hasPdf = priorAFS.some((p) => p.source_type === "pdf");
  const hasExcel = priorAFS.some((p) => p.source_type === "excel");
  const hasBothSources = hasPdf && hasExcel;
  const isPartial = trialBalances.some((tb) => tb.is_partial);

  /* ------------------------------------------------------------------ */
  /*  Render                                                             */
  /* ------------------------------------------------------------------ */
  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      {/* Page heading */}
      <div className="mb-6">
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Setup: {engagement.entity_name}
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          {framework?.name ?? "Unknown framework"} &middot;{" "}
          {engagement.period_start} to {engagement.period_end}
        </p>
      </div>

      {/* Step indicator */}
      <div className="mb-6 flex items-center gap-2">
        {STEPS.map((s) => (
          <button
            key={s.num}
            type="button"
            onClick={() => setStep(s.num)}
            className={`flex items-center gap-2 rounded-va-sm px-3 py-1.5 text-sm font-medium transition-colors ${
              step === s.num
                ? "bg-va-blue text-white"
                : "bg-va-surface text-va-text2 hover:bg-va-surface/80"
            }`}
          >
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/20 text-xs">
              {s.num}
            </span>
            {s.label}
          </button>
        ))}
      </div>

      {/* -------------------------------------------------------------- */}
      {/*  Step 1 — Framework & Entity                                    */}
      {/* -------------------------------------------------------------- */}
      {step === 1 && (
        <VACard className="p-6">
          <h2 className="text-lg font-semibold text-va-text">
            Framework &amp; Entity
          </h2>
          <p className="mt-1 text-sm text-va-text2">
            Confirm the engagement details before uploading data.
          </p>
          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <span className="text-xs font-medium uppercase text-va-muted">
                Entity
              </span>
              <p className="mt-1 text-sm text-va-text">
                {engagement.entity_name}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium uppercase text-va-muted">
                Framework
              </span>
              <p className="mt-1 text-sm text-va-text">
                {framework?.name ?? engagement.framework_id}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium uppercase text-va-muted">
                Period Start
              </span>
              <p className="mt-1 text-sm text-va-text">
                {engagement.period_start}
              </p>
            </div>
            <div>
              <span className="text-xs font-medium uppercase text-va-muted">
                Period End
              </span>
              <p className="mt-1 text-sm text-va-text">
                {engagement.period_end}
              </p>
            </div>
          </div>
          {engagement.prior_engagement_id && (
            <div className="mt-4 rounded-va-md border border-va-blue/30 bg-va-blue/5 p-4">
              <h3 className="text-sm font-semibold text-va-text">
                Roll Forward Available
              </h3>
              <p className="mt-1 text-xs text-va-text2">
                This engagement is linked to a prior period. You can carry
                forward sections and comparative data to use as a starting
                point.
              </p>
              <div className="mt-3 flex items-center gap-3">
                <VAButton
                  variant="primary"
                  disabled={rollingForward || rolledForward}
                  onClick={async () => {
                    if (!tenantId) return;
                    setRollingForward(true);
                    try {
                      const result = await api.afs.rollforward(
                        tenantId,
                        engagementId,
                      );
                      toast.success(
                        `Rolled forward ${result.sections_copied} section${result.sections_copied !== 1 ? "s" : ""}`,
                      );
                      setRolledForward(true);
                    } catch (e) {
                      toast.error(
                        e instanceof Error
                          ? e.message
                          : "Roll-forward failed",
                      );
                    } finally {
                      setRollingForward(false);
                    }
                  }}
                >
                  {rollingForward
                    ? "Rolling forward..."
                    : rolledForward
                      ? "Rolled Forward"
                      : "Roll Forward Sections"}
                </VAButton>
                {rolledForward && (
                  <span className="text-xs text-green-400">
                    Sections and comparatives copied successfully
                  </span>
                )}
              </div>
            </div>
          )}
          <div className="mt-6 flex justify-end">
            <VAButton variant="primary" onClick={() => setStep(2)}>
              Next: Upload Data
            </VAButton>
          </div>
        </VACard>
      )}

      {/* -------------------------------------------------------------- */}
      {/*  Step 2 — Upload Financial Data                                 */}
      {/* -------------------------------------------------------------- */}
      {step === 2 && (
        <VACard className="p-6">
          <h2 className="text-lg font-semibold text-va-text">
            Upload Financial Data
          </h2>
          <p className="mt-1 text-sm text-va-text2">
            Upload your Excel trial balance, PDF AFS, or both. When both are
            provided, we&apos;ll identify discrepancies for your review.
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            {/* Excel upload zone */}
            <div className="rounded-va-md border-2 border-dashed border-va-border p-6 text-center">
              <p className="text-sm font-medium text-va-text">
                Excel / CSV Trial Balance
              </p>
              <p className="mt-1 text-xs text-va-text2">.xlsx or .csv files</p>
              <input
                type="file"
                accept=".xlsx,.csv"
                className="mt-3 text-sm text-va-text2"
                disabled={uploading}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file || !tenantId) return;
                  setUploading(true);
                  try {
                    const tb = await api.afs.uploadTrialBalance(
                      tenantId,
                      engagementId,
                      file,
                    );
                    setTrialBalances((prev) => [...prev, tb]);
                    toast.success("Trial balance uploaded");
                  } catch (err) {
                    toast.error(
                      err instanceof Error ? err.message : "Upload failed",
                    );
                  } finally {
                    setUploading(false);
                    e.target.value = "";
                  }
                }}
              />
            </div>

            {/* PDF upload zone */}
            <div className="rounded-va-md border-2 border-dashed border-va-border p-6 text-center">
              <p className="text-sm font-medium text-va-text">
                PDF Annual Financial Statements
              </p>
              <p className="mt-1 text-xs text-va-text2">.pdf files</p>
              <input
                type="file"
                accept=".pdf"
                className="mt-3 text-sm text-va-text2"
                disabled={uploading}
                onChange={async (e) => {
                  const file = e.target.files?.[0];
                  if (!file || !tenantId) return;
                  setUploading(true);
                  try {
                    const pa = await api.afs.uploadPriorAFS(
                      tenantId,
                      engagementId,
                      file,
                      "pdf",
                    );
                    setPriorAFS((prev) => [...prev, pa]);
                    toast.success("PDF AFS uploaded");
                  } catch (err) {
                    toast.error(
                      err instanceof Error ? err.message : "Upload failed",
                    );
                  } finally {
                    setUploading(false);
                    e.target.value = "";
                  }
                }}
              />
            </div>
          </div>

          {/* Excel-based AFS upload */}
          <div className="mt-4 rounded-va-md border-2 border-dashed border-va-border p-6 text-center">
            <p className="text-sm font-medium text-va-text">
              Excel-Based AFS (optional)
            </p>
            <p className="mt-1 text-xs text-va-text2">
              Upload Excel-based annual financial statements for comparison with
              PDF AFS
            </p>
            <input
              type="file"
              accept=".xlsx,.xls"
              className="mt-3 text-sm text-va-text2"
              disabled={uploading}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file || !tenantId) return;
                setUploading(true);
                try {
                  const pa = await api.afs.uploadPriorAFS(
                    tenantId,
                    engagementId,
                    file,
                    "excel",
                  );
                  setPriorAFS((prev) => [...prev, pa]);
                  toast.success("Excel AFS uploaded");
                } catch (err) {
                  toast.error(
                    err instanceof Error ? err.message : "Upload failed",
                  );
                } finally {
                  setUploading(false);
                  e.target.value = "";
                }
              }}
            />
          </div>

          {/* Uploaded files list */}
          {(trialBalances.length > 0 || priorAFS.length > 0) && (
            <div className="mt-4">
              <h3 className="text-sm font-medium text-va-text">
                Uploaded Files
              </h3>
              <div className="mt-2 space-y-2">
                {trialBalances.map((tb) => (
                  <div
                    key={tb.trial_balance_id}
                    className="flex items-center gap-2 rounded-va-xs bg-va-surface px-3 py-2 text-sm"
                  >
                    <VABadge variant="violet">Trial Balance</VABadge>
                    <span className="text-va-text">{tb.source}</span>
                    {tb.is_partial && (
                      <VABadge variant="warning">Partial</VABadge>
                    )}
                  </div>
                ))}
                {priorAFS.map((pa) => (
                  <div
                    key={pa.prior_afs_id}
                    className="flex items-center gap-2 rounded-va-xs bg-va-surface px-3 py-2 text-sm"
                  >
                    <VABadge
                      variant={
                        pa.source_type === "pdf" ? "danger" : "success"
                      }
                    >
                      {pa.source_type.toUpperCase()}
                    </VABadge>
                    <span className="text-va-text">{pa.filename}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {uploading && (
            <div className="mt-3 flex justify-center">
              <VASpinner />
            </div>
          )}

          <div className="mt-6 flex justify-between">
            <VAButton variant="secondary" onClick={() => setStep(1)}>
              Back
            </VAButton>
            <VAButton
              variant="primary"
              disabled={trialBalances.length === 0 && priorAFS.length === 0}
              onClick={async () => {
                if (hasPdf && hasExcel) {
                  // Trigger reconciliation then go to step 3
                  if (tenantId) {
                    try {
                      const res = await api.afs.reconcile(
                        tenantId,
                        engagementId,
                      );
                      setDiscrepancies(res.discrepancies ?? []);
                    } catch {
                      /* ignore */
                    }
                  }
                  setStep(3);
                } else {
                  // Auto-set base source
                  if (tenantId) {
                    const src = hasPdf
                      ? "pdf"
                      : hasExcel
                        ? "excel"
                        : "va_baseline";
                    try {
                      await api.afs.setBaseSource(
                        tenantId,
                        engagementId,
                        src,
                      );
                      setBaseSource(src);
                    } catch {
                      /* ignore */
                    }
                  }
                  // Check if partial data -> step 4, otherwise complete
                  if (isPartial) {
                    setStep(4);
                  } else {
                    if (tenantId) {
                      try {
                        await api.afs.updateEngagement(
                          tenantId,
                          engagementId,
                          { status: "ingestion" },
                        );
                        toast.success("Setup complete");
                        router.push(`/afs/${engagementId}/sections`);
                      } catch (e) {
                        toast.error(
                          e instanceof Error
                            ? e.message
                            : "Failed to complete setup",
                        );
                      }
                    }
                  }
                }
              }}
            >
              {trialBalances.length === 0 && priorAFS.length === 0
                ? "Upload at least one file"
                : "Next"}
            </VAButton>
          </div>
        </VACard>
      )}

      {/* -------------------------------------------------------------- */}
      {/*  Step 3 — Source Reconciliation                                  */}
      {/* -------------------------------------------------------------- */}
      {step === 3 && (
        <VACard className="p-6">
          <h2 className="text-lg font-semibold text-va-text">
            Source Reconciliation
          </h2>
          <p className="mt-1 text-sm text-va-text2">
            Both PDF and Excel sources detected. Review discrepancies below and
            select a base source.
          </p>

          {/* Base source selector */}
          <div className="mt-4 flex items-center gap-4">
            <span className="text-sm font-medium text-va-text">
              Base Source:
            </span>
            <label className="flex items-center gap-2 text-sm text-va-text">
              <input
                type="radio"
                name="base"
                value="excel"
                checked={baseSource === "excel"}
                onChange={() => setBaseSource("excel")}
              />
              Excel
            </label>
            <label className="flex items-center gap-2 text-sm text-va-text">
              <input
                type="radio"
                name="base"
                value="pdf"
                checked={baseSource === "pdf"}
                onChange={() => setBaseSource("pdf")}
              />
              PDF
            </label>
          </div>

          {/* Discrepancy table */}
          {discrepancies.length > 0 ? (
            <div className="mt-4 overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-va-border text-left text-xs font-medium uppercase text-va-muted">
                    <th className="px-3 py-2">Line Item</th>
                    <th className="px-3 py-2">PDF Value</th>
                    <th className="px-3 py-2">Excel Value</th>
                    <th className="px-3 py-2">Difference</th>
                    <th className="px-3 py-2">Resolution</th>
                    <th className="px-3 py-2">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {discrepancies.map((d) => (
                    <tr
                      key={d.discrepancy_id}
                      className="border-b border-va-border/50"
                    >
                      <td className="px-3 py-2 text-va-text">
                        {d.line_item}
                      </td>
                      <td className="px-3 py-2 text-va-text">
                        {d.pdf_value?.toLocaleString() ?? "\u2014"}
                      </td>
                      <td className="px-3 py-2 text-va-text">
                        {d.excel_value?.toLocaleString() ?? "\u2014"}
                      </td>
                      <td className="px-3 py-2 text-va-text">
                        {d.difference?.toLocaleString() ?? "\u2014"}
                      </td>
                      <td className="px-3 py-2">
                        <VASelect
                          value={d.resolution ?? ""}
                          onChange={async (e) => {
                            if (!tenantId) return;
                            try {
                              const updated =
                                await api.afs.resolveDiscrepancy(
                                  tenantId,
                                  engagementId,
                                  d.discrepancy_id,
                                  {
                                    resolution: e.target.value,
                                    resolution_note: d.resolution_note ?? "",
                                  },
                                );
                              setDiscrepancies((prev) =>
                                prev.map((x) =>
                                  x.discrepancy_id === d.discrepancy_id
                                    ? updated
                                    : x,
                                ),
                              );
                            } catch {
                              /* ignore */
                            }
                          }}
                        >
                          <option value="">Select...</option>
                          <option value="use_pdf">Use PDF</option>
                          <option value="use_excel">Use Excel</option>
                          <option value="noted">Noted</option>
                        </VASelect>
                      </td>
                      <td className="px-3 py-2">
                        <VAInput
                          value={d.resolution_note ?? ""}
                          placeholder="Add note..."
                          onChange={(e) => {
                            const note = e.target.value;
                            setDiscrepancies((prev) =>
                              prev.map((x) =>
                                x.discrepancy_id === d.discrepancy_id
                                  ? { ...x, resolution_note: note }
                                  : x,
                              ),
                            );
                          }}
                          onBlur={async (e) => {
                            if (!tenantId || !d.resolution) return;
                            try {
                              await api.afs.resolveDiscrepancy(
                                tenantId,
                                engagementId,
                                d.discrepancy_id,
                                {
                                  resolution: d.resolution,
                                  resolution_note: e.target.value,
                                },
                              );
                            } catch {
                              /* ignore */
                            }
                          }}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 text-sm text-va-text2">
              No discrepancies found between sources.
            </p>
          )}

          <div className="mt-6 flex justify-between">
            <VAButton variant="secondary" onClick={() => setStep(2)}>
              Back
            </VAButton>
            <VAButton
              variant="primary"
              disabled={!baseSource}
              onClick={async () => {
                if (!tenantId) return;
                try {
                  await api.afs.setBaseSource(
                    tenantId,
                    engagementId,
                    baseSource,
                  );
                } catch {
                  /* ignore */
                }
                if (isPartial) {
                  setStep(4);
                } else {
                  try {
                    await api.afs.updateEngagement(
                      tenantId,
                      engagementId,
                      { status: "ingestion" },
                    );
                    toast.success("Setup complete");
                    router.push(`/afs/${engagementId}/sections`);
                  } catch (e) {
                    toast.error(
                      e instanceof Error
                        ? e.message
                        : "Failed to complete setup",
                    );
                  }
                }
              }}
            >
              {!baseSource ? "Select a base source" : "Next"}
            </VAButton>
          </div>
        </VACard>
      )}

      {/* -------------------------------------------------------------- */}
      {/*  Step 4 — YTD Projection                                        */}
      {/* -------------------------------------------------------------- */}
      {step === 4 && (
        <VACard className="p-6">
          <h2 className="text-lg font-semibold text-va-text">
            YTD Projection
          </h2>
          <p className="mt-1 text-sm text-va-text2">
            Your trial balance covers only part of the financial year. Describe
            how missing months should be projected.
          </p>

          <div className="mt-4 space-y-3">
            {(() => {
              const year =
                engagement.period_end?.split("-")[0] ?? "2026";
              const missingMonths = MONTHS.filter((m) => {
                const monthKey = `${year}-${m}`;
                return !trialBalances.some((tb) =>
                  (tb.period_months ?? []).includes(monthKey),
                );
              });

              if (missingMonths.length === 0) {
                return (
                  <p className="text-sm text-va-text2">
                    All months are covered by the uploaded trial balance data. No
                    projections are needed.
                  </p>
                );
              }

              return missingMonths.map((m) => {
                const monthKey = `${year}-${m}`;
                const existingProjection = projections.find(
                  (p) => p.month === monthKey,
                );
                return (
                  <div
                    key={monthKey}
                    className="rounded-va-xs border border-va-border p-3"
                  >
                    <div className="flex items-center gap-2">
                      <VABadge variant="warning">Missing</VABadge>
                      <span className="text-sm font-medium text-va-text">
                        {monthKey}
                      </span>
                      {existingProjection && (
                        <VABadge variant="success">Projected</VABadge>
                      )}
                    </div>
                    {!existingProjection && (
                      <div className="mt-2">
                        <VAInput
                          placeholder="e.g. Assume flat revenue from prior month, 5% seasonal uplift"
                          value={projectionInputs[monthKey] ?? ""}
                          onChange={(e) =>
                            setProjectionInputs((prev) => ({
                              ...prev,
                              [monthKey]: e.target.value,
                            }))
                          }
                        />
                        <VAButton
                          variant="secondary"
                          className="mt-2"
                          disabled={!projectionInputs[monthKey]?.trim()}
                          onClick={async () => {
                            if (!tenantId) return;
                            try {
                              const proj = await api.afs.createProjection(
                                tenantId,
                                engagementId,
                                {
                                  month: monthKey,
                                  basis_description:
                                    projectionInputs[monthKey]!.trim(),
                                },
                              );
                              setProjections((prev) => [...prev, proj]);
                              setProjectionInputs((prev) => {
                                const next = { ...prev };
                                delete next[monthKey];
                                return next;
                              });
                              toast.success(`Projection saved for ${monthKey}`);
                            } catch (e) {
                              toast.error(
                                e instanceof Error
                                  ? e.message
                                  : "Failed to save projection",
                              );
                            }
                          }}
                        >
                          Save Projection
                        </VAButton>
                      </div>
                    )}
                    {existingProjection && (
                      <p className="mt-1 text-xs text-va-text2">
                        Basis: {existingProjection.basis_description}
                      </p>
                    )}
                  </div>
                );
              });
            })()}
          </div>

          <div className="mt-6 flex justify-between">
            <VAButton
              variant="secondary"
              onClick={() => {
                setStep(hasBothSources ? 3 : 2);
              }}
            >
              Back
            </VAButton>
            <VAButton
              variant="primary"
              onClick={async () => {
                if (!tenantId) return;
                try {
                  await api.afs.updateEngagement(tenantId, engagementId, {
                    status: "ingestion",
                  });
                  toast.success("Setup complete");
                  router.push(`/afs/${engagementId}/sections`);
                } catch (e) {
                  toast.error(
                    e instanceof Error
                      ? e.message
                      : "Failed to complete setup",
                  );
                }
              }}
            >
              Complete Setup
            </VAButton>
          </div>
        </VACard>
      )}
    </main>
  );
}
