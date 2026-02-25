"""
Safe arithmetic expression evaluator.
No eval() or exec(). AST parse + evaluate with variable bindings.
"""

from __future__ import annotations

import ast
import operator
from typing import Any

from shared.fm_shared.errors import EngineError

BINARY_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}

UNARY_OPS = {
    ast.USub: operator.neg,
}

SAFE_BUILTINS: dict[str, Any] = {
    "min": min,
    "max": max,
    "abs": abs,
}


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def if_else(cond: float, true_val: float, false_val: float) -> float:
    return true_val if cond else false_val


SAFE_BUILTINS["clamp"] = clamp
SAFE_BUILTINS["if_else"] = if_else


class EvalError(EngineError):
    def __init__(self, message: str, **kwargs: Any) -> None:
        super().__init__(message, code="ERR_ENG_EVAL", **kwargs)


def evaluate(expression: str, variables: dict[str, float]) -> float:
    """
    Parse and evaluate a safe arithmetic expression.
    Supports: +, -, *, /, parentheses, min, max, clamp, if_else, variable names.
    """
    try:
        tree = ast.parse(expression.strip(), mode="eval")
    except SyntaxError as e:
        raise EvalError(f"Invalid expression syntax: {expression!r}") from e
    return _eval_node(tree.body, variables)


def _eval_node(node: ast.AST, variables: dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return float(node.value)
        raise EvalError(f"Unsupported constant type: {type(node.value)}")
    if isinstance(node, ast.Name):
        name = node.id
        if name not in variables:
            raise EvalError(f"Unknown variable: {name!r}")
        return variables[name]
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand, variables)
        raise EvalError(f"Unsupported unary op: {type(node.op)}")
    if isinstance(node, ast.BinOp):
        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)
        op = BINARY_OPS.get(type(node.op))
        if op is None:
            raise EvalError(f"Unsupported binary op: {type(node.op)}")
        try:
            return op(left, right)
        except ZeroDivisionError:
            raise EvalError("Division by zero")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise EvalError("Only simple function calls allowed")
        name = node.func.id
        if name not in SAFE_BUILTINS:
            raise EvalError(f"Disallowed function: {name!r}")
        args = [_eval_node(a, variables) for a in node.args]
        try:
            return SAFE_BUILTINS[name](*args)
        except TypeError as e:
            raise EvalError(f"Function call error: {name}({len(args)} args): {e}")
    raise EvalError(f"Unsupported AST node: {type(node)}")
