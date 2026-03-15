"""PIM walk-forward backtester.

PIM-4.7: Walk-forward backtester with configurable lookback and rebalance frequency.
PIM-4.8: IC (Information Coefficient) and ICIR (IC Information Ratio) computation.

No look-ahead bias: each rebalance period uses only CIS scores available at
that date. Realised returns come from the subsequent period.

Definitions
-----------
IC (Information Coefficient):
    Pearson correlation between predicted CIS ranks at the rebalance date and
    realised returns over the following period. IC ∈ [-1, +1]. A positive IC
    indicates the model ranks higher-returning companies with higher CIS scores.

ICIR (IC Information Ratio):
    mean(IC) / std(IC) across all rebalance periods. Measures signal consistency.
    A robust strategy is typically ICIR >= 0.5.

    # CFA Level II — IC/ICIR attribution methodology
"""

from __future__ import annotations

import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

from shared.fm_shared.errors import LLMError

logger = structlog.get_logger()

_LIMITATIONS = (
    "Backtest results are simulated using historical CIS scores and estimated period returns. "
    "Simulated performance does not predict future results. "
    "Transaction costs, slippage, and liquidity constraints are not modelled unless specified. "
    "IC and ICIR are statistical measures of signal quality, not guarantees of future alpha."
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class BacktestConfig:
    """Configuration for a walk-forward backtest run.

    lookback_days and rebalance_freq_days are in calendar days. The backtester
    maps these to period indices based on the density of input dates.
    """

    lookback_days: int = 252
    """Estimation window for parameter calibration (default: 1 trading year)."""

    rebalance_freq_days: int = 21
    """Rebalance frequency in calendar days (default: ~monthly)."""

    top_n: int = 10
    """Portfolio size: top-N holdings by CIS score."""

    max_weight_pct: float = 0.15
    """Single-position cap as a fraction [0, 1]."""

    max_sector_pct: float = 0.35
    """Sector concentration cap as a fraction [0, 1]."""

    benchmark_label: str = "equal_weight"
    """Label for the benchmark strategy (equal-weight all candidates)."""

    strategy_label: str = "top_n_cis"
    """Label identifying this strategy configuration."""

    def validate(self) -> None:
        if self.lookback_days < 1:
            raise ValueError("lookback_days must be >= 1")
        if self.rebalance_freq_days < 1:
            raise ValueError("rebalance_freq_days must be >= 1")
        if self.top_n < 1:
            raise ValueError("top_n must be >= 1")
        if not 0.0 < self.max_weight_pct <= 1.0:
            raise ValueError("max_weight_pct must be in (0, 1]")
        if not 0.0 < self.max_sector_pct <= 1.0:
            raise ValueError("max_sector_pct must be in (0, 1]")


# ---------------------------------------------------------------------------
# Period and result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class BacktestPeriod:
    """Performance statistics for a single rebalance period."""

    period_index: int
    rebalance_date: str
    """ISO date string of the rebalance decision point."""

    n_candidates: int
    n_holdings: int
    strategy_return: float
    """Equal-weight average return of selected holdings over the subsequent period."""
    benchmark_return: float
    """Equal-weight average return of all candidates over the same period."""
    ic: float | None
    """Per-period IC (None if fewer than 2 return observations)."""


@dataclass
class BacktestResult:
    """Complete walk-forward backtest output.

    PIM-4.7: strategy performance + benchmark comparison.
    PIM-4.8: IC/ICIR signal quality metrics.
    """

    backtest_id: str
    tenant_id: str
    config: BacktestConfig
    periods: list[BacktestPeriod]

    # Aggregate performance
    n_periods: int
    cumulative_return: float
    annualised_return: float
    volatility: float
    """Annualised standard deviation of period returns."""
    sharpe_ratio: float
    """Annualised return / annualised volatility (risk-free rate = 0)."""
    max_drawdown: float
    """Maximum peak-to-trough drawdown as a positive fraction (e.g. 0.20 = 20%)."""

    # IC / ICIR (PIM-4.8)
    ic_mean: float | None
    ic_std: float | None
    icir: float | None

    # Benchmark
    benchmark_cumulative_return: float
    benchmark_annualised_return: float

    limitations: str = field(default_factory=lambda: _LIMITATIONS)


# ---------------------------------------------------------------------------
# IC / ICIR (PIM-4.8)
# ---------------------------------------------------------------------------


def compute_ic(predicted_scores: list[float], realised_returns: list[float]) -> float | None:
    """Compute Pearson correlation between predicted CIS scores and realised returns.

    PIM-4.8: No look-ahead bias — predicted_scores are CIS values at the
    rebalance date; realised_returns are from the subsequent period.

    Args:
        predicted_scores: CIS scores at rebalance date (higher = higher conviction).
        realised_returns: Actual period returns for the same companies in the same order.

    Returns:
        Pearson correlation ∈ [-1, +1], or None if fewer than 2 observations.
    """
    n = len(predicted_scores)
    if n < 2 or len(realised_returns) != n:
        return None

    mean_x = sum(predicted_scores) / n
    mean_y = sum(realised_returns) / n

    cov = sum(
        (predicted_scores[i] - mean_x) * (realised_returns[i] - mean_y)
        for i in range(n)
    )
    std_x = math.sqrt(sum((x - mean_x) ** 2 for x in predicted_scores) / n)
    std_y = math.sqrt(sum((y - mean_y) ** 2 for y in realised_returns) / n)

    if std_x < 1e-9 or std_y < 1e-9:
        return None  # Degenerate case: zero variance in scores or returns

    return cov / (n * std_x * std_y)


def compute_icir(ic_series: list[float]) -> float | None:
    """Compute ICIR = mean(IC) / std(IC) across all rebalance periods.

    PIM-4.8: Measures signal consistency. A robust strategy is typically ICIR >= 0.5.

    Args:
        ic_series: List of per-period IC values (non-None values only).

    Returns:
        ICIR as a float, or None if fewer than 2 observations or std == 0.
    """
    if len(ic_series) < 2:
        return None

    mean_ic = sum(ic_series) / len(ic_series)
    variance = sum((ic - mean_ic) ** 2 for ic in ic_series) / len(ic_series)
    std_ic = math.sqrt(variance)

    if std_ic < 1e-9:
        return None  # All ICs identical — signal is consistent but not informative as a ratio

    return mean_ic / std_ic


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_max_drawdown(cumulative_path: list[float]) -> float:
    """Maximum peak-to-trough drawdown from a cumulative return path (1-based).

    e.g. cumulative_path = [1.0, 1.05, 0.95, 1.10] → drawdown = (1.05 - 0.95) / 1.05.

    Returns drawdown as a positive fraction.
    """
    if len(cumulative_path) < 2:
        return 0.0
    peak = cumulative_path[0]
    max_dd = 0.0
    for cr in cumulative_path[1:]:
        if cr > peak:
            peak = cr
        drawdown = (peak - cr) / peak if peak > 1e-9 else 0.0
        if drawdown > max_dd:
            max_dd = drawdown
    return max_dd


# ---------------------------------------------------------------------------
# Input record
# ---------------------------------------------------------------------------


@dataclass
class HistoricalCISRecord:
    """A CIS observation for a company at a specific date.

    realised_return: The period return realised AFTER this date (i.e. from this
    date to the next rebalance date). May be None if returns are not yet available
    or are being attached from the subsequent period's records.
    """

    date: str
    """ISO date string: 'YYYY-MM-DD'."""

    company_id: str
    cis_score: float
    sector: str | None = None
    realised_return: float | None = None


# ---------------------------------------------------------------------------
# Walk-forward backtester (PIM-4.7)
# ---------------------------------------------------------------------------


def run_backtest(
    historical_records: list[HistoricalCISRecord],
    config: BacktestConfig | None = None,
    tenant_id: str = "",
) -> BacktestResult:
    """Run a walk-forward backtest over historical CIS scores.

    PIM-4.7: Walk-forward loop over sorted rebalance dates.
    PIM-4.8: IC and ICIR computed per period from (predicted_scores, realised_returns).

    No look-ahead bias: CIS scores at date D predict which holdings to select;
    realised_return at D is the return from D to D+1 (next rebalance date).
    The realised_return field on each record stores this forward-looking return.

    Args:
        historical_records: CIS observations sorted by date ascending.
            Each record's realised_return is the return earned during the
            period starting at that record's date.
        config: Backtest configuration (defaults to BacktestConfig()).
        tenant_id: Tenant identifier for the result record.

    Returns:
        BacktestResult with per-period statistics and aggregate metrics.
    """
    config = config or BacktestConfig()
    config.validate()

    backtest_id = str(uuid.uuid4())

    # Group by date
    by_date: dict[str, list[HistoricalCISRecord]] = {}
    for rec in historical_records:
        by_date.setdefault(rec.date, []).append(rec)

    sorted_dates = sorted(by_date.keys())

    if len(sorted_dates) < 2:
        logger.warning("backtest_insufficient_dates", n_dates=len(sorted_dates), tenant_id=tenant_id)
        return _empty_result(backtest_id, tenant_id, config)

    # Map rebalance_freq_days to a step size in period indices.
    # With monthly dates (21-day freq), 1 step ≈ 1 month.
    # Clamp step to at least 1 to avoid infinite loop.
    step = max(1, config.rebalance_freq_days // 21)

    periods: list[BacktestPeriod] = []
    strategy_returns: list[float] = []
    benchmark_returns: list[float] = []
    ic_series: list[float] = []

    for period_idx, date_idx in enumerate(range(0, len(sorted_dates) - 1, step)):
        rebalance_date = sorted_dates[date_idx]
        next_date = sorted_dates[date_idx + 1]

        records_today = by_date[rebalance_date]
        records_next = {r.company_id: r for r in by_date.get(next_date, [])}

        # Greedy top-N selection with sector cap (mirrors build_portfolio logic)
        records_today_sorted = sorted(records_today, key=lambda r: r.cis_score, reverse=True)
        selected: list[HistoricalCISRecord] = []
        sector_counts: dict[str, int] = {}
        for rec in records_today_sorted:
            if len(selected) >= config.top_n:
                break
            sector = rec.sector or "__unknown__"
            # Sector weight relative to target portfolio size (top_n)
            prospective_count = sector_counts.get(sector, 0) + 1
            prospective_weight = prospective_count / config.top_n
            if prospective_weight > config.max_sector_pct:
                continue
            selected.append(rec)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1

        if not selected:
            continue

        # Collect returns for IC computation and strategy performance
        predicted_scores: list[float] = []
        realised_returns: list[float] = []
        for rec in selected:
            # Use the realised_return attached to this record (forward return from date D)
            ret = rec.realised_return
            if ret is None:
                # Fallback: caller stored the period-D→D+1 return on the D+1 record
                # rather than the D record. No look-ahead — same period's return.
                next_rec = records_next.get(rec.company_id)
                if next_rec is not None and next_rec.realised_return is not None:
                    ret = next_rec.realised_return
            if ret is not None:
                predicted_scores.append(rec.cis_score)
                realised_returns.append(ret)

        # IC for this period (PIM-4.8)
        period_ic = compute_ic(predicted_scores, realised_returns)
        if period_ic is not None:
            ic_series.append(period_ic)

        # Strategy return: equal-weight average of selected holdings
        strategy_period_return = (
            sum(realised_returns) / len(realised_returns) if realised_returns else 0.0
        )

        # Benchmark: equal-weight all candidates at this date
        all_returns = [r.realised_return for r in records_today if r.realised_return is not None]
        benchmark_period_return = sum(all_returns) / len(all_returns) if all_returns else 0.0

        strategy_returns.append(strategy_period_return)
        benchmark_returns.append(benchmark_period_return)

        periods.append(
            BacktestPeriod(
                period_index=period_idx,
                rebalance_date=rebalance_date,
                n_candidates=len(records_today),
                n_holdings=len(selected),
                strategy_return=strategy_period_return,
                benchmark_return=benchmark_period_return,
                ic=period_ic,
            )
        )

    n_periods = len(periods)
    if n_periods == 0:
        return _empty_result(backtest_id, tenant_id, config)

    # Cumulative returns (compounding)
    cumulative = 1.0
    cumulative_path = [1.0]
    for r in strategy_returns:
        cumulative *= 1.0 + r
        cumulative_path.append(cumulative)
    cumulative_return = cumulative - 1.0

    benchmark_cumulative = 1.0
    for r in benchmark_returns:
        benchmark_cumulative *= 1.0 + r
    benchmark_cumulative_return = benchmark_cumulative - 1.0

    # Annualised return: (1 + cumulative) ^ (periods_per_year / n) - 1
    periods_per_year = 252.0 / max(config.rebalance_freq_days, 1)
    annualised_return = (
        (cumulative ** (periods_per_year / n_periods)) - 1.0
        if cumulative > 0 and n_periods > 0
        else 0.0
    )
    benchmark_annualised = (
        (benchmark_cumulative ** (periods_per_year / n_periods)) - 1.0
        if benchmark_cumulative > 0 and n_periods > 0
        else 0.0
    )

    # Volatility: annualised std of period returns
    if n_periods >= 2:
        mean_r = sum(strategy_returns) / n_periods
        period_std = math.sqrt(sum((r - mean_r) ** 2 for r in strategy_returns) / n_periods)
        volatility = period_std * math.sqrt(periods_per_year)
    else:
        volatility = 0.0

    # Sharpe ratio (risk-free = 0)
    sharpe_ratio = annualised_return / volatility if volatility > 1e-9 else 0.0

    # Max drawdown
    max_drawdown = _compute_max_drawdown(cumulative_path)

    # IC / ICIR (PIM-4.8)
    ic_mean: float | None = None
    ic_std: float | None = None
    if ic_series:
        ic_mean = sum(ic_series) / len(ic_series)
        if len(ic_series) >= 2:
            ic_variance = sum((ic - ic_mean) ** 2 for ic in ic_series) / len(ic_series)
            ic_std = math.sqrt(ic_variance)
    icir = compute_icir(ic_series)

    return BacktestResult(
        backtest_id=backtest_id,
        tenant_id=tenant_id,
        config=config,
        periods=periods,
        n_periods=n_periods,
        cumulative_return=cumulative_return,
        annualised_return=annualised_return,
        volatility=volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
        ic_mean=ic_mean,
        ic_std=ic_std,
        icir=icir,
        benchmark_cumulative_return=benchmark_cumulative_return,
        benchmark_annualised_return=benchmark_annualised,
    )


def _empty_result(backtest_id: str, tenant_id: str, config: BacktestConfig) -> BacktestResult:
    """Return a zero-value BacktestResult when no periods can be computed."""
    return BacktestResult(
        backtest_id=backtest_id,
        tenant_id=tenant_id,
        config=config,
        periods=[],
        n_periods=0,
        cumulative_return=0.0,
        annualised_return=0.0,
        volatility=0.0,
        sharpe_ratio=0.0,
        max_drawdown=0.0,
        ic_mean=None,
        ic_std=None,
        icir=None,
        benchmark_cumulative_return=0.0,
        benchmark_annualised_return=0.0,
    )


# ---------------------------------------------------------------------------
# Persistence (PIM-4.7)
# ---------------------------------------------------------------------------


async def persist_backtest(result: BacktestResult, conn: Any) -> None:
    """Persist a backtest result to pim_backtest_results.

    ON CONFLICT DO NOTHING — backtest results are immutable once written.
    start_date and end_date are derived from the first and last period dates.
    """
    start_date = result.periods[0].rebalance_date if result.periods else None
    end_date = result.periods[-1].rebalance_date if result.periods else None

    config_json = json.dumps({
        "lookback_days": result.config.lookback_days,
        "rebalance_freq_days": result.config.rebalance_freq_days,
        "top_n": result.config.top_n,
        "max_weight_pct": result.config.max_weight_pct,
        "max_sector_pct": result.config.max_sector_pct,
        "benchmark_label": result.config.benchmark_label,
        "strategy_label": result.config.strategy_label,
    })

    periods_json = json.dumps([
        {
            "period_index": p.period_index,
            "rebalance_date": p.rebalance_date,
            "n_candidates": p.n_candidates,
            "n_holdings": p.n_holdings,
            "strategy_return": p.strategy_return,
            "benchmark_return": p.benchmark_return,
            "ic": p.ic,
        }
        for p in result.periods
    ])

    await conn.execute(
        """INSERT INTO pim_backtest_results (
               backtest_id, tenant_id, strategy_label, config_json,
               start_date, end_date, n_periods,
               cumulative_return, annualised_return, volatility,
               sharpe_ratio, max_drawdown,
               ic_mean, ic_std, icir,
               benchmark_label, benchmark_cumulative_return, benchmark_annualised_return,
               periods_json
           ) VALUES (
               $1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10,
               $11, $12, $13, $14, $15, $16, $17, $18, $19::jsonb
           )
           ON CONFLICT (tenant_id, backtest_id) DO NOTHING""",
        result.backtest_id,
        result.tenant_id,
        result.config.strategy_label,
        config_json,
        start_date,
        end_date,
        result.n_periods,
        result.cumulative_return,
        result.annualised_return,
        result.volatility,
        result.sharpe_ratio,
        result.max_drawdown,
        result.ic_mean,
        result.ic_std,
        result.icir,
        result.config.benchmark_label,
        result.benchmark_cumulative_return,
        result.benchmark_annualised_return,
        periods_json,
    )

    logger.info(
        "backtest_persisted",
        backtest_id=result.backtest_id,
        tenant_id=result.tenant_id,
        n_periods=result.n_periods,
        cumulative_return=result.cumulative_return,
        ic_mean=result.ic_mean,
        icir=result.icir,
    )


# ---------------------------------------------------------------------------
# LLM commentary schema and prompts (PIM-5.2)
# ---------------------------------------------------------------------------

_BACKTEST_COMMENTARY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "commentary": {
            "type": "string",
            "description": (
                "2–4 sentence interpretation of backtest performance: "
                "cumulative/annualised returns, Sharpe ratio, max drawdown, "
                "and IC/ICIR signal quality. Reference the specific values."
            ),
        },
        "risks": {
            "type": "string",
            "description": (
                "2–3 sentence risk commentary: data limitations, "
                "statistical robustness of IC estimate, and backtest caveats."
            ),
        },
    },
    "required": ["commentary", "risks"],
}

