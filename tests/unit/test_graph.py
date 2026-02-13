"""Unit tests for calculation graph: topo_sort, cycle detection."""

import pytest

from shared.fm_shared.model.graph import CalcGraph, GraphCycleError
from shared.fm_shared.model.schemas import (
    BlueprintEdge,
    BlueprintFormula,
    BlueprintNode,
    DriverBlueprint,
)


def _blueprint(
    nodes: list[dict], edges: list[dict], formulas: list[dict] | None = None
) -> DriverBlueprint:
    return DriverBlueprint(
        nodes=[BlueprintNode.model_validate(n) for n in nodes],
        edges=[BlueprintEdge.model_validate(e) for e in edges],
        formulas=[BlueprintFormula.model_validate(f) for f in (formulas or [])],
    )


def test_topo_sort_acyclic() -> None:
    """DAG returns correct execution order."""
    bp = _blueprint(
        nodes=[
            {"node_id": "a", "type": "driver", "label": "A", "ref": "drv:a"},
            {"node_id": "b", "type": "driver", "label": "B", "ref": "drv:b"},
            {"node_id": "c", "type": "formula", "label": "C"},
        ],
        edges=[{"from": "a", "to": "c"}, {"from": "b", "to": "c"}],
    )
    g = CalcGraph.from_blueprint(bp)
    order = g.topo_sort()
    assert set(order) == {"a", "b", "c"}
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("c")


def test_cycle_detection() -> None:
    """Cycle raises GraphCycleError with path."""
    bp = _blueprint(
        nodes=[
            {"node_id": "a", "type": "driver", "label": "A", "ref": "drv:a"},
            {"node_id": "b", "type": "formula", "label": "B"},
            {"node_id": "c", "type": "formula", "label": "C"},
        ],
        edges=[{"from": "a", "to": "b"}, {"from": "b", "to": "c"}, {"from": "c", "to": "b"}],
    )
    g = CalcGraph.from_blueprint(bp)
    with pytest.raises(GraphCycleError) as exc_info:
        g.topo_sort()
    assert "b" in exc_info.value.cycle_path or "c" in exc_info.value.cycle_path


def test_cycle_detect_returns_path() -> None:
    """detect_cycles returns cycle path when present."""
    bp = _blueprint(
        nodes=[
            {"node_id": "x", "type": "driver", "label": "X", "ref": "drv:x"},
            {"node_id": "y", "type": "formula", "label": "Y"},
        ],
        edges=[{"from": "x", "to": "y"}, {"from": "y", "to": "x"}],
    )
    g = CalcGraph.from_blueprint(bp)
    cycle = g.detect_cycles()
    assert cycle is not None
    assert len(cycle) >= 2
    assert set(cycle) <= {"x", "y"}


def test_no_cycle_returns_none() -> None:
    """detect_cycles returns None for DAG."""
    bp = _blueprint(
        nodes=[
            {"node_id": "a", "type": "driver", "label": "A", "ref": "drv:a"},
            {"node_id": "b", "type": "formula", "label": "B"},
        ],
        edges=[{"from": "a", "to": "b"}],
    )
    g = CalcGraph.from_blueprint(bp)
    assert g.detect_cycles() is None
    result = g.topo_sort()
    assert set(result) == {"a", "b"}
