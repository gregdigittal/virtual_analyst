"use client";

import { useState } from "react";
import { VAInput, VASelect, VAButton, VAConfirmDialog } from "@/components/ui";

/* ── Type interfaces (mirrored from FundingPanel) ──────────────────── */

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

/* ── Validated numeric input ───────────────────────────────────────── */

/**
 * A number input that uses local state for editing and calls onChange/onBlur
 * with the parsed value. This prevents controlled-component issues where
 * a mock onChange prevents the DOM value from updating.
 */
function NumericField({
  value,
  onCommit,
  error,
  step,
  className = "",
}: {
  value: number;
  onCommit: (val: number) => void;
  error?: string;
  step?: string;
  className?: string;
}) {
  const [localValue, setLocalValue] = useState<string>(String(value));
  const [focused, setFocused] = useState(false);

  // Sync from props when not focused
  const displayValue = focused ? localValue : String(value);

  return (
    <VAInput
      type="number"
      step={step}
      className={className}
      value={displayValue}
      error={error}
      onChange={(e) => {
        setLocalValue(e.target.value);
        const num = parseFloat(e.target.value);
        if (!isNaN(num)) onCommit(num);
      }}
      onFocus={() => {
        setLocalValue(String(value));
        setFocused(true);
      }}
      onBlur={(e) => {
        setFocused(false);
        const num = parseFloat(e.target.value);
        if (!isNaN(num)) onCommit(num);
      }}
    />
  );
}

/* ── Validation helpers ────────────────────────────────────────────── */

interface FieldErrors {
  [facilityId: string]: {
    interest_rate?: string;
    limit?: string;
    draw_amounts?: string;
  };
}

function validateFacility(facility: DebtFacility): FieldErrors[string] {
  const errors: FieldErrors[string] = {};
  if (facility.interest_rate < 0 || facility.interest_rate > 1) {
    errors.interest_rate = "Must be between 0 and 1";
  }
  if (facility.limit < 0) {
    errors.limit = "Must be > 0";
  }
  const totalDraws = (facility.draw_schedule ?? []).reduce(
    (sum, d) => sum + d.amount,
    0,
  );
  if (totalDraws > facility.limit && facility.limit > 0) {
    errors.draw_amounts = "Draw amounts exceed facility limit";
  }
  return errors;
}

/* ── Component ─────────────────────────────────────────────────────── */

interface FundingEditorProps {
  funding: FundingConfig | null;
  onChange: (f: FundingConfig) => void;
}

