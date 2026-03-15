"use client";

import { type PimMarkovSteadyStateResponse, type PimMarkovTopTransitionsResponse } from "@/lib/api";
import { useMemo, useState } from "react";

// ---------------------------------------------------------------------------
// Layout helpers — circular placement of nodes
// ---------------------------------------------------------------------------

interface Node {
  id: number;
  label: string;
  probability: number;
  x: number;
  y: number;
  r: number;
  gdpState: number;   // 0=contraction, 1=neutral, 2=expansion (from label)
}

const GDP_COLOURS: Record<number, string> = {
  0: "#ef4444",   // contraction — red
  1: "#eab308",   // neutral — yellow
  2: "#22c55e",   // expansion — green
};

function parseGdpState(label: string): number {
  if (label.startsWith("contraction")) return 0;
  if (label.startsWith("expansion")) return 2;
  return 1;
}

function buildNodes(
  topStates: PimMarkovSteadyStateResponse["top_states"],
  width: number,
  height: number,
): Node[] {
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.36;
  const n = topStates.length;
  const maxProb = Math.max(...topStates.map((s) => s.probability));

  return topStates.map((s, i) => {
    const angle = (2 * Math.PI * i) / n - Math.PI / 2;
    return {
      id: s.state_index,
      label: s.label,
      probability: s.probability,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      r: 12 + (s.probability / maxProb) * 22,
      gdpState: parseGdpState(s.label),
    };
  });
}

// ---------------------------------------------------------------------------
// Arrow marker
// ---------------------------------------------------------------------------

function ArrowDef() {
  return (
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#475569" />
      </marker>
      <marker id="arrow-hot" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
        <path d="M0,0 L0,6 L8,3 z" fill="#3b82f6" />
      </marker>
    </defs>
  );
}

// ---------------------------------------------------------------------------
// Edge component — curved line between nodes
// ---------------------------------------------------------------------------

interface EdgeProps {
  fromNode: Node;
  toNode: Node;
  probability: number;
  isHot: boolean;
}

function Edge({ fromNode, toNode, probability, isHot }: EdgeProps) {
  // Offset source/target to node edge (not center)
  const dx = toNode.x - fromNode.x;
  const dy = toNode.y - fromNode.y;
  const dist = Math.sqrt(dx * dx + dy * dy) || 1;
  const ux = dx / dist;
  const uy = dy / dist;

  const sx = fromNode.x + ux * fromNode.r;
  const sy = fromNode.y + uy * fromNode.r;
  const ex = toNode.x - ux * (toNode.r + 8);
  const ey = toNode.y - uy * (toNode.r + 8);

  // Slightly curved path
  const mx = (sx + ex) / 2 - uy * 20;
  const my = (sy + ey) / 2 + ux * 20;

  const opacity = 0.3 + probability * 0.7;
  const strokeWidth = 1 + probability * 3;

  return (
    <path
      d={`M${sx},${sy} Q${mx},${my} ${ex},${ey}`}
      stroke={isHot ? "#3b82f6" : "#475569"}
      strokeWidth={strokeWidth}
      strokeOpacity={opacity}
      fill="none"
      markerEnd={isHot ? "url(#arrow-hot)" : "url(#arrow)"}
    />
  );
}

// ---------------------------------------------------------------------------
// Main graph component
// ---------------------------------------------------------------------------

interface MarkovGraphProps {
  steadyState: PimMarkovSteadyStateResponse;
  transitions: PimMarkovTopTransitionsResponse;
}

