"use client";

import { useEffect, useState } from "react";
import { VAInput, VASelect, VAButton } from "@/components/ui";

export interface RevenueStream {
  label: string;
  stream_type: string;
  business_line?: string | null;
  market?: string | null;
  launch_month?: number | null;
  ramp_up_months?: number | null;
  ramp_curve?: string | null;
}

interface RevenueStreamEditorProps {
  streams: RevenueStream[];
  onChange: (streams: RevenueStream[]) => void;
}

const STREAM_TYPES = [
  { value: "recurring", label: "Recurring" },
  { value: "one_time", label: "One Time" },
  { value: "usage_based", label: "Usage Based" },
  { value: "licensing", label: "Licensing" },
];

const RAMP_CURVES = ["linear", "s_curve", "exponential", "step"];

export function RevenueStreamEditor({ streams, onChange }: RevenueStreamEditorProps) {
  const [local, setLocal] = useState<RevenueStream[]>(streams);

  // Sync external prop changes into local state
  useEffect(() => {
    setLocal(streams);
  }, [streams]);

  const commit = (updated: RevenueStream[]) => {
    setLocal(updated);
    onChange(updated);
  };

  const updateField = (index: number, field: keyof RevenueStream, value: string | number | null) => {
    const updated = local.map((s, i) => {
      if (i !== index) return s;
      const copy = { ...s, [field]: value };
      // Clear dependent fields when parent is cleared
      if (field === "launch_month" && (value == null || value === "")) {
        copy.launch_month = null;
        copy.ramp_up_months = null;
        copy.ramp_curve = null;
      }
      if (field === "ramp_up_months" && (value == null || value === "")) {
        copy.ramp_up_months = null;
        copy.ramp_curve = null;
      }
      return copy;
    });
    commit(updated);
  };

  const addStream = () => {
    commit([
      ...local,
      { label: "", stream_type: "recurring", business_line: "", market: "" },
    ]);
  };

  const deleteStream = (index: number) => {
    commit(local.filter((_, i) => i !== index));
  };

  return (
    <div>
      <div className="overflow-x-auto rounded-va-lg border border-va-border">
        <table className="w-full text-sm text-va-text">
          <thead>
            <tr className="border-b border-va-border bg-va-surface">
              <th className="px-3 py-2 text-left font-medium">Label</th>
              <th className="px-3 py-2 text-left font-medium">Type</th>
              <th className="px-3 py-2 text-left font-medium">Business Line</th>
              <th className="px-3 py-2 text-left font-medium">Market</th>
              <th className="px-3 py-2 text-right font-medium">Launch Month</th>
              <th className="px-3 py-2 text-right font-medium">Ramp Up Months</th>
              <th className="px-3 py-2 text-left font-medium">Ramp Curve</th>
              <th className="px-3 py-2 text-center font-medium" />
            </tr>
          </thead>
          <tbody>
            {local.map((stream, index) => {
              const hasLaunchMonth = stream.launch_month != null;
              const hasRampUpMonths = stream.ramp_up_months != null;
              return (
                <tr key={index} className="border-b border-va-border/50">
                  <td className="px-3 py-2">
                    <VAInput
                      value={stream.label}
                      onChange={(e) => updateField(index, "label", e.target.value)}
                      placeholder="Stream label"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <VASelect
                      value={stream.stream_type}
                      onChange={(e) => updateField(index, "stream_type", e.target.value)}
                    >
                      {STREAM_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>
                          {t.label}
                        </option>
                      ))}
                    </VASelect>
                  </td>
                  <td className="px-3 py-2">
                    <VAInput
                      value={stream.business_line ?? ""}
                      onChange={(e) => updateField(index, "business_line", e.target.value)}
                      placeholder="Business line"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <VAInput
                      value={stream.market ?? ""}
                      onChange={(e) => updateField(index, "market", e.target.value)}
                      placeholder="Market"
                    />
                  </td>
                  <td className="px-3 py-2">
                    <VAInput
                      type="number"
                      className="font-mono text-right"
                      value={stream.launch_month ?? ""}
                      onChange={(e) =>
                        updateField(
                          index,
                          "launch_month",
                          e.target.value === "" ? null : Number(e.target.value)
                        )
                      }
                      placeholder="Month"
                    />
                  </td>
                  <td className="px-3 py-2">
                    {hasLaunchMonth ? (
                      <VAInput
                        type="number"
                        className="font-mono text-right"
                        value={stream.ramp_up_months ?? ""}
                        onChange={(e) =>
                          updateField(
                            index,
                            "ramp_up_months",
                            e.target.value === "" ? null : Number(e.target.value)
                          )
                        }
                        placeholder="Months"
                      />
                    ) : null}
                  </td>
                  <td className="px-3 py-2">
                    {hasLaunchMonth && hasRampUpMonths ? (
                      <VASelect
                        value={stream.ramp_curve ?? ""}
                        onChange={(e) =>
                          updateField(index, "ramp_curve", e.target.value || null)
                        }
                      >
                        {!stream.ramp_curve && <option value="">Select curve</option>}
                        {RAMP_CURVES.map((c) => (
                          <option key={c} value={c}>
                            {c}
                          </option>
                        ))}
                      </VASelect>
                    ) : null}
                  </td>
                  <td className="px-3 py-2 text-center">
                    <button
                      type="button"
                      title="delete"
                      onClick={() => deleteStream(index)}
                      className="rounded p-1 text-va-text2 hover:bg-va-danger/20 hover:text-va-danger"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-4 w-4"
                        viewBox="0 0 20 20"
                        fill="currentColor"
                      >
                        <path
                          fillRule="evenodd"
                          d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zM7 8a1 1 0 012 0v6a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="mt-3">
        <VAButton variant="secondary" onClick={addStream}>
          + Add Stream
        </VAButton>
      </div>
    </div>
  );
}