export function FundingEditor({ funding, onChange }: FundingEditorProps) {
  const config: FundingConfig = funding ?? {
    debt_facilities: [],
    equity_raises: [],
    dividends: null,
  };

  const debts = config.debt_facilities ?? [];
  const equities = config.equity_raises ?? [];
  const div = config.dividends;

  const [expandedFacility, setExpandedFacility] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  /* ── Debt helpers ─────────────────────────────────────────────── */

  function emitUpdate(nextDebts: DebtFacility[]) {
    onChange({ ...config, debt_facilities: nextDebts });
  }

  function updateFacility(idx: number, patch: Partial<DebtFacility>) {
    const next = debts.map((d, i) => (i === idx ? { ...d, ...patch } : d));
    const updated = next[idx];
    // Run validation whenever a facility field changes
    const errors = validateFacility(updated);
    setFieldErrors((prev) => ({ ...prev, [updated.facility_id]: errors }));
    emitUpdate(next);
  }

  function addFacility() {
    const newFacility: DebtFacility = {
      facility_id: crypto.randomUUID(),
      label: "",
      type: "term_loan",
      limit: 0,
      interest_rate: 0,
      draw_schedule: [],
      repayment_schedule: [],
      is_cash_plug: false,
    };
    onChange({ ...config, debt_facilities: [...debts, newFacility] });
  }

  function removeFacility(facilityId: string) {
    onChange({
      ...config,
      debt_facilities: debts.filter((d) => d.facility_id !== facilityId),
    });
    setDeleteTarget(null);
    setFieldErrors((prev) => {
      const next = { ...prev };
      delete next[facilityId];
      return next;
    });
  }

  /* ── Schedule helpers ─────────────────────────────────────────── */

  function updateDrawPoint(
    facilityIdx: number,
    pointIdx: number,
    patch: Partial<DrawRepayPoint>,
  ) {
    const facility = debts[facilityIdx];
    const schedule = (facility.draw_schedule ?? []).map((p, i) =>
      i === pointIdx ? { ...p, ...patch } : p,
    );
    updateFacility(facilityIdx, { draw_schedule: schedule });
  }

  function addDrawPoint(facilityIdx: number) {
    const facility = debts[facilityIdx];
    const schedule = [...(facility.draw_schedule ?? []), { month: 0, amount: 0 }];
    updateFacility(facilityIdx, { draw_schedule: schedule });
  }

  function removeDrawPoint(facilityIdx: number, pointIdx: number) {
    const facility = debts[facilityIdx];
    const schedule = (facility.draw_schedule ?? []).filter(
      (_, i) => i !== pointIdx,
    );
    updateFacility(facilityIdx, { draw_schedule: schedule });
  }

  function updateRepayPoint(
    facilityIdx: number,
    pointIdx: number,
    patch: Partial<DrawRepayPoint>,
  ) {
    const facility = debts[facilityIdx];
    const schedule = (facility.repayment_schedule ?? []).map((p, i) =>
      i === pointIdx ? { ...p, ...patch } : p,
    );
    updateFacility(facilityIdx, { repayment_schedule: schedule });
  }

  function addRepayPoint(facilityIdx: number) {
    const facility = debts[facilityIdx];
    const schedule = [
      ...(facility.repayment_schedule ?? []),
      { month: 0, amount: 0 },
    ];
    updateFacility(facilityIdx, { repayment_schedule: schedule });
  }

  function removeRepayPoint(facilityIdx: number, pointIdx: number) {
    const facility = debts[facilityIdx];
    const schedule = (facility.repayment_schedule ?? []).filter(
      (_, i) => i !== pointIdx,
    );
    updateFacility(facilityIdx, { repayment_schedule: schedule });
  }

  /* ── Equity helpers ───────────────────────────────────────────── */

  function updateEquity(idx: number, patch: Partial<EquityRaise>) {
    const next = equities.map((e, i) => (i === idx ? { ...e, ...patch } : e));
    onChange({ ...config, equity_raises: next });
  }

  function addEquity() {
    onChange({
      ...config,
      equity_raises: [...equities, { label: "", amount: 0, month: 0 }],
    });
  }

  function removeEquity(idx: number) {
    onChange({
      ...config,
      equity_raises: equities.filter((_, i) => i !== idx),
    });
  }

  /* ── Dividend helpers ─────────────────────────────────────────── */

  function setDividendPolicy(policy: string) {
    if (policy === "none") {
      onChange({ ...config, dividends: { policy: "none" } });
    } else {
      onChange({
        ...config,
        dividends: { policy, value: div?.value ?? 0 },
      });
    }
  }

  function setDividendValue(value: number) {
    onChange({
      ...config,
      dividends: { policy: div?.policy ?? "fixed_amount", value },
    });
  }

  const currentPolicy = div?.policy ?? "none";

  /* ── Render ───────────────────────────────────────────────────── */

  return (
    <div className="space-y-8">
      {/* ── Debt Facilities ─────────────────────────────────────── */}
      <section>
        <h3 className="mb-3 text-sm font-brand font-medium text-va-text">
          Debt Facilities ({debts.length})
        </h3>

        {debts.length === 0 ? (
          <p className="text-sm text-va-text2">No debt facilities configured.</p>
        ) : (
          <div className="space-y-3">
            {debts.map((facility, idx) => {
              const errors = fieldErrors[facility.facility_id] ?? {};
              const isExpanded = expandedFacility === facility.facility_id;

              return (
                <div
                  key={facility.facility_id}
                  className="rounded-va-lg border border-va-border bg-va-surface p-4"
                >
                  {/* Main row */}
                  <div className="flex flex-wrap items-start gap-3">
                    <button
                      type="button"
                      title="expand"
                      className="mt-2 text-va-text2 hover:text-va-text transition"
                      onClick={() =>
                        setExpandedFacility(isExpanded ? null : facility.facility_id)
                      }
                    >
                      <svg
                        className={`h-4 w-4 transition-transform ${isExpanded ? "rotate-90" : ""}`}
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                        strokeWidth={2}
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          d="M9 5l7 7-7 7"
                        />
                      </svg>
                    </button>

                    <div className="min-w-[140px] flex-1">
                      <label className="mb-1 block text-xs font-medium text-va-text2">
                        Label
                      </label>
                      <VAInput
                        value={facility.label}
                        onChange={(e) =>
                          updateFacility(idx, { label: e.target.value })
                        }
                        placeholder="Facility name"
                      />
                    </div>

                    <div className="min-w-[120px]">
                      <label className="mb-1 block text-xs font-medium text-va-text2">
                        Type
                      </label>
                      <VASelect
                        value={facility.type}
                        onChange={(e) =>
                          updateFacility(idx, { type: e.target.value })
                        }
                      >
                        <option value="term_loan">Term Loan</option>
                        <option value="revolver">Revolver</option>
                        <option value="rcf">RCF</option>
                        <option value="bridge">Bridge</option>
                      </VASelect>
                    </div>

                    <div className="min-w-[120px]">
                      <label className="mb-1 block text-xs font-medium text-va-text2">
                        Limit
                      </label>
                      <NumericField
                        value={facility.limit}
                        className="font-mono"
                        error={errors.limit}
                        onCommit={(val) =>
                          updateFacility(idx, { limit: val })
                        }
                      />
                    </div>

                    <div className="min-w-[100px]">
                      <label className="mb-1 block text-xs font-medium text-va-text2">
                        Interest Rate
                      </label>
                      <NumericField
                        value={facility.interest_rate}
                        step="0.01"
                        className="font-mono"
                        error={errors.interest_rate}
                        onCommit={(val) =>
                          updateFacility(idx, { interest_rate: val })
                        }
                      />
                    </div>

                    <div className="flex items-end gap-2 self-end pb-1">
                      <label className="flex items-center gap-1.5 text-xs text-va-text2">
                        <input
                          type="checkbox"
                          checked={facility.is_cash_plug ?? false}
                          onChange={(e) =>
                            updateFacility(idx, {
                              is_cash_plug: e.target.checked,
                            })
                          }
                          className="rounded border-va-border"
                        />
                        Cash Plug
                      </label>

                      <VAButton
                        variant="ghost"
                        className="text-va-danger hover:text-va-danger/80"
                        onClick={() => setDeleteTarget(facility.facility_id)}
                      >
                        Delete
                      </VAButton>
                    </div>
                  </div>

                  {/* Expanded sub-tables */}
                  {isExpanded && (
                    <div className="mt-4 space-y-4 border-t border-va-border pt-4">
                      {/* Draw Schedule */}
                      <div>
                        <h4 className="mb-2 text-xs font-medium text-va-text">
                          Draw Schedule
                        </h4>
                        {(facility.draw_schedule ?? []).length === 0 ? (
                          <p className="text-xs text-va-text2">No draws.</p>
                        ) : (
                          <div className="space-y-2">
                            {(facility.draw_schedule ?? []).map((pt, pi) => (
                              <div key={pi} className="flex items-center gap-2">
                                <div className="w-24">
                                  <label className="mb-0.5 block text-[10px] text-va-text2">
                                    Month
                                  </label>
                                  <VAInput
                                    type="number"
                                    className="font-mono text-xs"
                                    value={pt.month}
                                    onChange={(e) =>
                                      updateDrawPoint(idx, pi, {
                                        month: parseInt(e.target.value) || 0,
                                      })
                                    }
                                  />
                                </div>
                                <div className="w-32">
                                  <label className="mb-0.5 block text-[10px] text-va-text2">
                                    Amount
                                  </label>
                                  <VAInput
                                    type="number"
                                    className="font-mono text-xs"
                                    value={pt.amount}
                                    onChange={(e) =>
                                      updateDrawPoint(idx, pi, {
                                        amount: parseFloat(e.target.value) || 0,
                                      })
                                    }
                                  />
                                </div>
                                <VAButton
                                  variant="ghost"
                                  className="mt-3 text-xs text-va-danger"
                                  onClick={() => removeDrawPoint(idx, pi)}
                                >
                                  Remove
                                </VAButton>
                              </div>
                            ))}
                          </div>
                        )}
                        {errors.draw_amounts && (
                          <p className="mt-1 text-xs text-va-danger">
                            {errors.draw_amounts}
                          </p>
                        )}
                        <VAButton
                          variant="ghost"
                          className="mt-2 text-xs"
                          onClick={() => addDrawPoint(idx)}
                        >
                          + Add Draw
                        </VAButton>
                      </div>

                      {/* Repayment Schedule */}
                      <div>
                        <h4 className="mb-2 text-xs font-medium text-va-text">
                          Repayment Schedule
                        </h4>
                        {(facility.repayment_schedule ?? []).length === 0 ? (
                          <p className="text-xs text-va-text2">No repayments.</p>
                        ) : (
                          <div className="space-y-2">
                            {(facility.repayment_schedule ?? []).map((pt, pi) => (
                              <div key={pi} className="flex items-center gap-2">
                                <div className="w-24">
                                  <label className="mb-0.5 block text-[10px] text-va-text2">
                                    Month
                                  </label>
                                  <VAInput
                                    type="number"
                                    className="font-mono text-xs"
                                    value={pt.month}
                                    onChange={(e) =>
                                      updateRepayPoint(idx, pi, {
                                        month: parseInt(e.target.value) || 0,
                                      })
                                    }
                                  />
                                </div>
                                <div className="w-32">
                                  <label className="mb-0.5 block text-[10px] text-va-text2">
                                    Amount
                                  </label>
                                  <VAInput
                                    type="number"
                                    className="font-mono text-xs"
                                    value={pt.amount}
                                    onChange={(e) =>
                                      updateRepayPoint(idx, pi, {
                                        amount: parseFloat(e.target.value) || 0,
                                      })
                                    }
                                  />
                                </div>
                                <VAButton
                                  variant="ghost"
                                  className="mt-3 text-xs text-va-danger"
                                  onClick={() => removeRepayPoint(idx, pi)}
                                >
                                  Remove
                                </VAButton>
                              </div>
                            ))}
                          </div>
                        )}
                        <VAButton
                          variant="ghost"
                          className="mt-2 text-xs"
                          onClick={() => addRepayPoint(idx)}
                        >
                          + Add Repayment
                        </VAButton>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        <VAButton variant="secondary" className="mt-3" onClick={addFacility}>
          + Add Facility
        </VAButton>
      </section>

      {/* ── Equity Raises ───────────────────────────────────────── */}
      <section>
        <h3 className="mb-3 text-sm font-brand font-medium text-va-text">
          Equity Raises ({equities.length})
        </h3>

        {equities.length === 0 ? (
          <p className="text-sm text-va-text2">No equity raises configured.</p>
        ) : (
          <div className="overflow-x-auto rounded-va-lg border border-va-border">
            <table className="w-full text-sm text-va-text">
              <thead>
                <tr className="border-b border-va-border bg-va-surface">
                  <th className="px-3 py-2 text-left font-medium">Label</th>
                  <th className="px-3 py-2 text-right font-medium">Amount</th>
                  <th className="px-3 py-2 text-right font-medium">Month</th>
                  <th className="px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {equities.map((eq, idx) => (
                  <tr key={idx} className="border-b border-va-border/50">
                    <td className="px-3 py-2">
                      <VAInput
                        value={eq.label ?? ""}
                        onChange={(e) =>
                          updateEquity(idx, { label: e.target.value })
                        }
                        placeholder="Raise label"
                      />
                    </td>
                    <td className="px-3 py-2">
                      <VAInput
                        type="number"
                        className="font-mono"
                        value={eq.amount}
                        onChange={(e) =>
                          updateEquity(idx, {
                            amount: parseFloat(e.target.value) || 0,
                          })
                        }
                      />
                    </td>
                    <td className="px-3 py-2">
                      <VAInput
                        type="number"
                        className="font-mono"
                        value={eq.month}
                        onChange={(e) =>
                          updateEquity(idx, {
                            month: parseInt(e.target.value) || 0,
                          })
                        }
                      />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <VAButton
                        variant="ghost"
                        className="text-va-danger text-xs"
                        onClick={() => removeEquity(idx)}
                      >
                        Delete
                      </VAButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <VAButton variant="secondary" className="mt-3" onClick={addEquity}>
          + Add Raise
        </VAButton>
      </section>

      {/* ── Dividend Policy ─────────────────────────────────────── */}
      <section>
        <h3 className="mb-3 text-sm font-brand font-medium text-va-text">
          Dividend Policy
        </h3>

        <div className="space-y-3">
          <div className="flex flex-wrap gap-4">
            <label className="flex items-center gap-2 text-sm text-va-text">
              <input
                type="radio"
                name="dividend-policy"
                value="none"
                checked={currentPolicy === "none"}
                onChange={() => setDividendPolicy("none")}
                className="border-va-border text-va-blue"
              />
              None
            </label>
            <label className="flex items-center gap-2 text-sm text-va-text">
              <input
                type="radio"
                name="dividend-policy"
                value="fixed_amount"
                checked={currentPolicy === "fixed_amount"}
                onChange={() => setDividendPolicy("fixed_amount")}
                className="border-va-border text-va-blue"
              />
              Fixed Amount
            </label>
            <label className="flex items-center gap-2 text-sm text-va-text">
              <input
                type="radio"
                name="dividend-policy"
                value="payout_ratio"
                checked={currentPolicy === "payout_ratio"}
                onChange={() => setDividendPolicy("payout_ratio")}
                className="border-va-border text-va-blue"
              />
              Payout Ratio
            </label>
          </div>

          {currentPolicy !== "none" && (
            <div className="max-w-xs">
              <label className="mb-1 block text-xs font-medium text-va-text2">
                {currentPolicy === "fixed_amount"
                  ? "Amount per period"
                  : "Ratio (0-1)"}
              </label>
              <VAInput
                type="number"
                className="font-mono"
                value={div?.value ?? 0}
                step={currentPolicy === "payout_ratio" ? "0.01" : "1"}
                onChange={(e) =>
                  setDividendValue(parseFloat(e.target.value) || 0)
                }
              />
            </div>
          )}
        </div>
      </section>

      {/* ── Delete confirmation dialog ──────────────────────────── */}
      <VAConfirmDialog
        open={deleteTarget !== null}
        title="Delete Facility"
        description="Are you sure you want to delete this debt facility? This action cannot be undone."
        confirmLabel="Delete"
        variant="danger"
        onConfirm={() => deleteTarget && removeFacility(deleteTarget)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
