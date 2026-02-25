"use client";

import { VACard } from "@/components/ui";

interface DrawRepayPoint {
  month: number;
  amount: number;
}

interface DebtFacility {
  facility_id: string;
  label: string;
  type: string;
  limit: number;
  interest_rate: number;
  draw_schedule?: DrawRepayPoint[];
  repayment_schedule?: DrawRepayPoint[];
  is_cash_plug?: boolean;
}

interface EquityRaise {
  amount: number;
  month: number;
  label?: string;
}

interface DividendsPolicy {
  policy: string;
  value?: number | null;
}

interface FundingConfig {
  equity_raises?: EquityRaise[];
  debt_facilities?: DebtFacility[];
  dividends?: DividendsPolicy | null;
}

function fmt(n: number): string {
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function pct(n: number): string {
  return `${(n * 100).toFixed(2)}%`;
}

export function FundingPanel({ funding }: { funding: FundingConfig | null | undefined }) {
  if (!funding) {
    return <p className="text-sm text-va-text2">No funding configuration.</p>;
  }

  const debts = funding.debt_facilities ?? [];
  const equities = funding.equity_raises ?? [];
  const div = funding.dividends;

  return (
    <div className="space-y-6">
      {/* Debt Facilities */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-va-text">
          Debt Facilities ({debts.length})
        </h3>
        {debts.length === 0 ? (
          <p className="text-sm text-va-text2">None configured.</p>
        ) : (
          <div className="overflow-x-auto rounded-va-lg border border-va-border">
            <table className="w-full text-sm text-va-text">
              <thead>
                <tr className="border-b border-va-border bg-va-surface">
                  <th className="px-3 py-2 text-left font-medium">Label</th>
                  <th className="px-3 py-2 text-left font-medium">Type</th>
                  <th className="px-3 py-2 text-right font-medium">Limit</th>
                  <th className="px-3 py-2 text-right font-medium">Rate</th>
                  <th className="px-3 py-2 text-center font-medium">Cash Plug</th>
                  <th className="px-3 py-2 text-right font-medium">Draws</th>
                  <th className="px-3 py-2 text-right font-medium">Repayments</th>
                </tr>
              </thead>
              <tbody>
                {debts.map((d) => (
                  <tr key={d.facility_id} className="border-b border-va-border/50">
                    <td className="px-3 py-2 font-medium">{d.label}</td>
                    <td className="px-3 py-2 text-va-text2">
                      {d.type.replace(/_/g, " ")}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">{fmt(d.limit)}</td>
                    <td className="px-3 py-2 text-right font-mono">{pct(d.interest_rate)}</td>
                    <td className="px-3 py-2 text-center">
                      {d.is_cash_plug ? (
                        <span className="text-va-blue">Yes</span>
                      ) : (
                        <span className="text-va-text2">No</span>
                      )}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-va-text2">
                      {(d.draw_schedule ?? []).length}
                    </td>
                    <td className="px-3 py-2 text-right font-mono text-va-text2">
                      {(d.repayment_schedule ?? []).length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Equity Raises */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-va-text">
          Equity Raises ({equities.length})
        </h3>
        {equities.length === 0 ? (
          <p className="text-sm text-va-text2">None configured.</p>
        ) : (
          <div className="overflow-x-auto rounded-va-lg border border-va-border">
            <table className="w-full text-sm text-va-text">
              <thead>
                <tr className="border-b border-va-border bg-va-surface">
                  <th className="px-3 py-2 text-left font-medium">Label</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                  <th className="px-3 py-2 text-right font-medium">Month</th>
                </tr>
              </thead>
              <tbody>
                {equities.map((e, i) => (
                  <tr key={i} className="border-b border-va-border/50">
                    <td className="px-3 py-2 font-medium">{e.label ?? `Raise ${i + 1}`}</td>
                    <td className="px-3 py-2 text-right font-mono">{fmt(e.amount)}</td>
                    <td className="px-3 py-2 text-right font-mono">{e.month}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Dividend Policy */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-va-text">Dividend Policy</h3>
        {!div || div.policy === "none" ? (
          <p className="text-sm text-va-text2">No dividends.</p>
        ) : (
          <VACard className="inline-block px-4 py-3">
            <span className="text-sm text-va-text">
              {div.policy === "fixed_amount" && (
                <>Fixed amount: <span className="font-mono font-medium">{fmt(div.value ?? 0)}</span> per period</>
              )}
              {div.policy === "payout_ratio" && (
                <>Payout ratio: <span className="font-mono font-medium">{pct(div.value ?? 0)}</span> of net income</>
              )}
            </span>
          </VACard>
        )}
      </div>
    </div>
  );
}
