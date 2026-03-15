"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { VACard, VABadge, VASpinner } from "@/components/ui";
import { api, type PimEconomicSnapshot } from "@/lib/api";
import { getAuthContext } from "@/lib/auth";

// -------------------------------------------------------------------------
// Helpers
// -------------------------------------------------------------------------

function fmt(value: number | null, decimals = 1, suffix = "%"): string {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(decimals)}${suffix}`;
}

function regimeBadgeVariant(
  regime: string
): "success" | "danger" | "warning" {
  if (regime === "expansion") return "success";
  if (regime === "contraction") return "danger";
  return "warning";
}

function regimeLabel(regime: string): string {
  return regime.charAt(0).toUpperCase() + regime.slice(1);
}

interface IndicatorRowProps {
  label: string;
  value: number | null;
  format?: (v: number | null) => string;
}

function IndicatorRow({ label, value, format }: IndicatorRowProps) {
  const display = format ? format(value) : fmt(value);
  return (
    <div className="flex items-center justify-between py-2 border-b border-va-border last:border-0">
      <span className="text-sm text-va-text2">{label}</span>
      <span className="font-mono text-sm text-va-text">
        {display}
      </span>
    </div>
  );
}

// -------------------------------------------------------------------------
// Page
// -------------------------------------------------------------------------

export default function EconomicContextPage() {
  const router = useRouter();
  const [current, setCurrent] = useState<PimEconomicSnapshot | null>(null);
  const [history, setHistory] = useState<PimEconomicSnapshot[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const ctx = await getAuthContext();
      if (!ctx) {
        router.replace("/login");
        return;
      }
      api.setAccessToken(ctx.accessToken);

      try {
        const tenantId = ctx.tenantId;
        const [currentRes, historyRes] = await Promise.all([
          api.pim.economic.current(tenantId),
          api.pim.economic.snapshots(tenantId, { limit: 12 }),
        ]);
        if (!cancelled) {
          setCurrent(currentRes);
          setHistory(historyRes.snapshots ?? []);
        }
      } catch (e: unknown) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : "Failed to load economic data";
          setError(msg);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load().catch(() => setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [router]);

  // --- Loading ---
  if (loading) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="flex items-center gap-3 text-va-text2">
          <VASpinner />
          <span>Loading economic context…</span>
        </div>
      </main>
    );
  }

  // --- Error ---
  if (error) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <VACard className="border-red-500/30 bg-red-950/20 p-6">
          <p className="text-sm text-red-400">{error}</p>
        </VACard>
      </main>
    );
  }

  // --- Empty ---
  if (!current) {
    return (
      <main className="mx-auto max-w-5xl px-4 py-8">
        <div className="mb-6">
          <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
            Economic Context
          </h1>
          <p className="mt-1 text-sm text-va-text2">
            Macroeconomic regime and FRED indicator dashboard.
          </p>
        </div>
        <VACard className="p-6 text-center">
          <p className="text-sm text-va-text2">
            No economic snapshot available. The monthly FRED refresh has not
            run yet — check back after the first scheduled sync.
          </p>
        </VACard>
      </main>
    );
  }

  const updatedAt = new Date(current.fetched_at).toLocaleDateString("en-ZA", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
              Economic Context
            </h1>
            <p className="mt-1 text-sm text-va-text2">
              Macroeconomic regime and FRED indicator dashboard. Updated{" "}
              {updatedAt}.
            </p>
          </div>
          <VABadge variant={regimeBadgeVariant(current.regime)}>
            {regimeLabel(current.regime)}
          </VABadge>
        </div>
      </div>

      {/* Current snapshot cards */}
      <div className="mb-8 grid grid-cols-1 gap-4 md:grid-cols-2">
        {/* Regime summary */}
        <VACard className="p-6">
          <h2 className="mb-1 text-sm font-medium text-va-text2 uppercase tracking-wide">
            Current Regime
          </h2>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="font-brand text-3xl font-bold text-va-text">
              {regimeLabel(current.regime)}
            </span>
            <span className="text-sm text-va-text2">
              {(current.regime_confidence * 100).toFixed(0)}% confidence
            </span>
          </div>
          <p className="mt-2 text-xs text-va-text2">
            {current.indicators_agreeing} of {current.indicators_total}{" "}
            indicators consistent with regime classification.
          </p>
        </VACard>

        {/* FRED indicators */}
        <VACard className="p-6">
          <h2 className="mb-3 text-sm font-medium text-va-text2 uppercase tracking-wide">
            FRED Indicators
          </h2>
          <IndicatorRow
            label="Real GDP Growth (QoQ)"
            value={current.gdp_growth_pct}
          />
          <IndicatorRow
            label="CPI Inflation (YoY)"
            value={current.cpi_yoy_pct}
          />
          <IndicatorRow
            label="Unemployment Rate"
            value={current.unemployment_rate}
          />
          <IndicatorRow
            label="10Y–2Y Yield Spread"
            value={current.yield_spread_10y2y}
            format={(v) => fmt(v, 2, "%")}
          />
          <IndicatorRow
            label="ISM PMI"
            value={current.ism_pmi}
            format={(v) => fmt(v, 1, "")}
          />
        </VACard>
      </div>

      {/* Regime timeline */}
      {history.length > 1 && (
        <VACard className="p-6">
          <h2 className="mb-4 text-sm font-medium text-va-text2 uppercase tracking-wide">
            Regime Timeline (last {history.length} snapshots)
          </h2>
          <div className="flex flex-wrap gap-2">
            {history.map((snap) => {
              const month = new Date(snap.fetched_at).toLocaleDateString(
                "en-ZA",
                { year: "2-digit", month: "short" }
              );
              return (
                <div
                  key={snap.snapshot_id}
                  className="flex flex-col items-center gap-1"
                >
                  <VABadge variant={regimeBadgeVariant(snap.regime)}>
                    {regimeLabel(snap.regime).slice(0, 3)}
                  </VABadge>
                  <span className="text-xs text-va-text2">{month}</span>
                </div>
              );
            })}
          </div>
        </VACard>
      )}

      {/* Limitations disclosure — SR-6 */}
      <p className="mt-6 text-xs text-va-text2/60">
        Economic regime classification is a statistical model-based estimate
        derived from FRED macroeconomic data. It does not constitute investment
        advice. Regime signals reflect historical indicator thresholds and may
        lag real economic turning points.
      </p>
    </main>
  );
}
