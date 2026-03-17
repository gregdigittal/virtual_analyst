"""DTF-A: Markov model manual calibration CLI.

Developer tool — never call from API routes.

Usage:
  python tools/dtf/calibrate.py inspect
  python tools/dtf/calibrate.py validate
  python tools/dtf/calibrate.py override --from-state 0 --to-state 1 --probability 0.15
  python tools/dtf/calibrate.py reset

Operations:
  inspect   — print current transition matrix dimensions + top-5 steady-state states
  validate  — assert all rows sum to 1.0 ± 1e-9; print PASS/FAIL per row
  override  — set transition probability P(from→to); re-normalises the row
  reset     — restore matrix to the version computed from observed data

Tables used:
  pim_markov_matrices      — one row per tenant/matrix version
  pim_markov_transitions   — 6561 rows (81×81) per matrix version
  pim_markov_transitions_baseline — snapshot for reset (created on first reset call)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import numpy as np

N_STATES = 81
_TOLERANCE = 1e-9


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


async def _get_conn() -> asyncpg.Connection:  # type: ignore[type-arg]
    """Open a single asyncpg connection using DATABASE_URL."""
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/finmodel_dev")
    return await asyncpg.connect(db_url)


async def _fetch_latest_matrix_id(conn: asyncpg.Connection, tenant_id: str) -> str | None:  # type: ignore[type-arg]
    """Return the most recent matrix_id for the given tenant."""
    row = await conn.fetchrow(
        """
        SELECT matrix_id
        FROM pim_markov_matrices
        WHERE tenant_id = $1
        ORDER BY estimated_at DESC
        LIMIT 1
        """,
        tenant_id,
    )
    return str(row["matrix_id"]) if row else None


async def _fetch_transitions(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    tenant_id: str,
    matrix_id: str,
) -> list[Any]:
    """Fetch all transition rows for a matrix."""
    rows: list[Any] = await conn.fetch(
        """
        SELECT from_state, to_state, probability
        FROM pim_markov_transitions
        WHERE tenant_id = $1 AND matrix_id = $2
        ORDER BY from_state, to_state
        """,
        tenant_id,
        matrix_id,
    )
    return rows


def _build_matrix_from_rows(rows: list[Any]) -> np.ndarray:
    """Reconstruct the 81×81 numpy matrix from DB rows."""
    matrix = np.zeros((N_STATES, N_STATES), dtype=np.float64)
    for r in rows:
        matrix[r["from_state"]][r["to_state"]] = r["probability"]
    return matrix


# ---------------------------------------------------------------------------
# Pure validation logic (exported for tests)
# ---------------------------------------------------------------------------


def validate_row_sums(
    matrix: np.ndarray,
    tolerance: float = _TOLERANCE,
) -> list[tuple[int, float, bool]]:
    """Validate that each row of the matrix sums to 1.0 ± tolerance.

    Returns a list of (row_index, row_sum, passed) tuples.
    """
    results: list[tuple[int, float, bool]] = []
    for i in range(matrix.shape[0]):
        row_sum = float(matrix[i].sum())
        passed = abs(row_sum - 1.0) <= tolerance
        results.append((i, row_sum, passed))
    return results


def renormalise_row(row_probs: dict[int, float], override_to: int, override_prob: float) -> dict[int, float]:
    """Set P(from→override_to) = override_prob, then re-normalise the row to sum to 1.0.

    Args:
        row_probs:      Current {to_state: probability} mapping for the from_state row.
        override_to:    The to_state index whose probability is being overridden.
        override_prob:  The new probability for (from_state → override_to).

    Returns:
        New {to_state: probability} mapping with all values summing to 1.0.
    """
    updated = {k: v for k, v in row_probs.items()}
    updated[override_to] = override_prob

    total = sum(updated.values())
    if total == 0.0:
        # Degenerate case: distribute uniformly
        n = len(updated)
        return {k: 1.0 / n for k in updated}

    return {k: v / total for k, v in updated.items()}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


async def cmd_inspect(tenant_id: str) -> None:
    """Print matrix dimensions and top-5 steady-state states."""
    conn = await _get_conn()
    try:
        matrix_id = await _fetch_latest_matrix_id(conn, tenant_id)
        if matrix_id is None:
            print(f"No Markov matrix found for tenant '{tenant_id}'.")
            return

        rows = await _fetch_transitions(conn, tenant_id, matrix_id)
        print(f"Matrix ID  : {matrix_id}")
        print(f"Rows in DB : {len(rows)}")

        if not rows:
            print("No transition rows — matrix is empty.")
            return

        matrix = _build_matrix_from_rows(rows)
        print(f"Dimensions : {matrix.shape[0]} x {matrix.shape[1]}")

        # Power iteration to find steady-state
        pi = np.ones(N_STATES, dtype=np.float64) / N_STATES
        for _ in range(10_000):
            pi_new = pi @ matrix
            if np.allclose(pi_new, pi, atol=1e-12):
                break
            pi = pi_new

        top_idx = np.argsort(pi)[::-1][:5]
        print("\nTop-5 steady-state states:")
        for rank, idx in enumerate(top_idx, 1):
            print(f"  {rank}. state {int(idx):3d}  p={pi[idx]:.6f}")
    finally:
        await conn.close()


async def cmd_validate(tenant_id: str) -> bool:
    """Validate all row sums; returns True if all pass, False if any fail."""
    conn = await _get_conn()
    try:
        matrix_id = await _fetch_latest_matrix_id(conn, tenant_id)
        if matrix_id is None:
            print(f"No Markov matrix found for tenant '{tenant_id}'.")
            return False

        rows = await _fetch_transitions(conn, tenant_id, matrix_id)
        if not rows:
            print("No transition rows — nothing to validate.")
            return False

        matrix = _build_matrix_from_rows(rows)
        results = validate_row_sums(matrix)

        all_pass = True
        for row_idx, row_sum, passed in results:
            status = "PASS" if passed else "FAIL"
            print(f"ROW {row_idx:3d}: {status} ({row_sum:.10f})")
            if not passed:
                all_pass = False

        if all_pass:
            print("\nAll rows PASS.")
        else:
            print("\nSome rows FAILED — matrix may be corrupted.")
        return all_pass
    finally:
        await conn.close()


async def cmd_override(
    tenant_id: str,
    from_state: int,
    to_state: int,
    probability: float,
) -> None:
    """Override a single transition probability and re-normalise the row."""
    if not (0 <= from_state < N_STATES):
        print(f"ERROR: from_state must be in [0, {N_STATES - 1}]")
        sys.exit(1)
    if not (0 <= to_state < N_STATES):
        print(f"ERROR: to_state must be in [0, {N_STATES - 1}]")
        sys.exit(1)
    if not (0.0 <= probability <= 1.0):
        print("ERROR: probability must be in [0.0, 1.0]")
        sys.exit(1)

    conn = await _get_conn()
    try:
        matrix_id = await _fetch_latest_matrix_id(conn, tenant_id)
        if matrix_id is None:
            print(f"No Markov matrix found for tenant '{tenant_id}'.")
            sys.exit(1)

        # Fetch current row
        current_row_rows = await conn.fetch(
            """
            SELECT to_state, probability
            FROM pim_markov_transitions
            WHERE tenant_id = $1 AND matrix_id = $2 AND from_state = $3
            """,
            tenant_id,
            matrix_id,
            from_state,
        )

        row_probs: dict[int, float] = {r["to_state"]: r["probability"] for r in current_row_rows}

        # Ensure all to_states exist (fill zeros for missing)
        for j in range(N_STATES):
            if j not in row_probs:
                row_probs[j] = 0.0

        new_probs = renormalise_row(row_probs, to_state, probability)

        # Update DB in a transaction
        async with conn.transaction():
            for j, p in new_probs.items():
                await conn.execute(
                    """
                    INSERT INTO pim_markov_transitions (tenant_id, matrix_id, from_state, to_state, probability)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (tenant_id, matrix_id, from_state, to_state)
                    DO UPDATE SET probability = EXCLUDED.probability
                    """,
                    tenant_id,
                    matrix_id,
                    from_state,
                    j,
                    p,
                )

        new_row_sum = sum(new_probs.values())
        print(
            f"Override applied: P({from_state}→{to_state}) = {probability:.6f}"
        )
        print(f"Row {from_state} re-normalised. New row sum: {new_row_sum:.10f}")
    finally:
        await conn.close()


async def cmd_reset(tenant_id: str) -> None:
    """Restore matrix from baseline snapshot, or create the baseline if it doesn't exist."""
    conn = await _get_conn()
    try:
        matrix_id = await _fetch_latest_matrix_id(conn, tenant_id)
        if matrix_id is None:
            print(f"No Markov matrix found for tenant '{tenant_id}'.")
            sys.exit(1)

        # Check if baseline table exists
        baseline_exists: bool = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = 'pim_markov_transitions_baseline'
            )
            """
        )

        if not baseline_exists:
            # Create baseline table and snapshot current data
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pim_markov_transitions_baseline (
                    tenant_id   text    NOT NULL,
                    matrix_id   text    NOT NULL,
                    from_state  integer NOT NULL,
                    to_state    integer NOT NULL,
                    probability double precision NOT NULL,
                    PRIMARY KEY (tenant_id, matrix_id, from_state, to_state)
                )
                """
            )
            await conn.execute(
                """
                INSERT INTO pim_markov_transitions_baseline
                    (tenant_id, matrix_id, from_state, to_state, probability)
                SELECT tenant_id, matrix_id, from_state, to_state, probability
                FROM pim_markov_transitions
                WHERE tenant_id = $1 AND matrix_id = $2
                ON CONFLICT DO NOTHING
                """,
                tenant_id,
                matrix_id,
            )
            print("Baseline created — nothing to reset yet.")
            return

        # Check if baseline has data for this matrix
        baseline_count: int = await conn.fetchval(
            "SELECT COUNT(*) FROM pim_markov_transitions_baseline WHERE tenant_id = $1 AND matrix_id = $2",
            tenant_id,
            matrix_id,
        )

        if baseline_count == 0:
            # Snapshot current data as the baseline
            await conn.execute(
                """
                INSERT INTO pim_markov_transitions_baseline
                    (tenant_id, matrix_id, from_state, to_state, probability)
                SELECT tenant_id, matrix_id, from_state, to_state, probability
                FROM pim_markov_transitions
                WHERE tenant_id = $1 AND matrix_id = $2
                ON CONFLICT DO NOTHING
                """,
                tenant_id,
                matrix_id,
            )
            print("Baseline created — nothing to reset yet.")
            return

        # Restore from baseline
        async with conn.transaction():
            await conn.execute(
                """
                DELETE FROM pim_markov_transitions
                WHERE tenant_id = $1 AND matrix_id = $2
                """,
                tenant_id,
                matrix_id,
            )
            await conn.execute(
                """
                INSERT INTO pim_markov_transitions
                    (tenant_id, matrix_id, from_state, to_state, probability)
                SELECT tenant_id, matrix_id, from_state, to_state, probability
                FROM pim_markov_transitions_baseline
                WHERE tenant_id = $1 AND matrix_id = $2
                """,
                tenant_id,
                matrix_id,
            )

        print(f"Matrix {matrix_id} restored from baseline ({baseline_count} rows).")
    finally:
        await conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DTF-A: Markov model manual calibration CLI."
    )
    parser.add_argument(
        "--tenant-id",
        default=os.environ.get("DTF_TENANT_ID", ""),
        help="Tenant ID (or set DTF_TENANT_ID env var)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inspect", help="Print matrix dimensions and top-5 steady-state states")
    subparsers.add_parser("validate", help="Assert all rows sum to 1.0 ± 1e-9")

    override_parser = subparsers.add_parser("override", help="Override a transition probability")
    override_parser.add_argument("--from-state", type=int, required=True, help="Source state index [0–80]")
    override_parser.add_argument("--to-state", type=int, required=True, help="Target state index [0–80]")
    override_parser.add_argument("--probability", type=float, required=True, help="New probability [0.0–1.0]")

    subparsers.add_parser("reset", help="Restore matrix from baseline snapshot")

    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tenant_id = args.tenant_id
    if not tenant_id:
        print("ERROR: --tenant-id or DTF_TENANT_ID env var required.")
        sys.exit(1)

    if args.command == "inspect":
        asyncio.run(cmd_inspect(tenant_id))
    elif args.command == "validate":
        passed = asyncio.run(cmd_validate(tenant_id))
        if not passed:
            sys.exit(1)
    elif args.command == "override":
        asyncio.run(cmd_override(tenant_id, args.from_state, args.to_state, args.probability))
    elif args.command == "reset":
        asyncio.run(cmd_reset(tenant_id))


if __name__ == "__main__":
    main()
