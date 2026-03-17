"""Unit tests for DTF-A calibrate.py — pure logic functions only.

No database connection required.  All asyncpg calls are mocked.
"""

from __future__ import annotations

import numpy as np
import pytest

from tools.dtf.calibrate import renormalise_row, validate_row_sums

# ---------------------------------------------------------------------------
# validate_row_sums tests
# ---------------------------------------------------------------------------


def test_validate_perfect_matrix() -> None:
    """All rows sum to exactly 1.0 — all should PASS."""
    # 3x3 uniform matrix: each row sums to 1.0 exactly
    matrix = np.array(
        [
            [1 / 3, 1 / 3, 1 / 3],
            [0.5, 0.25, 0.25],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float64,
    )
    results = validate_row_sums(matrix)

    assert len(results) == 3
    for row_idx, row_sum, passed in results:
        assert passed, f"Row {row_idx} unexpectedly failed with sum={row_sum:.10f}"


def test_validate_imperfect_matrix() -> None:
    """One row sums to 1.01 — that row should FAIL, others should PASS."""
    matrix = np.array(
        [
            [1 / 3, 1 / 3, 1 / 3],   # row 0: sum = 1.0 (PASS)
            [0.5, 0.26, 0.25],        # row 1: sum = 1.01 (FAIL)
            [0.0, 0.0, 1.0],          # row 2: sum = 1.0 (PASS)
        ],
        dtype=np.float64,
    )
    results = validate_row_sums(matrix)

    assert len(results) == 3

    row_0_passed = results[0][2]
    row_1_passed = results[1][2]
    row_2_passed = results[2][2]

    assert row_0_passed, "Row 0 should PASS"
    assert not row_1_passed, "Row 1 should FAIL (sum ≈ 1.01)"
    assert row_2_passed, "Row 2 should PASS"


def test_validate_returns_correct_sums() -> None:
    """validate_row_sums returns the actual row sums, not approximations."""
    matrix = np.array([[0.6, 0.4], [0.3, 0.7]], dtype=np.float64)
    results = validate_row_sums(matrix)

    for _, row_sum, _ in results:
        assert abs(row_sum - 1.0) < 1e-9, f"Row sum {row_sum} is not 1.0"


def test_validate_all_fail_matrix() -> None:
    """A matrix where every row sums to 0.5 — all rows should FAIL."""
    matrix = np.full((3, 3), 1 / 6, dtype=np.float64)  # each row sums to 0.5
    results = validate_row_sums(matrix)

    for row_idx, _, passed in results:
        assert not passed, f"Row {row_idx} should FAIL"


# ---------------------------------------------------------------------------
# renormalise_row tests
# ---------------------------------------------------------------------------


def test_override_renormalises_row() -> None:
    """After setting P(0→1)=0.5, the entire row must sum to 1.0."""
    # Simulate a 3-state row: {0: 0.4, 1: 0.4, 2: 0.2}
    row_probs = {0: 0.4, 1: 0.4, 2: 0.2}

    result = renormalise_row(row_probs, override_to=1, override_prob=0.5)

    total = sum(result.values())
    assert abs(total - 1.0) < 1e-9, f"Row sum after override = {total:.10f}, expected 1.0"


def test_override_sets_specified_probability() -> None:
    """The overridden (from→to) cell must appear in the result, normalised proportionally."""
    row_probs = {0: 0.33, 1: 0.33, 2: 0.34}

    result = renormalise_row(row_probs, override_to=0, override_prob=0.1)

    total = sum(result.values())
    assert abs(total - 1.0) < 1e-9

    # The to_state=0 cell should be proportionally included in the normalised result
    # Its unnormalised value is 0.1; total unnormalised = 0.1 + 0.33 + 0.34 = 0.77
    expected_0 = 0.1 / (0.1 + 0.33 + 0.34)
    assert abs(result[0] - expected_0) < 1e-9


def test_override_all_zeros_distributes_uniformly() -> None:
    """If all probabilities are 0, uniform distribution is returned."""
    row_probs = {0: 0.0, 1: 0.0, 2: 0.0}

    result = renormalise_row(row_probs, override_to=1, override_prob=0.0)

    # All zero → uniform
    for v in result.values():
        assert abs(v - 1 / 3) < 1e-9


def test_override_large_row_sum_check() -> None:
    """Renormalised row must sum to 1.0 for a 81-state row."""
    row_probs = {j: 1.0 / 81 for j in range(81)}

    result = renormalise_row(row_probs, override_to=40, override_prob=0.5)

    total = sum(result.values())
    assert abs(total - 1.0) < 1e-9
