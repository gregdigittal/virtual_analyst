"use client";

import { useState } from "react";

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

/**
 * Compute eigenvalues of a symmetric matrix using the Jacobi eigenvalue algorithm.
 * Suitable for small matrices (N <= 10). Returns an array of eigenvalues.
 */
function computeEigenvalues(matrix: number[][]): number[] {
  const n = matrix.length;
  if (n === 0) return [];
  if (n === 1) return [matrix[0][0]];

  // Copy matrix
  const a: number[][] = matrix.map((row) => [...row]);
  const maxIter = 100 * n * n;

  for (let iter = 0; iter < maxIter; iter++) {
    // Find largest off-diagonal element
    let maxVal = 0;
    let p = 0;
    let q = 1;
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        if (Math.abs(a[i][j]) > maxVal) {
          maxVal = Math.abs(a[i][j]);
          p = i;
          q = j;
        }
      }
    }

    // Convergence check
    if (maxVal < 1e-12) break;

    // Compute rotation
    const app = a[p][p];
    const aqq = a[q][q];
    const apq = a[p][q];

    let theta: number;
    if (Math.abs(app - aqq) < 1e-15) {
      theta = Math.PI / 4;
    } else {
      theta = 0.5 * Math.atan2(2 * apq, app - aqq);
    }

    const c = Math.cos(theta);
    const s = Math.sin(theta);

    // Apply rotation
    const newApp = c * c * app + 2 * s * c * apq + s * s * aqq;
    const newAqq = s * s * app - 2 * s * c * apq + c * c * aqq;

    a[p][p] = newApp;
    a[q][q] = newAqq;
    a[p][q] = 0;
    a[q][p] = 0;

    for (let i = 0; i < n; i++) {
      if (i === p || i === q) continue;
      const aip = a[i][p];
      const aiq = a[i][q];
      a[i][p] = c * aip + s * aiq;
      a[p][i] = a[i][p];
      a[i][q] = -s * aip + c * aiq;
      a[q][i] = a[i][q];
    }
  }

  return Array.from({ length: n }, (_, i) => a[i][i]);
}

/**
 * Check if a correlation matrix (given as refs + entries) is positive semi-definite.
 */
function isPositiveSemiDefinite(
  refs: string[],
  getRho: (a: string, b: string) => number,
): boolean {
  const n = refs.length;
  const matrix: number[][] = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => getRho(refs[i], refs[j])),
  );
  const eigenvalues = computeEigenvalues(matrix);
  return eigenvalues.every((ev) => ev >= -1e-10);
}

/**
 * Canonical key for a pair: always ref_a < ref_b alphabetically.
 */
function canonicalPair(a: string, b: string): [string, string] {
  return a < b ? [a, b] : [b, a];
}

export function CorrelationMatrixEditor({
  distributions,
  correlationMatrix,
  editable = false,
  onChange,
}: {
  distributions: DistributionConfig[];
  correlationMatrix: CorrelationEntry[];
  editable?: boolean;
  onChange?: (entries: CorrelationEntry[]) => void;
}) {
  const [editingCell, setEditingCell] = useState<{ row: string; col: string } | null>(null);
  const [editValue, setEditValue] = useState("");

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

  function handleCellClick(rowRef: string, colRef: string) {
    if (!editable || rowRef === colRef) return;
    const rho = getRho(rowRef, colRef);
    setEditingCell({ row: rowRef, col: colRef });
    setEditValue(rho.toString());
  }

  function commitEdit() {
    if (!editingCell || !onChange) {
      setEditingCell(null);
      return;
    }

    let val = parseFloat(editValue);
    if (isNaN(val)) val = 0;
    val = Math.max(-1, Math.min(1, val));

    const [canonA, canonB] = canonicalPair(editingCell.row, editingCell.col);

    // Build new entries: replace existing or add new, removing near-zero
    const newEntries: CorrelationEntry[] = [];
    const editedKey = `${canonA}|${canonB}`;
    let replaced = false;

    for (const entry of correlationMatrix) {
      const [eA, eB] = canonicalPair(entry.ref_a, entry.ref_b);
      const key = `${eA}|${eB}`;
      if (key === editedKey) {
        replaced = true;
        if (Math.abs(val) > 0.001) {
          newEntries.push({ ref_a: canonA, ref_b: canonB, rho: val });
        }
      } else {
        newEntries.push(entry);
      }
    }

    if (!replaced && Math.abs(val) > 0.001) {
      newEntries.push({ ref_a: canonA, ref_b: canonB, rho: val });
    }

    setEditingCell(null);
    onChange(newEntries);
  }

  function cancelEdit() {
    setEditingCell(null);
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      commitEdit();
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit();
    }
  }

  const psdValid = editable ? isPositiveSemiDefinite(refs, getRho) : true;

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
                  const isEditing =
                    editingCell?.row === rowRef && editingCell?.col === colRef;

                  return (
                    <td
                      key={colRef}
                      className={`px-2 py-1 text-center font-mono ${
                        isDiag
                          ? "bg-va-border/30 text-va-text2"
                          : `${cellColor(rho)} text-va-text`
                      }${editable && !isDiag ? " cursor-pointer hover:ring-1 hover:ring-va-blue" : ""}`}
                      title={`${refLabel(rowRef)} × ${refLabel(colRef)} = ${rho}`}
                      onClick={() => handleCellClick(rowRef, colRef)}
                    >
                      {isEditing ? (
                        <input
                          type="number"
                          role="spinbutton"
                          className="w-14 bg-va-surface text-center font-mono text-va-text outline-none ring-1 ring-va-blue"
                          value={editValue}
                          step={0.05}
                          min={-1}
                          max={1}
                          autoFocus
                          onChange={(e) => setEditValue(e.target.value)}
                          onBlur={commitEdit}
                          onKeyDown={handleKeyDown}
                        />
                      ) : (
                        rho.toFixed(2)
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* PSD validation banner */}
      {editable && (
        <div className="text-xs">
          {psdValid ? (
            <p className="text-green-400">Matrix is valid (positive semi-definite).</p>
          ) : (
            <p className="text-amber-400">
              Matrix is not positive semi-definite. MC sampling may produce unexpected
              correlations.
            </p>
          )}
        </div>
      )}

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
