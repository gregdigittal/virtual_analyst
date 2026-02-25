"use client";

import { useState } from "react";
import { VAButton, VACard, VAInput } from "@/components/ui";

interface OpExCategory {
  name: string;
  share_pct: number;
  growth_rate: number;
}

interface BlueprintNode {
  id: string;
  type: "formula";
  ref: string;
  label: string;
}

interface BlueprintFormula {
  output: string;
  expression: string;
  inputs: string[];
}

interface Props {
  totalOpex: number;
  onGenerate: (nodes: BlueprintNode[], formulas: BlueprintFormula[]) => void;
}

const DEFAULT_CATEGORIES: OpExCategory[] = [
  { name: "Personnel", share_pct: 40, growth_rate: 0.05 },
  { name: "Facilities", share_pct: 20, growth_rate: 0.03 },
  { name: "Admin", share_pct: 15, growth_rate: 0.02 },
  { name: "Sales & Marketing", share_pct: 15, growth_rate: 0.04 },
  { name: "Other", share_pct: 10, growth_rate: 0.02 },
];

function toNodeId(name: string): string {
  return `opex_${name.toLowerCase().replace(/[^a-z0-9]/g, "_")}`;
}

export function OpExCategoryWizard({ totalOpex, onGenerate }: Props) {
  const [categories, setCategories] = useState<OpExCategory[]>(DEFAULT_CATEGORIES);

  const totalShare = categories.reduce((s, c) => s + c.share_pct, 0);

  function updateCategory(idx: number, patch: Partial<OpExCategory>) {
    setCategories((prev) =>
      prev.map((c, i) => (i === idx ? { ...c, ...patch } : c))
    );
  }

  function removeCategory(idx: number) {
    setCategories((prev) => prev.filter((_, i) => i !== idx));
  }

  function addCategory() {
    setCategories((prev) => [
      ...prev,
      { name: `Category ${prev.length + 1}`, share_pct: 0, growth_rate: 0.02 },
    ]);
  }

  function handleGenerate() {
    const nodes: BlueprintNode[] = [];
    const formulas: BlueprintFormula[] = [];
    const usedIds = new Set<string>();

    for (const cat of categories) {
      let id = toNodeId(cat.name);
      // Deduplicate: append _2, _3, etc. if ID already used
      if (usedIds.has(id)) {
        let suffix = 2;
        while (usedIds.has(`${id}_${suffix}`)) suffix++;
        id = `${id}_${suffix}`;
      }
      usedIds.add(id);

      nodes.push({ id, type: "formula", ref: id, label: `OpEx: ${cat.name}` });
      formulas.push({
        output: id,
        expression: `total_opex * ${cat.share_pct / 100} * (1 + ${cat.growth_rate}) ** t`,
        inputs: ["total_opex"],
      });
    }

    onGenerate(nodes, formulas);
  }

  return (
    <VACard className="p-4">
      <h3 className="mb-3 text-sm font-semibold text-va-text">
        OpEx Category Allocation
      </h3>
      <p className="mb-4 text-xs text-va-text2">
        Define OpEx categories with share percentages and annual growth rates.
        This generates blueprint nodes that allocate total OpEx ({totalOpex.toLocaleString()}) across categories.
      </p>

      <div className="mb-3 space-y-2">
        {categories.map((cat, i) => (
          <div key={i} className="flex items-center gap-2">
            <VAInput
              value={cat.name}
              onChange={(e) => updateCategory(i, { name: e.target.value })}
              placeholder="Category name"
              className="flex-1"
            />
            <div className="flex items-center gap-1">
              <VAInput
                type="number"
                value={cat.share_pct}
                onChange={(e) =>
                  updateCategory(i, { share_pct: Number(e.target.value) })
                }
                className="w-20"
              />
              <span className="text-xs text-va-text2">%</span>
            </div>
            <div className="flex items-center gap-1">
              <VAInput
                type="number"
                value={(cat.growth_rate * 100).toFixed(1)}
                onChange={(e) =>
                  updateCategory(i, {
                    growth_rate: Number(e.target.value) / 100,
                  })
                }
                className="w-20"
                step="0.1"
              />
              <span className="text-xs text-va-text2">% g</span>
            </div>
            <button
              type="button"
              onClick={() => removeCategory(i)}
              className="rounded px-1.5 py-0.5 text-xs text-va-danger hover:bg-va-danger/10"
              title="Remove"
            >
              &times;
            </button>
          </div>
        ))}
      </div>

      <div className="mb-4 flex items-center justify-between">
        <VAButton type="button" variant="ghost" onClick={addCategory}>
          + Add category
        </VAButton>
        <span
          className={`text-xs font-mono ${
            Math.abs(totalShare - 100) < 0.01
              ? "text-va-text2"
              : "text-va-danger"
          }`}
        >
          Total: {totalShare.toFixed(1)}%
        </span>
      </div>

      <VAButton
        onClick={handleGenerate}
        disabled={Math.abs(totalShare - 100) > 0.5}
      >
        Generate Blueprint Nodes
      </VAButton>
      {Math.abs(totalShare - 100) > 0.5 && (
        <p className="mt-1 text-xs text-va-danger">
          Shares must sum to 100% (currently {totalShare.toFixed(1)}%)
        </p>
      )}
    </VACard>
  );
}
