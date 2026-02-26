"use client";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

export interface MappingData {
  revenue: number;
  cost: number;
  capex: number;
  unmapped: number;
}

/* ------------------------------------------------------------------ */
/*  MappingPreview                                                     */
/* ------------------------------------------------------------------ */

export function MappingPreview({ mapping }: { mapping: MappingData }) {
  return (
    <div className="inline-flex flex-wrap items-center gap-3 text-sm">
      <span>
        <span className="font-medium text-va-success">{mapping.revenue}</span>{" "}
        <span className="text-va-text2">revenue</span>
      </span>
      <span>
        <span className="font-medium text-va-text">{mapping.cost}</span>{" "}
        <span className="text-va-text2">cost</span>
      </span>
      <span>
        <span className="font-medium text-va-text">{mapping.capex}</span>{" "}
        <span className="text-va-text2">capex</span>
      </span>
      <span>
        <span className="font-medium text-va-warning">{mapping.unmapped}</span>{" "}
        <span className="text-va-text2">unmapped</span>
      </span>
    </div>
  );
}
