"use client";

import { VACard } from "@/components/ui/VACard";
import { VAButton } from "@/components/ui/VAButton";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface ReviewMapping {
  entityName: string;
  revenueStreams: string[];
  costItems: string[];
  capexItems: string[];
  unmapped: string[];
}

export interface ReviewPanelProps {
  mapping: ReviewMapping;
  onCreateDraft: () => void;
  loading?: boolean;
}

/* ------------------------------------------------------------------ */
/*  Section helper                                                     */
/* ------------------------------------------------------------------ */

function Section({
  title,
  items,
  className,
}: {
  title: string;
  items: string[];
  className?: string;
}) {
  if (items.length === 0) return null;

  return (
    <div className="mt-3">
      <h4 className={`text-xs font-semibold uppercase tracking-wider ${className ?? "text-va-text2"}`}>
        {title}
      </h4>
      <ul className="mt-1 space-y-0.5">
        {items.map((item) => (
          <li key={item} className="text-sm text-va-text">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  ReviewPanel                                                        */
/* ------------------------------------------------------------------ */

export function ReviewPanel({ mapping, onCreateDraft, loading }: ReviewPanelProps) {
  return (
    <VACard className="p-5">
      <h3 className="text-base font-brand font-semibold text-va-text">
        {mapping.entityName}
      </h3>

      <Section title="Revenue Streams" items={mapping.revenueStreams} />
      <Section title="Cost Items" items={mapping.costItems} />
      <Section title="Capex Items" items={mapping.capexItems} />
      <Section
        title="Unmapped"
        items={mapping.unmapped}
        className="text-va-warning"
      />

      <div className="mt-5">
        <VAButton onClick={onCreateDraft} disabled={loading}>
          {loading ? "Creating..." : "Create Draft"}
        </VAButton>
      </div>
    </VACard>
  );
}
