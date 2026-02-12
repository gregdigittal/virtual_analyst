"""
Calculation graph from driver_blueprint.
DAG build, topological sort, cycle detection.
"""

from __future__ import annotations

from collections import defaultdict, deque

from shared.fm_shared.errors import EngineError
from shared.fm_shared.model.schemas import (
    BlueprintEdge,
    BlueprintFormula,
    BlueprintNode,
    DriverBlueprint,
)


class GraphCycleError(EngineError):
    """Raised when the driver blueprint contains a cycle."""

    def __init__(self, cycle_path: list[str], message: str | None = None) -> None:
        self.cycle_path = cycle_path
        msg = message or f"Cycle detected in calculation graph: {' -> '.join(cycle_path)}"
        super().__init__(msg, code="ERR_ENG_CYCLE")


class CalcGraph:
    """
    Directed graph built from driver_blueprint.
    Nodes are driver, formula, or output; edges define execution order.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, BlueprintNode] = {}
        self.edges: list[BlueprintEdge] = []
        self.formulas_by_output: dict[str, BlueprintFormula] = {}
        self._adj: dict[str, list[str]] = defaultdict(list)
        self._in_degree: dict[str, int] = defaultdict(int)

    @classmethod
    def from_blueprint(cls, blueprint: DriverBlueprint) -> CalcGraph:
        g = cls()
        for node in blueprint.nodes:
            g.nodes[node.node_id] = node
            g._in_degree.setdefault(node.node_id, 0)
        for edge in blueprint.edges:
            g.edges.append(edge)
            src = edge.from_
            g._adj[src].append(edge.to)
            g._in_degree[edge.to] = g._in_degree.get(edge.to, 0) + 1
        for formula in blueprint.formulas:
            g.formulas_by_output[formula.output_node_id] = formula
        return g

    def topo_sort(self) -> list[str]:
        """Return node IDs in execution order (Kahn's algorithm)."""
        cycle = self.detect_cycles()
        if cycle is not None:
            raise GraphCycleError(cycle)
        in_deg = dict(self._in_degree)
        queue = deque(nid for nid, d in in_deg.items() if d == 0)
        order: list[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for succ in self._adj.get(nid, []):
                in_deg[succ] -= 1
                if in_deg[succ] == 0:
                    queue.append(succ)
        if len(order) != len(self.nodes):
            # Remaining nodes form a cycle; find one
            cycle = self._find_cycle_set(in_deg)
            raise GraphCycleError(cycle)
        return order

    def detect_cycles(self) -> list[str] | None:
        """Return a cycle path if one exists, else None."""
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []
        path_set: set[str] = set()
        node_to_idx: dict[str, int] = {}

        def dfs(nid: str) -> list[str] | None:
            visited.add(nid)
            rec_stack.add(nid)
            path.append(nid)
            path_set.add(nid)
            node_to_idx[nid] = len(path) - 1
            for succ in self._adj.get(nid, []):
                if succ not in visited:
                    cycle = dfs(succ)
                    if cycle is not None:
                        return cycle
                elif succ in rec_stack:
                    start = node_to_idx[succ]
                    return path[start:] + [succ]
            rec_stack.remove(nid)
            path.pop()
            path_set.discard(nid)
            return None

        for nid in self.nodes:
            if nid not in visited:
                cycle = dfs(nid)
                if cycle is not None:
                    return cycle
        return None

    def _find_cycle_set(self, in_deg: dict[str, int]) -> list[str]:
        """Find any cycle from nodes that still have in_degree > 0."""
        cycle_nodes = {nid for nid, d in in_deg.items() if d > 0}
        if not cycle_nodes:
            return []
        start = next(iter(cycle_nodes))
        seen: set[str] = set()
        stack = [start]
        parent: dict[str, str] = {}
        while stack:
            nid = stack.pop()
            if nid in seen:
                # Reconstruct cycle
                cycle: list[str] = []
                cur = nid
                while True:
                    cycle.append(cur)
                    cur = parent.get(cur)
                    if cur is None or cur == nid:
                        break
                cycle.reverse()
                return cycle if cur == nid else [nid]
            seen.add(nid)
            for succ in self._adj.get(nid, []):
                if succ in cycle_nodes:
                    parent[succ] = nid
                    stack.append(succ)
        return [start]
