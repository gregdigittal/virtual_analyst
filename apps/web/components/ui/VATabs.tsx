"use client";

import type { ReactNode } from "react";

interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

interface VATabsProps {
  tabs: TabItem[];
  activeId: string;
  onSelect: (id: string) => void;
  className?: string;
}

export function VATabs({
  tabs,
  activeId,
  onSelect,
  className = "",
}: VATabsProps) {
  return (
    <div className={className}>
      <div
        className="flex gap-1 border-b border-va-border"
        role="tablist"
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeId === tab.id}
            onClick={() => onSelect(tab.id)}
            className={`rounded-t-va-sm px-4 py-2 text-sm font-medium transition focus:outline-none focus-visible:ring-2 focus-visible:ring-va-blue focus-visible:ring-offset-2 focus-visible:ring-offset-va-midnight ${
              activeId === tab.id
                ? "border border-va-border border-b-0 bg-va-panel text-va-text"
                : "text-va-text2 hover:bg-white/5"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div className="rounded-b-va-lg border border-va-border border-t-0 bg-va-panel/80 p-4">
        {tabs.find((t) => t.id === activeId)?.content}
      </div>
    </div>
  );
}
