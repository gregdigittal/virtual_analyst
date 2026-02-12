"""Unit tests for safe expression evaluator."""

import pytest

from shared.fm_shared.model.evaluator import EvalError, evaluate


def test_evaluate_arithmetic() -> None:
    """Basic arithmetic evaluates correctly."""
    assert evaluate("1 + 2", {}) == 3.0
    assert evaluate("10 - 3", {}) == 7.0
    assert evaluate("4 * 5", {}) == 20.0
    assert evaluate("20 / 4", {}) == 5.0
    assert evaluate("2 * 3 + 4", {}) == 10.0


def test_evaluate_with_variables() -> None:
    """Expressions with variables resolve correctly."""
    assert evaluate("a + b", {"a": 10, "b": 5}) == 15.0
    assert (
        evaluate("units_sold * price_per_unit", {"units_sold": 100, "price_per_unit": 2.5}) == 250.0
    )


def test_evaluate_min_max() -> None:
    """min and max work."""
    assert evaluate("min(1, 2)", {}) == 1.0
    assert evaluate("max(1, 2)", {}) == 2.0
    assert evaluate("min(a, b)", {"a": 10, "b": 3}) == 3.0


def test_evaluate_clamp() -> None:
    """clamp works."""
    assert evaluate("clamp(5, 0, 10)", {}) == 5.0
    assert evaluate("clamp(-1, 0, 10)", {}) == 0.0
    assert evaluate("clamp(15, 0, 10)", {}) == 10.0


def test_evaluate_if_else() -> None:
    """if_else works."""
    assert evaluate("if_else(1, 10, 20)", {}) == 10.0
    assert evaluate("if_else(0, 10, 20)", {}) == 20.0


def test_unsafe_rejected() -> None:
    """Unsafe operations raise EvalError."""
    with pytest.raises(EvalError):
        evaluate("__import__('os').system('ls')", {})
    with pytest.raises(EvalError):
        evaluate("eval('1+1')", {})
    with pytest.raises(EvalError):
        evaluate("open('/etc/passwd')", {})


def test_missing_variable_raises() -> None:
    """Missing variable raises EvalError."""
    with pytest.raises(EvalError):
        evaluate("a + b", {"a": 1})
