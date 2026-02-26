"use client";

import { VACard, VATabs } from "@/components/ui";
import { useState } from "react";
import Link from "next/link";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

interface PeriodRow {
  label: string;
  [key: string]: unknown;
}

interface ConsolidatedRunResult {
  consolidated_is?: { income_statement?: PeriodRow[] };
  consolidated_bs?: { balance_sheet?: PeriodRow[] };
  consolidated_cf?: { cash_flow?: PeriodRow[] };
  consolidated_kpis?: unknown;
  minority_interest?: {
    nci_profit?: number[];
    nci_equity?: number[];
  };
  entity_results?: {
    entity_id: string;
    currency: string;
    ownership_pct: number;
  }[];
  eliminations?: {
    from_entity_id: string;
    to_entity_id: string;
    link_type: string;
    amount_per_period: number[];
  }[];
  fx_rates_used?: Record<string, number | { avg: number; closing: number }>;
  integrity?: {
    warnings?: string[];
    errors?: string[];
  };
}

function fmt(n: number): string {
  if (Number.isNaN(n)) return "\u2014";
  return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function ConsolidatedTable({ title, rows }: { title: string; rows: PeriodRow[] }) {
  if (!rows || rows.length === 0) return null;
  const periodKeys = Object.keys(rows[0] ?? {})
    .filter((k) => k.startsWith("period_"))
    .sort((a, b) => {
      const na = parseInt(a.split("_")[1], 10);
      const nb = parseInt(b.split("_")[1], 10);
      return na - nb;
    });
  return (
    <div className="mb-6">
      <h3 className="mb-2 font-brand text-lg font-medium text-va-text">{title}</h3>
      <div className="overflow-x-auto rounded-va-lg border border-va-border">
        <table className="w-full min-w-[600px] text-sm text-va-text">
          <thead>
            <tr className="border-b border-va-border bg-va-surface">
              <th className="px-3 py-2 text-left font-medium">Line item</th>
              {periodKeys.map((k) => (
                <th key={k} className="px-3 py-2 text-right font-medium font-mono">
                  P{k.split("_")[1]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={row.label || i}
                className={i % 2 === 0 ? "border-b border-va-border/50" : "border-b border-va-border/50 bg-va-surface/50"}
              >
                <td className="px-3 py-2 font-medium">{row.label}</td>
                {periodKeys.map((k) => {
                  const v = typeof row[k] === "number" ? (row[k] as number) : 0;
                  return (
                    <td key={k} className={`px-3 py-2 text-right font-mono ${v < 0 ? "text-va-danger" : ""}`}>
                      {fmt(v)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function ConsolidatedResults({
  result,
  entityRunMap,
}: {
  result: ConsolidatedRunResult;
  entityRunMap?: Record<string, string>;
}) {
  const [activeTab, setActiveTab] = useState("statements");

  const isRows = result.consolidated_is?.income_statement ?? [];
  const bsRows = result.consolidated_bs?.balance_sheet ?? [];
  const cfRows = result.consolidated_cf?.cash_flow ?? [];
  const nci = result.minority_interest;
  const entities = result.entity_results ?? [];
  const elims = result.eliminations ?? [];
  const fxRates = result.fx_rates_used ?? {};
  const integrity = result.integrity ?? {};

  const nciChartData = (nci?.nci_profit ?? []).map((v, i) => ({ period: `P${i}`, nci_profit: v }));

  // Determine whether fx_rates_used values are objects with avg/closing or plain numbers
  const fxEntries = Object.entries(fxRates);
  const hasStructuredRates = fxEntries.length > 0 && typeof fxEntries[0][1] === "object" && fxEntries[0][1] !== null;

  return (
    <VATabs
      activeId={activeTab}
      onSelect={setActiveTab}
      tabs={[
        {
          id: "statements",
          label: "Statements",
          content: (
            <div>
              <ConsolidatedTable title="Consolidated Income Statement" rows={isRows} />
              <ConsolidatedTable title="Consolidated Balance Sheet" rows={bsRows} />
              <ConsolidatedTable title="Consolidated Cash Flow" rows={cfRows} />
              {isRows.length === 0 && bsRows.length === 0 && cfRows.length === 0 && (
                <p className="text-sm text-va-text2">No consolidated statement data.</p>
              )}
            </div>
          ),
        },
        {
          id: "entities",
          label: "Entity Breakdown",
          content: (
            <div>
              {entities.length === 0 ? (
                <p className="text-sm text-va-text2">No entity data.</p>
              ) : (
                <div className="overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">Entity</th>
                        <th className="px-3 py-2 text-left font-medium">Currency</th>
                        <th className="px-3 py-2 text-right font-medium">Ownership</th>
                      </tr>
                    </thead>
                    <tbody>
                      {entities.map((e) => {
                        const runId = entityRunMap?.[e.entity_id];
                        return (
                          <tr
                            key={e.entity_id}
                            className={`border-b border-va-border/50${runId ? " cursor-pointer hover:bg-va-surface/50" : ""}`}
                          >
                            <td className="px-3 py-2 font-medium">
                              {runId ? (
                                <Link href={"/runs/" + runId} role="link">
                                  {e.entity_id}
                                </Link>
                              ) : (
                                e.entity_id
                              )}
                            </td>
                            <td className="px-3 py-2 text-va-text2">{e.currency}</td>
                            <td className="px-3 py-2 text-right font-mono">{e.ownership_pct}%</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ),
        },
        {
          id: "nci",
          label: "NCI",
          content: (
            <div className="space-y-4">
              {(!nci || (!nci.nci_profit?.some((v) => v !== 0) && !nci.nci_equity?.some((v) => v !== 0))) ? (
                <p className="text-sm text-va-text2">No non-controlling interest (all entities 100% owned).</p>
              ) : (
                <>
                  {nci?.nci_profit && nci.nci_profit.some((v) => v !== 0) && (
                    <div>
                      <h4 className="mb-1 text-sm font-medium text-va-text">NCI Share of Profit</h4>
                      <div className="flex flex-wrap gap-2">
                        {nci.nci_profit.map((v, i) => (
                          <VACard key={i} className="px-3 py-2 text-center">
                            <p className="text-xs text-va-text2">P{i}</p>
                            <p className="font-mono text-sm text-va-text">{fmt(v)}</p>
                          </VACard>
                        ))}
                      </div>
                      {nciChartData.length > 1 && (
                        <div className="mt-4">
                          <ResponsiveContainer width="100%" height={200}>
                            <LineChart data={nciChartData}>
                              <XAxis dataKey="period" />
                              <YAxis />
                              <Tooltip />
                              <Line type="monotone" dataKey="nci_profit" stroke="#6366f1" strokeWidth={2} />
                            </LineChart>
                          </ResponsiveContainer>
                        </div>
                      )}
                    </div>
                  )}
                  {nci?.nci_equity && nci.nci_equity.some((v) => v !== 0) && (
                    <div>
                      <h4 className="mb-1 text-sm font-medium text-va-text">NCI Share of Equity</h4>
                      <div className="flex flex-wrap gap-2">
                        {nci.nci_equity.map((v, i) => (
                          <VACard key={i} className="px-3 py-2 text-center">
                            <p className="text-xs text-va-text2">P{i}</p>
                            <p className="font-mono text-sm text-va-text">{fmt(v)}</p>
                          </VACard>
                        ))}
                      </div>
                    </div>
                  )}
                  <div>
                    <h4 className="mb-1 text-sm font-medium text-va-text">NCI Entities</h4>
                    <ul className="text-sm text-va-text2">
                      {entities
                        .filter((e) => e.ownership_pct < 100)
                        .map((e) => (
                          <li key={e.entity_id}>
                            {e.entity_id}: {e.ownership_pct}% owned ({100 - e.ownership_pct}% NCI)
                          </li>
                        ))}
                    </ul>
                  </div>
                </>
              )}
            </div>
          ),
        },
        {
          id: "eliminations",
          label: "IC Eliminations",
          content: (
            <div>
              {elims.length === 0 ? (
                <p className="text-sm text-va-text2">No intercompany eliminations.</p>
              ) : (
                <div className="overflow-x-auto rounded-va-lg border border-va-border">
                  <table className="w-full text-sm text-va-text">
                    <thead>
                      <tr className="border-b border-va-border bg-va-surface">
                        <th className="px-3 py-2 text-left font-medium">From</th>
                        <th className="px-3 py-2 text-left font-medium">To</th>
                        <th className="px-3 py-2 text-left font-medium">Type</th>
                        <th className="px-3 py-2 text-right font-medium">Total Eliminated</th>
                      </tr>
                    </thead>
                    <tbody>
                      {elims.map((e, i) => {
                        const total = (e.amount_per_period ?? []).reduce((s, v) => s + v, 0);
                        return (
                          <tr key={i} className="border-b border-va-border/50">
                            <td className="px-3 py-2">{e.from_entity_id}</td>
                            <td className="px-3 py-2">{e.to_entity_id}</td>
                            <td className="px-3 py-2 text-va-text2">{e.link_type.replace(/_/g, " ")}</td>
                            <td className="px-3 py-2 text-right font-mono">{fmt(total)}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                    <tfoot>
                      <tr className="border-t-2 border-va-border bg-va-surface font-medium">
                        <td colSpan={3} className="px-3 py-2">Total</td>
                        <td className="px-3 py-2 text-right font-mono">
                          {fmt(elims.reduce((s, e) => s + (e.amount_per_period ?? []).reduce((a, b) => a + b, 0), 0))}
                        </td>
                      </tr>
                    </tfoot>
                  </table>
                </div>
              )}
            </div>
          ),
        },
        {
          id: "fx",
          label: "FX & Integrity",
          content: (
            <div className="space-y-4">
              <div>
                <h4 className="mb-1 text-sm font-medium text-va-text">FX Rates Used</h4>
                {fxEntries.length === 0 ? (
                  <p className="text-sm text-va-text2">No FX rates (single-currency group).</p>
                ) : (
                  <div className="overflow-x-auto rounded-va-lg border border-va-border">
                    <table className="w-full text-sm text-va-text">
                      <thead>
                        <tr className="border-b border-va-border bg-va-surface">
                          <th className="px-3 py-2 text-left font-medium">Pair</th>
                          {hasStructuredRates ? (
                            <>
                              <th className="px-3 py-2 text-right font-medium">Avg Rate</th>
                              <th className="px-3 py-2 text-right font-medium">Closing Rate</th>
                            </>
                          ) : (
                            <th className="px-3 py-2 text-right font-medium">Rate</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {fxEntries.map(([pair, rate]) => (
                          <tr key={pair} className="border-b border-va-border/50">
                            <td className="px-3 py-2 font-mono">{pair}</td>
                            {hasStructuredRates && typeof rate === "object" && rate !== null ? (
                              <>
                                <td className="px-3 py-2 text-right font-mono">
                                  {(rate as { avg: number; closing: number }).avg.toFixed(4)}
                                </td>
                                <td className="px-3 py-2 text-right font-mono">
                                  {(rate as { avg: number; closing: number }).closing.toFixed(4)}
                                </td>
                              </>
                            ) : (
                              <td className="px-3 py-2 text-right font-mono">
                                {typeof rate === "number" ? rate.toFixed(4) : String(rate)}
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
              <div>
                <h4 className="mb-1 text-sm font-medium text-va-text">Integrity</h4>
                {(integrity.errors ?? []).length > 0 && (
                  <div className="mb-2 rounded-va-xs border border-va-danger/50 bg-va-danger/10 px-3 py-2 text-sm text-va-danger">
                    <strong>Errors:</strong>
                    <ul className="mt-1 list-disc pl-4">
                      {integrity.errors!.map((e, i) => <li key={i}>{e}</li>)}
                    </ul>
                  </div>
                )}
                {(integrity.warnings ?? []).length > 0 && (
                  <div className="rounded-va-xs border border-va-warning/50 bg-va-warning/10 px-3 py-2 text-sm text-va-warning">
                    <strong>Warnings:</strong>
                    <ul className="mt-1 list-disc pl-4">
                      {integrity.warnings!.map((w, i) => <li key={i}>{w}</li>)}
                    </ul>
                  </div>
                )}
                {(integrity.errors ?? []).length === 0 && (integrity.warnings ?? []).length === 0 && (
                  <p className="text-sm text-va-success">All checks passed.</p>
                )}
              </div>
            </div>
          ),
        },
      ]}
    />
  );
}
