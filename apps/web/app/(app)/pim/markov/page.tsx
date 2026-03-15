"use client";

import { VABadge, VACard, VASpinner } from "@/components/ui";
import {
  api,
  type PimMarkovSteadyStateResponse,
  type PimMarkovTopTransitionsResponse,
} from "@/lib/api";
import { getAuthContext } from "@/lib/auth";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { MarkovGraph } from "./MarkovGraph";

// ---------------------------------------------------------------------------
// Steady-state bar chart
// ---------------------------------------------------------------------------

function SteadyStateChart({ topStates }: { topStates: PimMarkovSteadyStateResponse["top_states"] }) {
  const data = topStates.map((s) => ({
    label: s.label.split("/").slice(0, 2).join("/"),
    probability: parseFloat((s.probability * 100).toFixed(2)),
  }));

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 120 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
        <XAxis
          type="number"
          tick={{ fill: "#94a3b8", fontSize: 11 }}
          tickFormatter={(v: number) => `${v.toFixed(1)}%`}
        />
        <YAxis type="category" dataKey="label" tick={{ fill: "#94a3b8", fontSize: 10 }} width={115} />
        <Tooltip
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          formatter={(v: any) => [`${Number(v).toFixed(2)}%`, "Steady-state"]}
          contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 6 }}
          labelStyle={{ color: "#94a3b8" }}
        />
        <Bar dataKey="probability" fill="#3b82f6" radius={[0, 3, 3, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function MarkovPage() {
  const [tenantId, setTenantId] = useState<string | null>(null);
  const [steadyState, setSteadyState] = useState<PimMarkovSteadyStateResponse | null>(null);
  const [transitions, setTransitions] = useState<PimMarkovTopTransitionsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuthContext().then(async (ctx) => {
      if (!ctx) {
        window.location.href = "/login";
        return;
      }
      api.setAccessToken(ctx.accessToken);
      setTenantId(ctx.tenantId);

      try {
        const [ss, tx] = await Promise.all([
          api.pim.markov.steadyState(ctx.tenantId),
          api.pim.markov.topTransitions(ctx.tenantId, 8),
        ]);
        setSteadyState(ss);
        setTransitions(tx);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    });
  }, []);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <Link href="/pim" className="mb-2 flex items-center gap-1 text-sm text-va-text2 hover:text-va-text">
          ← Portfolio Intelligence
        </Link>
        <h1 className="font-brand text-2xl font-semibold tracking-tight text-va-text">
          Markov State Diagram
        </h1>
        <p className="mt-1 text-sm text-va-text2">
          81-state Markov chain over GDP, sentiment, quality, and momentum dimensions.
          Steady-state probabilities show long-run frequency of each regime.
        </p>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-20">
          <VASpinner />
        </div>
      )}

      {error && !loading && (
        <VACard className="p-6">
          <p className="text-sm text-red-400">{error}</p>
          <p className="mt-2 text-xs text-va-text2">
            {error.includes("No Markov matrix")
              ? "Run a CIS computation with historical data to build the Markov transition matrix."
              : "Check API connectivity and retry."}
          </p>
        </VACard>
      )}

      {!loading && !error && steadyState && transitions && (
        <div className="space-y-6">
          {/* Metadata badges */}
          <VACard className="p-6">
            <div className="flex flex-wrap items-center gap-3">
              <VABadge variant={steadyState.is_ergodic ? "success" : "default"}>
                {steadyState.is_ergodic ? "Ergodic" : "Non-ergodic"}
              </VABadge>
              <VABadge variant="default">{steadyState.n_observations} observations</VABadge>
              {!steadyState.quantecon_available && (
                <VABadge variant="warning">Power-iteration (QuantEcon unavailable)</VABadge>
              )}
            </div>
            <p className="mt-3 text-xs text-va-text2">{steadyState.limitations}</p>
          </VACard>

          {/* State transition diagram */}
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              State Transition Diagram
            </h2>
            <p className="mb-4 text-xs text-va-text2">
              Top-{steadyState.top_states.length} states by steady-state probability.
              Arrows show transitions with probability &gt; 5%.
            </p>
            <MarkovGraph steadyState={steadyState} transitions={transitions} />
          </VACard>

          {/* Steady-state bar chart */}
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              Steady-State Distribution
            </h2>
            <p className="mb-3 text-xs text-va-text2">
              Long-run probability of each state. Label shows GDP/sentiment dimensions.
            </p>
            <SteadyStateChart topStates={steadyState.top_states} />
          </VACard>

          {/* Top transitions table */}
          <VACard className="p-6">
            <h2 className="mb-4 text-base font-medium text-va-text">
              Highest-Probability Transitions
            </h2>
            <div className="overflow-x-auto rounded-va-lg border border-va-border">
              <table className="w-full text-sm text-va-text">
                <thead>
                  <tr className="border-b border-va-border bg-va-surface">
                    <th className="px-4 py-3 text-left font-medium">From State</th>
                    <th className="px-4 py-3 text-left font-medium">To State</th>
                    <th className="px-4 py-3 text-right font-medium">Probability</th>
                  </tr>
                </thead>
                <tbody>
                  {transitions.edges.slice(0, 15).map((e) => (
                    <tr
                      key={`${e.from_state}-${e.to_state}`}
                      className="border-b border-va-border last:border-0"
                    >
                      <td className="px-4 py-2 font-mono text-xs text-va-text2">{e.from_label}</td>
                      <td className="px-4 py-2 font-mono text-xs text-va-text2">{e.to_label}</td>
                      <td className="px-4 py-2 text-right font-mono">
                        {(e.probability * 100).toFixed(2)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </VACard>
        </div>
      )}
    </main>
  );
}
