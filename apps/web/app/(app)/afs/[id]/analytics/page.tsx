"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { api, type AFSAnalytics } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import {
  VAButton,
  VACard,
  VABadge,
  VASpinner,
  VASelect,
  VAEmptyState,
  useToast,
} from "@/components/ui";

/* ---------------------------------------------------------------------- */
/*  Constants                                                              */
/* ---------------------------------------------------------------------- */

const SEGMENTS = [
  { value: "general", label: "General" },
  { value: "manufacturing", label: "Manufacturing" },
  { value: "retail", label: "Retail" },
  { value: "technology", label: "Technology" },
  { value: "financial_services", label: "Financial Services" },
  { value: "mining", label: "Mining" },
  { value: "construction", label: "Construction" },
  { value: "healthcare", label: "Healthcare" },
];

const RATIO_CATEGORIES: Record<string, { label: string; keys: string[] }> = {
  liquidity: {
    label: "Liquidity",
    keys: ["current_ratio", "quick_ratio"],
  },
  solvency: {
    label: "Solvency",
    keys: ["debt_to_equity", "interest_coverage", "debt_ratio"],
  },
  profitability: {
    label: "Profitability",
    keys: [
      "gross_margin_pct",
      "operating_margin_pct",
      "net_margin_pct",
      "return_on_equity",
      "return_on_assets",
    ],
  },
  efficiency: {
    label: "Efficiency",
    keys: [
      "asset_turnover",
      "receivable_days",
      "inventory_days",
      "payable_days",
      "cash_conversion_cycle",
    ],
  },
  going_concern: {
    label: "Going Concern",
    keys: ["altman_z_proxy"],
  },
};

const RATIO_LABELS: Record<string, string> = {
  current_ratio: "Current Ratio",
  quick_ratio: "Quick Ratio",
  debt_to_equity: "Debt to Equity",
  interest_coverage: "Interest Coverage",
  debt_ratio: "Debt Ratio",
  gross_margin_pct: "Gross Margin %",
  operating_margin_pct: "Operating Margin %",
  net_margin_pct: "Net Margin %",
  return_on_equity: "Return on Equity %",
  return_on_assets: "Return on Assets %",
  asset_turnover: "Asset Turnover",
  receivable_days: "Receivable Days",
  inventory_days: "Inventory Days",
  payable_days: "Payable Days",
  cash_conversion_cycle: "Cash Conversion Cycle",
  altman_z_proxy: "Altman Z-Score (Proxy)",
};

/* ---------------------------------------------------------------------- */
/*  BenchmarkBar                                                           */
/* ---------------------------------------------------------------------- */

