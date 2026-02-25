"use client";

interface CorrelationEntry {
  ref_a: string;
  ref_b: string;
  rho: number;
}

interface DistributionConfig {
  ref: string;
  family: string;
  params?: Record<string, number>;
}

function refLabel(ref: string): string {
  return ref.startsWith("drv:") ? ref.slice(4).replace(/_/g, " ") : ref;
}

function cellColor(rho: number): string {
  if (rho > 0.6) return "bg-blue-600/40";
  if (rho > 0.3) return "bg-blue-500/25";
  if (rho > 0.05) return "bg-blue-400/15";
  if (rho < -0.6) return "bg-red-600/40";
  if (rho < -0.3) return "bg-red-500/25";
  if (rho < -0.05) return "bg-red-400/15";
  return "bg-va-surface/50";
}

export function CorrelationMatrixEditor({
  distributions,
  correlationMatrix,
}: {
  distributions: DistributionConfig[];
  correlationMatrix: CorrelationEntry[];
}) {
  if (!distributions || distributions.length < 2) {
    return (
      <p className="text-sm text-va-text2">
        Add at least 2 driver distributions to configure correlations.
      </p>
    );
  }

  const refs = distributions.map((d) => d.ref);
  const lookup = new Map<string, number>();
  for (const entry of correlationMatrix) {
    lookup.set(`${entry.ref_a}|${entry.ref_b}`, entry.rho);
    lookup.set(`${entry.ref_b}|${entry.ref_a}`, entry.rho);
  }

  function getRho(a: string, b: string): number {
    if (a === b) return 1.0;
    return lookup.get(`${a}|${b}`) ?? 0;
  }

  const nonZeroPairs = correlationMatrix.filter((e) => Math.abs(e.rho) > 0.001);

  return (
    <div className="space-y-4">
      {/* Matrix grid */}
      <div className="overflow-x-auto">
        <table className="text-xs">
          <thead>
            <tr>
              <th className="px-2 py-1" />
              {refs.map((ref) => (
                <th
                  key={ref}
                  className="px-2 py-1 text-center font-medium text-va-text2"
                  title={ref}
                >
                  {refLabel(ref).slice(0, 10)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {refs.map((rowRef) => (
              <tr key={rowRef}>
                <td className="px-2 py-1 text-right font-medium text-va-text2" title={rowRef}>
                  {refLabel(rowRef).slice(0, 10)}
                </td>
                {refs.map((colRef) => {
                  const rho = getRho(rowRef, colRef);
                  const isDiag = rowRef === colRef;
                  return (
                    <td
                      key={colRef}
                      className={`px-2 py-1 text-center font-mono ${
                        isDiag
                          ? "bg-va-border/30 text-va-text2"
                          : `${cellColor(rho)} text-va-text`
                      }`}
                      title={`${refLabel(rowRef)} × ${refLabel(colRef)} = ${rho}`}
                    >
                      {rho.toFixed(2)}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* List view of non-zero pairs */}
      {nonZeroPairs.length > 0 && (
        <div>
          <h4 className="mb-1 text-xs font-medium text-va-text2">
            Active correlations ({nonZeroPairs.length})
          </h4>
          <ul className="space-y-0.5 text-sm">
            {nonZeroPairs.map((e, i) => (
              <li key={i} className="flex items-baseline gap-2 text-va-text">
                <span className="text-va-text2">{refLabel(e.ref_a)}</span>
                <span className="text-va-text2">&times;</span>
                <span className="text-va-text2">{refLabel(e.ref_b)}</span>
                <span className="text-va-text2">=</span>
                <span
                  className={`font-mono font-medium ${
                    e.rho > 0 ? "text-blue-400" : "text-red-400"
                  }`}
                >
                  {e.rho > 0 ? "+" : ""}
                  {e.rho.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