export function MarkovGraph({ steadyState, transitions }: MarkovGraphProps) {
  const [hoveredNodeId, setHoveredNodeId] = useState<number | null>(null);

  const W = 600;
  const H = 480;

  const nodes = useMemo(
    () => buildNodes(steadyState.top_states, W, H),
    [steadyState.top_states],
  );

  const nodeMap = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);

  // Determine which edges involve the hovered node
  const hotEdgeSet = useMemo(() => {
    if (hoveredNodeId === null) return new Set<string>();
    return new Set(
      transitions.edges
        .filter((e) => e.from_state === hoveredNodeId)
        .map((e) => `${e.from_state}-${e.to_state}`),
    );
  }, [hoveredNodeId, transitions.edges]);

  const hoveredNode = hoveredNodeId !== null ? nodeMap.get(hoveredNodeId) : undefined;
  const hoveredEdges = useMemo(
    () => transitions.edges.filter((e) => e.from_state === hoveredNodeId),
    [hoveredNodeId, transitions.edges],
  );

  return (
    <div className="flex flex-col gap-4 lg:flex-row">
      {/* SVG graph */}
      <div className="flex-1">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          style={{ maxHeight: 480 }}
          aria-label="Markov state transition diagram"
        >
          <ArrowDef />

          {/* Edges */}
          {transitions.edges.map((e) => {
            const from = nodeMap.get(e.from_state);
            const to = nodeMap.get(e.to_state);
            if (!from || !to) return null;
            const key = `${e.from_state}-${e.to_state}`;
            return (
              <Edge
                key={key}
                fromNode={from}
                toNode={to}
                probability={e.probability}
                isHot={hotEdgeSet.has(key)}
              />
            );
          })}

          {/* Nodes */}
          {nodes.map((node) => {
            const colour = GDP_COLOURS[node.gdpState] ?? "#64748b";
            const isHovered = node.id === hoveredNodeId;
            const pctLabel = `${(node.probability * 100).toFixed(1)}%`;
            // Short label: first dimension only
            const shortLabel = node.label.split("/")[0] ?? node.label;

            return (
              <g
                key={node.id}
                transform={`translate(${node.x},${node.y})`}
                style={{ cursor: "pointer" }}
                onMouseEnter={() => setHoveredNodeId(node.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
              >
                <circle
                  r={node.r}
                  fill={colour}
                  fillOpacity={isHovered ? 0.9 : 0.55}
                  stroke={colour}
                  strokeWidth={isHovered ? 2.5 : 1.5}
                />
                <text
                  textAnchor="middle"
                  dy="0.35em"
                  fontSize={10}
                  fill="#f8fafc"
                  fontWeight={isHovered ? "bold" : "normal"}
                  pointerEvents="none"
                >
                  {pctLabel}
                </text>
                <text
                  textAnchor="middle"
                  dy={node.r + 12}
                  fontSize={9}
                  fill="#94a3b8"
                  pointerEvents="none"
                >
                  {shortLabel}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Legend */}
        <div className="mt-2 flex flex-wrap gap-4 px-2">
          {Object.entries(GDP_COLOURS).map(([k, c]) => (
            <div key={k} className="flex items-center gap-1.5 text-xs text-va-text2">
              <span className="inline-block h-3 w-3 rounded-full" style={{ background: c }} />
              {k === "0" ? "Contraction" : k === "1" ? "Neutral" : "Expansion"}
            </div>
          ))}
          <span className="text-xs text-va-text2">
            Node size ∝ steady-state probability · Hover to highlight outgoing transitions
          </span>
        </div>
      </div>

      {/* Side panel — hovered state details */}
      <div className="w-full lg:w-64">
        {hoveredNode ? (
          <div className="space-y-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-va-text2">Selected State</p>
              <p className="mt-1 text-sm font-mono text-va-text">{hoveredNode.label}</p>
              <p className="text-xs text-va-text2">
                Steady-state: {(hoveredNode.probability * 100).toFixed(2)}%
              </p>
            </div>
            {hoveredEdges.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-va-text2">
                  Outgoing Transitions
                </p>
                <ul className="mt-1 space-y-1">
                  {hoveredEdges
                    .sort((a, b) => b.probability - a.probability)
                    .map((e) => (
                      <li key={e.to_state} className="flex items-center justify-between text-xs">
                        <span className="truncate text-va-text2">{e.to_label.split("/")[0]}</span>
                        <span className="ml-2 font-mono text-va-text">
                          {(e.probability * 100).toFixed(1)}%
                        </span>
                      </li>
                    ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="text-sm text-va-text2">
            Hover a state node to see outgoing transition probabilities.
          </p>
        )}
      </div>
    </div>
  );
}
