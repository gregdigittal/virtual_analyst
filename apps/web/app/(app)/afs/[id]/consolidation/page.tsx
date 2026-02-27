"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  api,
  type AFSConsolidation,
  type AFSConsolidationEntity,
  type AFSEngagement,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VABadge,
  VASpinner,
  VAEmptyState,
  VAInput,
  useToast,
} from "@/components/ui";

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmtNumber(v: number): string {
  return Math.abs(v).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function statusBadgeVariant(
  status: string,
): "default" | "success" | "danger" | "warning" {
  if (status === "consolidated") return "success";
  if (status === "error") return "danger";
  if (status === "pending") return "warning";
  return "default";
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function ConsolidationPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const engagementId = params.id as string;

  /* State ---------------------------------------------------------- */
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [engagement, setEngagement] = useState<AFSEngagement | null>(null);
  const [consolidation, setConsolidation] =
    useState<AFSConsolidation | null>(null);
  const [entities, setEntities] = useState<AFSConsolidationEntity[]>([]);
  const [orgStructures, setOrgStructures] = useState<
    { org_id: string; group_name: string; reporting_currency: string; status: string }[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [linking, setLinking] = useState(false);
  const [running, setRunning] = useState(false);

  // Link org form
  const [selectedOrgId, setSelectedOrgId] = useState("");
  const [reportingCurrency, setReportingCurrency] = useState("ZAR");

  // FX rates (keyed by currency code)
  const [fxAvgRates, setFxAvgRates] = useState<Record<string, string>>({});
  const [fxClosingRates, setFxClosingRates] = useState<Record<string, string>>({});

  /* ------------------------------------------------------------------ */
  /*  Initial data load                                                  */
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
      if (!cancelled) setTenantId(ctx.tenantId);

      try {
        const eng = await api.afs.getEngagement(ctx.tenantId, engagementId);
        if (!cancelled) setEngagement(eng);

        // Try to load existing consolidation
        let existingConsolidation: AFSConsolidation | null = null;
        try {
          existingConsolidation = await api.afs.getConsolidation(
            ctx.tenantId,
            engagementId,
          );
        } catch {
          // 404 means no consolidation linked yet -- that is fine
          existingConsolidation = null;
        }

        if (existingConsolidation) {
          if (!cancelled) {
            setConsolidation(existingConsolidation);
            // Seed FX rate inputs from existing data
            const avgEntries = Object.entries(
              existingConsolidation.fx_avg_rates ?? {},
            );
            const closingEntries = Object.entries(
              existingConsolidation.fx_closing_rates ?? {},
            );
            const avgMap: Record<string, string> = {};
            avgEntries.forEach(([k, v]) => {
              avgMap[k] = String(v);
            });
            const closingMap: Record<string, string> = {};
            closingEntries.forEach(([k, v]) => {
              closingMap[k] = String(v);
            });
            setFxAvgRates(avgMap);
            setFxClosingRates(closingMap);
          }

          // Load entities
          try {
            const entRes = await api.afs.listConsolidationEntities(
              ctx.tenantId,
              engagementId,
            );
            if (!cancelled) setEntities(entRes.items ?? []);
          } catch {
            if (!cancelled) toast.error("Failed to load consolidation entities");
          }
        } else {
          // Load org structures for the link form
          try {
            const orgRes = await api.orgStructures.list(ctx.tenantId);
            if (!cancelled) setOrgStructures(orgRes.items ?? []);
          } catch {
            if (!cancelled) toast.error("Failed to load organisation structures");
          }
        }
      } catch {
        if (!cancelled) toast.error("Failed to load engagement data");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [engagementId, router, toast]);

  /* ------------------------------------------------------------------ */
  /*  Derived state                                                      */
  /* ------------------------------------------------------------------ */

  const reportingCcy = consolidation?.reporting_currency ?? reportingCurrency;

  const foreignCurrencies = entities
    .map((e) => e.currency)
    .filter((c) => c && c !== reportingCcy)
    .filter((c, i, arr) => arr.indexOf(c) === i); // unique

  const allHaveTB = entities.length > 0 && entities.every((e) => e.has_trial_balance);

  const consolidatedTB: { account: string; net: number }[] = (() => {
    if (!consolidation?.consolidated_tb_json) return [];
    const raw = consolidation.consolidated_tb_json as {
      account_name?: string;
      account?: string;
      net_amount?: number;
      net?: number;
    }[];
    return raw
      .map((row) => ({
        account: row.account_name ?? row.account ?? "Unknown",
        net: row.net_amount ?? row.net ?? 0,
      }))
      .sort((a, b) => Math.abs(b.net) - Math.abs(a.net))
      .slice(0, 20);
  })();

  const eliminations = (consolidation?.elimination_entries_json ?? []) as {
    account?: string;
    from_entity?: string;
    to_entity?: string;
    amount?: number;
  }[];

  /* ------------------------------------------------------------------ */
  /*  Handlers                                                           */
  /* ------------------------------------------------------------------ */

  async function handleLinkOrg() {
    if (!tenantId || !selectedOrgId) return;
    setLinking(true);
    try {
      const result = await api.afs.linkOrg(tenantId, engagementId, {
        org_id: selectedOrgId,
        reporting_currency: reportingCurrency || undefined,
      });
      setConsolidation(result);

      // Load entities after linking
      try {
        const entRes = await api.afs.listConsolidationEntities(
          tenantId,
          engagementId,
        );
        setEntities(entRes.items ?? []);
      } catch {
        toast.error("Failed to load consolidation entities");
      }

      toast.success("Organisation linked successfully");
    } catch {
      toast.error("Failed to link organisation");
    } finally {
      setLinking(false);
    }
  }

  function buildFxRatesPayload(): {
    fx_avg_rates?: Record<string, number>;
    fx_closing_rates?: Record<string, number>;
  } {
    const body: {
      fx_avg_rates?: Record<string, number>;
      fx_closing_rates?: Record<string, number>;
    } = {};

    if (foreignCurrencies.length > 0) {
      const avg: Record<string, number> = {};
      const closing: Record<string, number> = {};
      foreignCurrencies.forEach((ccy) => {
        const a = parseFloat(fxAvgRates[ccy] ?? "");
        const c = parseFloat(fxClosingRates[ccy] ?? "");
        if (!Number.isNaN(a)) avg[ccy] = a;
        if (!Number.isNaN(c)) closing[ccy] = c;
      });
      if (Object.keys(avg).length > 0) body.fx_avg_rates = avg;
      if (Object.keys(closing).length > 0) body.fx_closing_rates = closing;
    }

    return body;
  }

  async function handleRunConsolidation() {
    if (!tenantId) return;
    setRunning(true);
    try {
      const body = buildFxRatesPayload();
      const result = await api.afs.runConsolidation(
        tenantId,
        engagementId,
        Object.keys(body).length > 0 ? body : undefined,
      );
      setConsolidation(result);
      toast.success("Consolidation completed successfully");
    } catch {
      toast.error("Failed to run consolidation");
    } finally {
      setRunning(false);
    }
  }

  /* ------------------------------------------------------------------ */
  /*  Loading state                                                      */
  /* ------------------------------------------------------------------ */

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <VASpinner />
      </div>
    );
  }

  /* ------------------------------------------------------------------ */
  /*  Render                                                             */
  /* ------------------------------------------------------------------ */

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-va-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => router.push(`/afs/${engagementId}/sections`)}
            className="text-va-text2 hover:text-va-text"
          >
            &larr;
          </button>
          <h1 className="text-lg font-semibold text-va-text">
            {engagement?.entity_name} — Consolidation
          </h1>
        </div>
        <div className="flex items-center gap-2">
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/sections`)}
          >
            Sections
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/tax`)}
          >
            Tax
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/review`)}
          >
            Review
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/output`)}
          >
            Output
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/analytics`)}
          >
            Analytics
          </VAButton>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 space-y-6 overflow-y-auto p-6">
        {/* ---------------------------------------------------------- */}
        {/*  Link Org-Structure panel (no consolidation yet)            */}
        {/* ---------------------------------------------------------- */}
        {!consolidation && (
          <VACard className="mx-auto max-w-2xl p-6">
            <h2 className="mb-4 text-base font-semibold text-va-text">
              Link Organisation Structure
            </h2>

            {orgStructures.length === 0 ? (
              <VAEmptyState
                icon="file-text"
                title="No organisation structures"
                description="Create an organisation structure first before linking it to this engagement."
              />
            ) : (
              <div className="space-y-4">
                {/* Org select */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text2">
                    Organisation
                  </label>
                  <select
                    value={selectedOrgId}
                    onChange={(e) => setSelectedOrgId(e.target.value)}
                    className="w-full rounded-va-sm border border-va-border bg-va-panel px-3 py-2 text-sm text-va-text"
                  >
                    <option value="">Select an organisation...</option>
                    {orgStructures.map((org) => (
                      <option key={org.org_id} value={org.org_id}>
                        {org.group_name} ({org.reporting_currency})
                      </option>
                    ))}
                  </select>
                </div>

                {/* Reporting currency */}
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text2">
                    Reporting Currency
                  </label>
                  <VAInput
                    value={reportingCurrency}
                    onChange={(e) =>
                      setReportingCurrency(e.target.value.toUpperCase())
                    }
                    placeholder="ZAR"
                  />
                </div>

                {/* Link button */}
                <VAButton
                  variant="primary"
                  onClick={handleLinkOrg}
                  disabled={linking || !selectedOrgId}
                >
                  {linking ? "Linking..." : "Link Organisation"}
                </VAButton>
              </div>
            )}
          </VACard>
        )}

        {/* ---------------------------------------------------------- */}
        {/*  Entity TB Status                                           */}
        {/* ---------------------------------------------------------- */}
        {consolidation && (
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-semibold text-va-text">
              Entity Trial Balance Status
            </h2>

            {entities.length === 0 ? (
              <p className="text-sm text-va-muted">
                No entities found for this consolidation group.
              </p>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead>
                      <tr>
                        <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                          Name
                        </th>
                        <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                          Type
                        </th>
                        <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                          Currency
                        </th>
                        <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                          TB Status
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {entities.map((entity) => (
                        <tr key={entity.entity_id}>
                          <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                            {entity.name}
                          </td>
                          <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                            {entity.entity_type}
                          </td>
                          <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                            {entity.currency}
                          </td>
                          <td className="border-b border-va-border/50 px-4 py-2">
                            <VABadge
                              variant={
                                entity.has_trial_balance ? "success" : "danger"
                              }
                            >
                              {entity.has_trial_balance ? "Uploaded" : "Missing"}
                            </VABadge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="mt-3 text-xs text-va-muted">
                  Upload trial balances via the Setup page with entity tags.
                </p>
              </>
            )}
          </VACard>
        )}

        {/* ---------------------------------------------------------- */}
        {/*  FX Translation Rates                                       */}
        {/* ---------------------------------------------------------- */}
        {consolidation && foreignCurrencies.length > 0 && (
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-semibold text-va-text">
              FX Translation Rates
            </h2>
            <p className="mb-4 text-xs text-va-text2">
              Rates to translate from entity currency to reporting currency (
              {reportingCcy}).
            </p>

            <div className="space-y-4">
              {foreignCurrencies.map((ccy) => (
                <div key={ccy} className="flex items-center gap-4">
                  <span className="w-16 text-sm font-medium text-va-text">
                    {ccy}
                  </span>
                  <div className="flex-1">
                    <label className="mb-1 block text-xs text-va-text2">
                      Average Rate
                    </label>
                    <VAInput
                      type="number"
                      step="0.0001"
                      value={fxAvgRates[ccy] ?? ""}
                      onChange={(e) =>
                        setFxAvgRates((prev) => ({
                          ...prev,
                          [ccy]: e.target.value,
                        }))
                      }
                      placeholder="e.g. 17.50"
                    />
                  </div>
                  <div className="flex-1">
                    <label className="mb-1 block text-xs text-va-text2">
                      Closing Rate
                    </label>
                    <VAInput
                      type="number"
                      step="0.0001"
                      value={fxClosingRates[ccy] ?? ""}
                      onChange={(e) =>
                        setFxClosingRates((prev) => ({
                          ...prev,
                          [ccy]: e.target.value,
                        }))
                      }
                      placeholder="e.g. 18.00"
                    />
                  </div>
                </div>
              ))}
            </div>
          </VACard>
        )}

        {/* ---------------------------------------------------------- */}
        {/*  Run Consolidation                                          */}
        {/* ---------------------------------------------------------- */}
        {consolidation && (
          <VACard className="p-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <h2 className="text-base font-semibold text-va-text">
                  Run Consolidation
                </h2>
                <VABadge variant={statusBadgeVariant(consolidation.status)}>
                  {consolidation.status.charAt(0).toUpperCase() +
                    consolidation.status.slice(1)}
                </VABadge>
              </div>
              <VAButton
                variant="primary"
                onClick={handleRunConsolidation}
                disabled={running || !allHaveTB}
              >
                {running ? "Running..." : "Run Consolidation"}
              </VAButton>
            </div>

            {!allHaveTB && entities.length > 0 && (
              <p className="mt-3 text-xs text-amber-400">
                All entities must have trial balances uploaded before running
                consolidation.
              </p>
            )}

            {consolidation.error_message && (
              <div className="mt-3 rounded-va-sm border border-red-500/30 bg-red-500/10 p-3">
                <p className="text-xs font-medium text-red-400">Error</p>
                <p className="mt-1 text-xs text-red-300/80">
                  {consolidation.error_message}
                </p>
              </div>
            )}

            {consolidation.consolidated_at && (
              <p className="mt-3 text-xs text-va-text2">
                Last consolidated:{" "}
                {new Date(consolidation.consolidated_at).toLocaleDateString(
                  "en-ZA",
                  {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  },
                )}
              </p>
            )}
          </VACard>
        )}

        {/* ---------------------------------------------------------- */}
        {/*  Consolidated TB Summary                                    */}
        {/* ---------------------------------------------------------- */}
        {consolidation && consolidatedTB.length > 0 && (
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-semibold text-va-text">
              Consolidated Trial Balance Summary
            </h2>
            <p className="mb-3 text-xs text-va-text2">
              Top 20 accounts by absolute net value
            </p>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr>
                    <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                      Account Name
                    </th>
                    <th className="border-b border-va-border px-4 py-2 text-right font-medium text-va-text2">
                      Net Amount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {consolidatedTB.map((row, idx) => (
                    <tr key={idx}>
                      <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                        {row.account}
                      </td>
                      <td
                        className={`border-b border-va-border/50 px-4 py-2 text-right ${
                          row.net < 0 ? "text-red-400" : "text-va-text"
                        }`}
                      >
                        {row.net < 0 ? "(" : ""}
                        {fmtNumber(row.net)}
                        {row.net < 0 ? ")" : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </VACard>
        )}

        {/* ---------------------------------------------------------- */}
        {/*  Elimination Entries                                         */}
        {/* ---------------------------------------------------------- */}
        {consolidation && eliminations.length > 0 && (
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-semibold text-va-text">
              Elimination Entries
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr>
                    <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                      Account
                    </th>
                    <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                      From Entity
                    </th>
                    <th className="border-b border-va-border px-4 py-2 font-medium text-va-text2">
                      To Entity
                    </th>
                    <th className="border-b border-va-border px-4 py-2 text-right font-medium text-va-text2">
                      Amount
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {eliminations.map((entry, idx) => (
                    <tr key={idx}>
                      <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                        {entry.account ?? "—"}
                      </td>
                      <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                        {entry.from_entity ?? "—"}
                      </td>
                      <td className="border-b border-va-border/50 px-4 py-2 text-va-text">
                        {entry.to_entity ?? "—"}
                      </td>
                      <td className="border-b border-va-border/50 px-4 py-2 text-right text-va-text">
                        {entry.amount != null ? fmtNumber(entry.amount) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </VACard>
        )}
      </div>
    </div>
  );
}
