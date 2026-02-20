"use client";

import { VACard } from "@/components/ui";
import { useState, type JSX } from "react";

interface ConfigViewerProps {
  config: Record<string, unknown>;
}

const SECTION_META: Record<string, { label: string; description: string }> = {
  metadata: { label: "Metadata", description: "Entity name, currency, forecast horizon, tax rate" },
  assumptions: { label: "Assumptions", description: "Revenue streams, cost structure, working capital, capex, funding" },
  driver_blueprint: { label: "Driver Blueprint", description: "Node/edge graph and formula definitions" },
  distributions: { label: "Distributions", description: "Stochastic distribution definitions (Monte Carlo)" },
  scenarios: { label: "Scenarios", description: "Embedded scenario overrides (legacy)" },
  evidence_summary: { label: "Evidence Summary", description: "Assumption audit trail and confidence scores" },
  integrity: { label: "Integrity", description: "Validation checks and status" },
};

const SCALAR_KEYS = new Set([
  "artifact_type", "artifact_version", "tenant_id", "baseline_id",
  "baseline_version", "created_at", "created_by", "parent_baseline_id",
  "parent_baseline_version", "template_id",
]);

function formatValue(value: unknown, depth: number = 0): JSX.Element {
  if (value === null || value === undefined) return <span className="text-va-text2">—</span>;
  if (typeof value === "boolean") return <span className={value ? "text-green-400" : "text-va-danger"}>{String(value)}</span>;
  if (typeof value === "number") return <span className="font-mono">{value.toLocaleString(undefined, { maximumFractionDigits: 4 })}</span>;
  if (typeof value === "string") return <span className="text-amber-300/80">&quot;{value}&quot;</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="text-va-text2">[]</span>;
    if (depth > 1) return <span className="text-va-text2">[{value.length} items]</span>;
    return (
      <div className="space-y-2">
        {value.map((item, i) => (
          <div key={i} className="rounded-va-xs border border-va-border/50 bg-va-surface/50 p-2">
            <span className="mb-1 text-[10px] uppercase tracking-wide text-va-text2">Item {i + 1}</span>
            {typeof item === "object" && item !== null ? (
              <ObjectView obj={item as Record<string, unknown>} depth={depth + 1} />
            ) : (
              formatValue(item, depth + 1)
            )}
          </div>
        ))}
      </div>
    );
  }
  if (typeof value === "object") {
    return <ObjectView obj={value as Record<string, unknown>} depth={depth + 1} />;
  }
  return <span>{String(value)}</span>;
}

function ObjectView({ obj, depth = 0 }: { obj: Record<string, unknown>; depth?: number }) {
  const entries = Object.entries(obj);
  if (entries.length === 0) return <span className="text-va-text2">{"{}"}</span>;
  return (
    <dl className="space-y-1">
      {entries.map(([k, v]) => (
        <div key={k} className="flex gap-2">
          <dt className="shrink-0 text-xs font-medium text-va-text2 capitalize" style={{ minWidth: "120px" }}>
            {k.replace(/_/g, " ")}
          </dt>
          <dd className="text-xs text-va-text">{formatValue(v, depth)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function ConfigViewer({ config }: ConfigViewerProps) {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set());
  const [showRaw, setShowRaw] = useState(false);

  const knownSectionKeys = Object.keys(SECTION_META);
  const scalars = Object.entries(config).filter(([k]) => SCALAR_KEYS.has(k));
  const sections = Object.entries(config).filter(([k]) => knownSectionKeys.includes(k));
  const otherObjects = Object.entries(config).filter(
    ([k]) => !SCALAR_KEYS.has(k) && !knownSectionKeys.includes(k) && typeof config[k] === "object" && config[k] !== null
  );

  function toggleSection(key: string) {
    setExpandedSections((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="space-y-3">
      {scalars.length > 0 && (
        <VACard className="p-4">
          <h3 className="mb-2 text-sm font-medium text-va-text">General parameters</h3>
          <dl className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {scalars.map(([k, v]) => (
              <div key={k}>
                <dt className="text-xs text-va-text2 capitalize">{k.replace(/_/g, " ")}</dt>
                <dd className="text-sm font-mono text-va-text">{String(v ?? "—")}</dd>
              </div>
            ))}
          </dl>
        </VACard>
      )}

      {sections.map(([key, value]) => {
        const meta = SECTION_META[key];
        const expanded = expandedSections.has(key);
        const itemCount = Array.isArray(value) ? value.length : Object.keys(value as object).length;
        return (
          <VACard key={key} className="overflow-hidden">
            <button
              type="button"
              onClick={() => toggleSection(key)}
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-white/5"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-va-text">
                  {meta?.label ?? key.replace(/_/g, " ")}
                </span>
                <span className="rounded-full bg-va-surface px-2 py-0.5 text-[10px] text-va-text2">
                  {itemCount} {Array.isArray(value) ? "items" : "fields"}
                </span>
              </div>
              <span className="text-va-text2">{expanded ? "▾" : "▸"}</span>
            </button>
            {expanded && (
              <div className="border-t border-va-border px-4 py-3">
                {meta?.description && <p className="mb-3 text-xs text-va-text2">{meta.description}</p>}
                {formatValue(value)}
              </div>
            )}
          </VACard>
        );
      })}

      {otherObjects.map(([key, value]) => {
        const expanded = expandedSections.has(key);
        return (
          <VACard key={key} className="overflow-hidden">
            <button
              type="button"
              onClick={() => toggleSection(key)}
              className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-white/5"
            >
              <span className="text-sm font-medium text-va-text capitalize">{key.replace(/_/g, " ")}</span>
              <span className="text-va-text2">{expanded ? "▾" : "▸"}</span>
            </button>
            {expanded && (
              <div className="border-t border-va-border px-4 py-3">
                {formatValue(value)}
              </div>
            )}
          </VACard>
        );
      })}

      <details open={showRaw} onToggle={(e) => setShowRaw((e.target as HTMLDetailsElement).open)}>
        <summary className="cursor-pointer text-xs text-va-text2 hover:text-va-text">
          View raw JSON
        </summary>
        <pre className="mt-2 max-h-96 overflow-auto rounded-va-xs bg-va-surface p-3 font-mono text-xs text-va-text2">
          {JSON.stringify(config, null, 2)}
        </pre>
      </details>
    </div>
  );
}
