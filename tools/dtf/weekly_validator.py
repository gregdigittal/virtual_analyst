"""DTF-B: Automated weekly Markov model validation.

Developer tool — run weekly via cron or manually:
  python tools/dtf/weekly_validator.py [--weeks N] [--output path/to/report.json]

Validates that CIS scores from N weeks ago predicted actual outcomes correctly.

The validation uses pim_portfolio_holdings (cis_score column) as the CIS score source.
Actual outcome is proxied by the score change over the evaluation window
(score at t+N vs score at t), since no dedicated returns table exists.

IC = Spearman rank correlation between:
  - predicted rank  (cis_score at t, ranked descending — higher score = rank 1)
  - actual rank     (score change over N weeks, ranked descending)

Exits with code 0 if IC >= 0.4, code 1 if IC < 0.4.
Writes a JSON report to tools/dtf/reports/YYYY-MM-DD.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

IC_THRESHOLD = 0.4
MIN_OBSERVATIONS = 10
DEFAULT_WEEKS = 4

_REPORTS_DIR = Path(__file__).parent / "reports"


# ---------------------------------------------------------------------------
# Pure IC computation (exported for tests)
# ---------------------------------------------------------------------------


def compute_spearman_ic(pairs: list[tuple[float, float]]) -> float:
    """Compute Spearman rank correlation (IC) from (predicted_score, actual_score) pairs.

    Returns the IC in [-1.0, 1.0].  1.0 = perfect predictive rank agreement.

    Spearman IC = Pearson correlation of the ranks.
    Tie-handling: average rank (standard scipy convention, implemented here manually
    to avoid a scipy dependency in the CLI tool).
    """
    n = len(pairs)
    if n < 2:  # noqa: PLR2004
        return 0.0

    predicted_scores = [p[0] for p in pairs]
    actual_scores = [p[1] for p in pairs]

    def _rank(values: list[float]) -> list[float]:
        """Assign average ranks (1-based, ascending)."""
        indexed = sorted(enumerate(values), key=lambda x: x[1])
        ranks: list[float] = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j < n - 1 and indexed[j + 1][1] == indexed[j][1]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0  # 1-based average
            for k in range(i, j + 1):
                ranks[indexed[k][0]] = avg_rank
            i = j + 1
        return ranks

    pred_ranks = _rank(predicted_scores)
    actual_ranks = _rank(actual_scores)

    mean_pred = sum(pred_ranks) / n
    mean_actual = sum(actual_ranks) / n

    numerator: float = sum((pred_ranks[i] - mean_pred) * (actual_ranks[i] - mean_actual) for i in range(n))
    denom_pred: float = sum((r - mean_pred) ** 2 for r in pred_ranks) ** 0.5
    denom_actual: float = sum((r - mean_actual) ** 2 for r in actual_ranks) ** 0.5

    if denom_pred == 0.0 or denom_actual == 0.0:
        return 0.0

    return float(numerator / (denom_pred * denom_actual))


def build_report(
    evaluation_date: date,
    weeks_evaluated: int,
    pairs: list[tuple[str, float, float]],
    ic_score: float | None,
    reason: str | None = None,
) -> dict[str, Any]:
    """Build the JSON report dict.

    Args:
        evaluation_date:  Date of this validation run.
        weeks_evaluated:  Look-back window in weeks.
        pairs:            List of (company_id, predicted_score, actual_score_change).
        ic_score:         Computed IC, or None if insufficient data.
        reason:           Reason string when pass is null.

    Returns:
        Report dict matching the documented JSON schema.
    """
    n = len(pairs)

    if reason is not None:
        return {
            "date": evaluation_date.isoformat(),
            "weeks_evaluated": weeks_evaluated,
            "ic_score": None,
            "ic_threshold": IC_THRESHOLD,
            "pass": None,
            "n_observations": n,
            "reason": reason,
            "details": [],
        }

    passed = (ic_score is not None) and (ic_score >= IC_THRESHOLD)
    details = [
        {
            "company_id": company_id,
            "predicted_score": round(pred, 4),
            "actual_score_change": round(actual, 4),
        }
        for company_id, pred, actual in pairs
    ]

    return {
        "date": evaluation_date.isoformat(),
        "weeks_evaluated": weeks_evaluated,
        "ic_score": round(ic_score, 6) if ic_score is not None else None,
        "ic_threshold": IC_THRESHOLD,
        "pass": passed,
        "n_observations": n,
        "details": details,
    }


# ---------------------------------------------------------------------------
# DB access
# ---------------------------------------------------------------------------


async def _get_conn() -> asyncpg.Connection:  # type: ignore[type-arg]
    """Open a single asyncpg connection using DATABASE_URL."""
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/finmodel_dev",
    )
    return await asyncpg.connect(db_url)


async def _fetch_cis_scores_for_run(
    conn: asyncpg.Connection,  # type: ignore[type-arg]
    tenant_id: str,
    before_ts: datetime,
    after_ts: datetime,
) -> list[Any]:
    """Fetch CIS scores from the most recent portfolio run within the given window."""
    rows: list[Any] = await conn.fetch(
        """
        SELECT ph.company_id, ph.cis_score, pr.run_at
        FROM pim_portfolio_holdings ph
        JOIN pim_portfolio_runs pr
          ON ph.tenant_id = pr.tenant_id AND ph.run_id = pr.run_id
        WHERE pr.tenant_id = $1
          AND pr.run_at >= $2
          AND pr.run_at < $3
        ORDER BY pr.run_at DESC, ph.cis_score DESC
        """,
        tenant_id,
        after_ts,
        before_ts,
    )
    return rows


async def _run_validation(tenant_id: str, weeks: int) -> dict[str, Any]:
    """Core validation logic: fetch scores, compute IC, build report."""
    now_utc = datetime.now(tz=UTC)
    today = now_utc.date()

    # Window: scores from ~2*weeks ago to ~weeks ago (baseline),
    # and scores from ~weeks ago to now (outcome proxy).
    baseline_end = now_utc - timedelta(weeks=weeks)
    baseline_start = now_utc - timedelta(weeks=weeks * 2)
    outcome_end = now_utc
    outcome_start = now_utc - timedelta(weeks=weeks)

    conn = await _get_conn()
    try:
        baseline_rows = await _fetch_cis_scores_for_run(
            conn, tenant_id, before_ts=baseline_end, after_ts=baseline_start
        )
        outcome_rows = await _fetch_cis_scores_for_run(
            conn, tenant_id, before_ts=outcome_end, after_ts=outcome_start
        )
    finally:
        await conn.close()

    # Build lookup: company_id → scores
    baseline_scores: dict[str, float] = {}
    for r in baseline_rows:
        cid = r["company_id"]
        if cid not in baseline_scores:
            baseline_scores[cid] = float(r["cis_score"])

    outcome_scores: dict[str, float] = {}
    for r in outcome_rows:
        cid = r["company_id"]
        if cid not in outcome_scores:
            outcome_scores[cid] = float(r["cis_score"])

    # Intersect: only companies with both baseline and outcome scores
    common_ids = set(baseline_scores.keys()) & set(outcome_scores.keys())
    pairs: list[tuple[str, float, float]] = [
        (cid, baseline_scores[cid], outcome_scores[cid] - baseline_scores[cid])
        for cid in sorted(common_ids)
    ]

    n = len(pairs)
    if n < MIN_OBSERVATIONS:
        return build_report(today, weeks, pairs, ic_score=None, reason="insufficient_data")

    score_pairs = [(p[1], p[2]) for p in pairs]
    ic = compute_spearman_ic(score_pairs)
    return build_report(today, weeks, pairs, ic_score=ic)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="DTF-B: Automated weekly Markov model validation."
    )
    parser.add_argument(
        "--tenant-id",
        default=os.environ.get("DTF_TENANT_ID", ""),
        help="Tenant ID (or set DTF_TENANT_ID env var)",
    )
    parser.add_argument(
        "--weeks",
        type=int,
        default=DEFAULT_WEEKS,
        help=f"Look-back window in weeks (default: {DEFAULT_WEEKS})",
    )
    today_str = date.today().isoformat()
    parser.add_argument(
        "--output",
        default=str(_REPORTS_DIR / f"{today_str}.json"),
        help=f"Output JSON report path (default: tools/dtf/reports/{today_str}.json)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tenant_id = args.tenant_id
    if not tenant_id:
        print("ERROR: --tenant-id or DTF_TENANT_ID env var required.")
        sys.exit(1)

    report = asyncio.run(_run_validation(tenant_id, args.weeks))

    # Write report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)

    # Print summary
    ic_display = f"{report['ic_score']:.4f}" if report["ic_score"] is not None else "N/A"
    passed = report.get("pass")
    status = "PASS" if passed is True else ("FAIL" if passed is False else "SKIP (insufficient data)")
    print(f"Date             : {report['date']}")
    print(f"Weeks evaluated  : {report['weeks_evaluated']}")
    print(f"Observations     : {report['n_observations']}")
    print(f"IC score         : {ic_display}")
    print(f"IC threshold     : {report['ic_threshold']}")
    print(f"Result           : {status}")
    print(f"Report written   : {output_path}")

    if passed is False:
        sys.exit(1)


if __name__ == "__main__":
    main()