function BenchmarkBar({
  value,
  p25,
  median,
  p75,
}: {
  value: number;
  p25: number;
  median: number;
  p75: number;
}) {
  const min = Math.min(p25 * 0.5, value * 0.8);
  const max = Math.max(p75 * 1.5, value * 1.2);
  const range = max - min || 1;
  const pct = Math.max(0, Math.min(100, ((value - min) / range) * 100));
  const p25Pct = ((p25 - min) / range) * 100;
  const medPct = ((median - min) / range) * 100;
  const p75Pct = ((p75 - min) / range) * 100;
  const inRange = value >= p25 && value <= p75;
  const color =
    inRange
      ? "bg-emerald-400"
      : value < p25 * 0.7 || value > p75 * 1.5
        ? "bg-red-400"
        : "bg-amber-400";

  return (
    <div className="relative h-3 w-full rounded-full bg-va-panel">
      <div
        className="absolute top-0 h-3 rounded-full bg-va-surface"
        style={{ left: `${p25Pct}%`, width: `${p75Pct - p25Pct}%` }}
      />
      <div
        className="absolute top-0 h-3 w-px bg-va-text2"
        style={{ left: `${medPct}%` }}
      />
      <div
        className={`absolute top-0.5 h-2 w-2 rounded-full ${color}`}
        style={{ left: `${pct}%` }}
      />
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/*  Page                                                                   */
/* ---------------------------------------------------------------------- */

export default function AnalyticsPage() {
  const params = useParams();
  const router = useRouter();
  const { toast } = useToast();
  const engagementId = params.id as string;

  const [tenantId, setTenantId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [computing, setComputing] = useState(false);
  const [analytics, setAnalytics] = useState<AFSAnalytics | null>(null);
  const [entityName, setEntityName] = useState("");
  const [segment, setSegment] = useState("general");
  const [error, setError] = useState<string | null>(null);

  /* -------------------------------------------------------------------- */
  /*  Data loading                                                         */
  /* -------------------------------------------------------------------- */

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
        // Get engagement name
        const eng = await api.afs.getEngagement(ctx.tenantId, engagementId);
        if (!cancelled) setEntityName(eng.entity_name);
        // Try to load existing analytics
        try {
          const a = await api.afs.getAnalytics(ctx.tenantId, engagementId);
          if (!cancelled) {
            setAnalytics(a);
            if (a.industry_segment) setSegment(a.industry_segment);
          }
        } catch {
          // No analytics yet — that's fine
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [router, engagementId]);

  /* -------------------------------------------------------------------- */
  /*  Compute handler                                                      */
  /* -------------------------------------------------------------------- */

  async function handleCompute() {
    if (!tenantId) return;
    setComputing(true);
    try {
      const result = await api.afs.computeAnalytics(
        tenantId,
        engagementId,
        { industry_segment: segment },
      );
      setAnalytics(result);
      toast.success("Analytics computed successfully");
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Failed to compute analytics",
      );
    } finally {
      setComputing(false);
    }
  }

  /* -------------------------------------------------------------------- */
  /*  Loading state                                                        */
  /* -------------------------------------------------------------------- */

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <VASpinner />
      </div>
    );
  }

  /* -------------------------------------------------------------------- */
  /*  Render                                                               */
  /* -------------------------------------------------------------------- */

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <button
            onClick={() => router.push(`/afs/${engagementId}/sections`)}
            className="text-sm text-va-blue hover:underline mb-1"
          >
            &larr; Back to Sections
          </button>
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            {entityName} &mdash; Analytics
          </h1>
        </div>
        <div className="flex gap-2">
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
            onClick={() => router.push(`/afs/${engagementId}/consolidation`)}
          >
            Consolidation
          </VAButton>
          <VAButton
            variant="secondary"
            onClick={() => router.push(`/afs/${engagementId}/output`)}
          >
            Output
          </VAButton>
        </div>
      </div>

      {/* Error */}
      {error && (
        <VACard className="p-6">
          <p className="text-sm text-va-danger">{error}</p>
        </VACard>
      )}

      {!error && (
        <>
          {/* Compute Panel */}
          <VACard className="mb-6 p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
              <div className="flex items-end gap-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-va-text">
                    Industry Segment
                  </label>
                  <VASelect
                    value={segment}
                    onChange={(e) => setSegment(e.target.value)}
                  >
                    {SEGMENTS.map((s) => (
                      <option key={s.value} value={s.value}>
                        {s.label}
                      </option>
                    ))}
                  </VASelect>
                </div>
                <VAButton
                  variant="primary"
                  onClick={handleCompute}
                  disabled={computing}
                >
                  {computing ? "Computing..." : "Compute Analytics"}
                </VAButton>
              </div>
              {analytics && (
                <div className="flex items-center gap-3 text-sm text-va-text2">
                  <span>
                    Last computed:{" "}
                    {new Date(analytics.computed_at).toLocaleString()}
                  </span>
                  <VABadge
                    variant={
                      analytics.status === "computed"
                        ? "success"
                        : analytics.status === "stale"
                          ? "warning"
                          : "danger"
                    }
                  >
                    {analytics.status}
                  </VABadge>
                </div>
              )}
            </div>
          </VACard>

          {/* No analytics yet */}
          {!analytics && (
            <VAEmptyState
              icon="chart"
              title="No analytics computed yet"
              description="Select an industry segment and click 'Compute Analytics' to generate financial ratio analysis, benchmarks, and AI insights."
            />
          )}

          {/* Analytics Results */}
          {analytics && (
            <>
              {/* Ratio Cards Grid */}
              <div className="mb-6 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                {Object.entries(RATIO_CATEGORIES).map(([catKey, cat]) => (
                  <VACard key={catKey} className="p-5">
                    <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-va-text2">
                      {cat.label}
                    </h3>
                    <div className="space-y-3">
                      {cat.keys.map((rKey) => {
                        const value = analytics.ratios_json[rKey];
                        const bench = analytics.benchmark_comparison_json[rKey];
                        return (
                          <div key={rKey}>
                            <div className="flex items-center justify-between text-sm">
                              <span className="text-va-text">
                                {RATIO_LABELS[rKey] || rKey}
                              </span>
                              <span className="font-mono font-medium text-va-text">
                                {value != null
                                  ? typeof value === "number"
                                    ? value.toFixed(2)
                                    : value
                                  : "N/A"}
                              </span>
                            </div>
                            {bench && (
                              <div className="mt-1">
                                <BenchmarkBar
                                  value={bench.value}
                                  p25={bench.p25}
                                  median={bench.median}
                                  p75={bench.p75}
                                />
                                <div className="mt-0.5 flex justify-between text-[10px] text-va-muted">
                                  <span>p25: {bench.p25}</span>
                                  <span>med: {bench.median}</span>
                                  <span>p75: {bench.p75}</span>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </VACard>
                ))}
              </div>

              {/* Anomalies */}
              <VACard className="mb-6 p-5">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-va-text2">
                  Anomalies &amp; Alerts
                </h3>
                {(analytics.anomalies_json?.anomalies ?? []).length === 0 ? (
                  <p className="text-sm text-va-muted">
                    No anomalies detected.
                  </p>
                ) : (
                  <div className="space-y-3">
                    {analytics.anomalies_json.anomalies.map((a, i) => (
                      <div
                        key={i}
                        className="rounded-va-sm border border-va-border bg-va-surface p-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <span className="text-sm font-medium text-va-text">
                              {RATIO_LABELS[a.ratio_key] || a.ratio_key}
                            </span>
                            <p className="mt-1 text-sm text-va-text2">
                              {a.description}
                            </p>
                            <p className="mt-1 text-xs text-va-muted">
                              Disclosure impact: {a.disclosure_impact}
                            </p>
                          </div>
                          <VABadge
                            variant={
                              a.severity === "critical"
                                ? "danger"
                                : a.severity === "warning"
                                  ? "warning"
                                  : "default"
                            }
                          >
                            {a.severity}
                          </VABadge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </VACard>

              {/* Management Commentary */}
              <VACard className="mb-6 p-5">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-va-text2">
                  Management Commentary Suggestions
                </h3>
                {!analytics.commentary_json ? (
                  <p className="text-sm text-va-muted">
                    Commentary not available. Re-compute analytics to generate.
                  </p>
                ) : (
                  <div className="grid gap-4 md:grid-cols-3">
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase text-va-blue">
                        Key Highlights
                      </h4>
                      <ul className="space-y-1">
                        {analytics.commentary_json.key_highlights.map(
                          (h, i) => (
                            <li key={i} className="text-sm text-va-text2">
                              &bull; {h}
                            </li>
                          ),
                        )}
                      </ul>
                    </div>
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase text-amber-400">
                        Risk Factors
                      </h4>
                      <ul className="space-y-1">
                        {analytics.commentary_json.risk_factors.map((r, i) => (
                          <li key={i} className="text-sm text-va-text2">
                            &bull; {r}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4 className="mb-2 text-xs font-semibold uppercase text-emerald-400">
                        Outlook
                      </h4>
                      <ul className="space-y-1">
                        {analytics.commentary_json.outlook_points.map(
                          (o, i) => (
                            <li key={i} className="text-sm text-va-text2">
                              &bull; {o}
                            </li>
                          ),
                        )}
                      </ul>
                    </div>
                  </div>
                )}
              </VACard>

              {/* Going Concern */}
              <VACard className="p-5">
                <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-va-text2">
                  Going Concern Assessment
                </h3>
                {!analytics.going_concern_json ? (
                  <p className="text-sm text-va-muted">
                    Going concern assessment not available. Re-compute analytics
                    to generate.
                  </p>
                ) : (
                  <>
                    <div className="mb-4 flex items-center gap-3">
                      <span className="text-sm text-va-text">Risk Level:</span>
                      <VABadge
                        variant={
                          analytics.going_concern_json.risk_level === "low"
                            ? "success"
                            : analytics.going_concern_json.risk_level ===
                                "moderate"
                              ? "warning"
                              : "danger"
                        }
                      >
                        {analytics.going_concern_json.risk_level}
                      </VABadge>
                      <span className="text-sm text-va-text">
                        Disclosure Required:
                      </span>
                      <VABadge
                        variant={
                          analytics.going_concern_json.disclosure_required
                            ? "danger"
                            : "success"
                        }
                      >
                        {analytics.going_concern_json.disclosure_required
                          ? "Yes"
                          : "No"}
                      </VABadge>
                    </div>

                    {analytics.going_concern_json.factors.length > 0 && (
                      <div className="mb-4 overflow-x-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-va-border text-left text-xs uppercase text-va-text2">
                              <th className="py-2 pr-4">Factor</th>
                              <th className="py-2 pr-4">Indicator</th>
                              <th className="py-2">Detail</th>
                            </tr>
                          </thead>
                          <tbody>
                            {analytics.going_concern_json.factors.map(
                              (f, i) => (
                                <tr
                                  key={i}
                                  className="border-b border-va-border/50"
                                >
                                  <td className="py-2 pr-4 text-va-text">
                                    {f.factor}
                                  </td>
                                  <td className="py-2 pr-4">
                                    <VABadge
                                      variant={
                                        f.indicator === "positive"
                                          ? "success"
                                          : f.indicator === "negative"
                                            ? "danger"
                                            : "default"
                                      }
                                    >
                                      {f.indicator}
                                    </VABadge>
                                  </td>
                                  <td className="py-2 text-va-text2">
                                    {f.detail}
                                  </td>
                                </tr>
                              ),
                            )}
                          </tbody>
                        </table>
                      </div>
                    )}

                    <div className="rounded-va-sm border border-va-border bg-va-surface p-3">
                      <span className="text-xs font-semibold uppercase text-va-text2">
                        Recommendation
                      </span>
                      <p className="mt-1 text-sm text-va-text">
                        {analytics.going_concern_json.recommendation}
                      </p>
                    </div>
                  </>
                )}
              </VACard>
            </>
          )}
        </>
      )}
    </main>
  );
}