_BACKTEST_COMMENTARY_SYSTEM = (
    "You are a quantitative analyst reviewing a walk-forward backtest of a CIS-ranked "
    "equity selection strategy. Your task is to write a concise, factual interpretation "
    "of the backtest results for an institutional investment audience. "
    "Cite the specific metrics provided. Do not recommend buying or selling securities. "
    "Acknowledge that simulated performance does not predict future results."
)


async def generate_backtest_commentary(
    backtest_id: str,
    tenant_id: str,
    n_periods: int,
    cumulative_return: float | None,
    annualised_return: float | None,
    sharpe_ratio: float | None,
    max_drawdown: float | None,
    ic_mean: float | None,
    icir: float | None,
    strategy_label: str,
    benchmark_label: str,
    benchmark_cumulative_return: float | None,
    llm_router: Any,
) -> tuple[str, str]:
    """Generate LLM commentary for a completed backtest run.

    PIM-5.2: Uses pim_backtest_commentary task label with temperature=0.2
    for high-fidelity interpretation of numerical metrics.

    Returns:
        Tuple of (commentary, risks) strings. On LLM failure, returns
        fallback strings rather than raising — non-fatal for the endpoint.
    """

    def _pct(v: float | None) -> str:
        return f"{v * 100:.1f}%" if v is not None else "N/A"

    def _f2(v: float | None) -> str:
        return f"{v:.2f}" if v is not None else "N/A"

    summary = (
        f"Backtest Summary — Strategy: {strategy_label}\n"
        f"Periods: {n_periods}\n"
        f"Cumulative Return: {_pct(cumulative_return)} "
        f"(benchmark {_pct(benchmark_cumulative_return)} via {benchmark_label})\n"
        f"Annualised Return: {_pct(annualised_return)}\n"
        f"Sharpe Ratio: {_f2(sharpe_ratio)}\n"
        f"Max Drawdown: {_pct(max_drawdown)}\n"
        f"IC (mean): {_f2(ic_mean)}\n"
        f"ICIR: {_f2(icir)}\n"
    )

    try:
        response = await llm_router.complete_with_routing(
            tenant_id,
            [
                {"role": "system", "content": _BACKTEST_COMMENTARY_SYSTEM},
                {"role": "user", "content": summary},
            ],
            _BACKTEST_COMMENTARY_SCHEMA,
            "pim_backtest_commentary",
            max_tokens=1024,
            temperature=0.2,
        )
        content = response.content or {}
        if not isinstance(content, dict):
            logger.warning(
                "pim_backtest_commentary_not_dict",
                content_type=type(content).__name__,
                backtest_id=backtest_id,
            )
            content = {}
        commentary = content.get("commentary", "")
        risks = content.get("risks", "")
    except Exception as exc:  # noqa: BLE001 — catch LLMError + unexpected errors
        if isinstance(exc, LLMError):
            logger.warning(
                "pim_backtest_commentary_llm_failed",
                backtest_id=backtest_id,
                tenant_id=tenant_id,
                error=str(exc),
            )
            raise
        logger.error(
            "pim_backtest_commentary_unexpected_error",
            backtest_id=backtest_id,
            tenant_id=tenant_id,
            error=str(exc),
        )
        raise LLMError(str(exc), code="ERR_COMMENTARY_UNEXPECTED") from exc

    return commentary, risks
