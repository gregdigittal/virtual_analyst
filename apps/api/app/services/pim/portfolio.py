"""PIM portfolio construction service.

PIM-4.2: Greedy constructor — rank by CIS, apply position constraints, select top-N.
PIM-4.3: Position constraints — max single-position size, sector caps, min liquidity.
PIM-4.4: Portfolio run snapshot + versioning — persist to pim_portfolio_runs/holdings.
PIM-4.5: LLM portfolio narrative — pim_portfolio_narrative task label, temp=0.2.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

from shared.fm_shared.errors import LLMError

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# LLM schema and prompts (PIM-4.5)
# ---------------------------------------------------------------------------

_PORTFOLIO_NARRATIVE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "required": ["summary", "top_picks", "risk_note", "regime_context"],
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
            "description": "2-4 sentence overview of the portfolio construction rationale",
        },
        "top_picks": {
            "type": "string",
            "description": "Brief rationale for the top 2-3 holdings by CIS score",
        },
        "risk_note": {
            "type": "string",
            "description": "Key concentration, sector, or liquidity risks in the portfolio",
        },
        "regime_context": {
            "type": "string",
            "description": "How the current economic regime influenced selection",
        },
    },
}

_PORTFOLIO_NARRATIVE_SYSTEM = (
    "You are a quantitative portfolio analyst explaining a model-driven portfolio construction. "
    "Describe what drives the selection using only the data provided. "
    "Do not recommend buying or selling specific securities. "
    "Acknowledge that this is a quantitative model output, not investment advice. "
    "Include a limitations disclaimer referencing model uncertainty."
)

_LIMITATIONS = (
    "This portfolio is constructed by a quantitative model using CIS scores as of the run date. "
    "It does not constitute investment advice. Past model performance does not predict future returns. "
    "CIS scores are model estimates subject to data availability and estimation uncertainty."
)

# ---------------------------------------------------------------------------
# Domain dataclasses
# ---------------------------------------------------------------------------


@dataclass
class PositionConstraints:
    """Position-sizing and portfolio constraints. PIM-4.3.

    All constraints are applied greedily during selection in descending CIS order.
    """

    top_n: int = 10
    """Maximum number of holdings."""

    max_weight_pct: float = 0.15
    """Maximum single-position weight as a fraction [0, 1]. Default: 15%."""

    max_sector_pct: float = 0.35
    """Maximum sector concentration as a fraction [0, 1]. Default: 35%."""

    min_cis_score: float = 0.0
    """Minimum CIS score to be eligible. Range [0, 100]. Default: no filter."""

    min_liquidity_usd: float | None = None
    """Minimum market-cap proxy (USD). None = no liquidity filter applied."""

    def validate(self) -> None:
        if self.top_n < 1:
            raise ValueError("top_n must be >= 1")
        if not 0.0 < self.max_weight_pct <= 1.0:
            raise ValueError("max_weight_pct must be in (0, 1]")
        if not 0.0 < self.max_sector_pct <= 1.0:
            raise ValueError("max_sector_pct must be in (0, 1]")
        if not 0.0 <= self.min_cis_score <= 100.0:
            raise ValueError("min_cis_score must be in [0, 100]")


@dataclass
class PortfolioCandidate:
    """Input company candidate for portfolio construction."""

    company_id: str
    cis_score: float
    ticker: str | None = None
    name: str | None = None
    sector: str | None = None
    market_cap_usd: float | None = None
    """Market cap proxy for liquidity filtering (USD)."""

    # Factor scores — carried through to holdings for narrative + audit
    fundamental_quality: float | None = None
    fundamental_momentum: float | None = None
    idiosyncratic_sentiment: float | None = None
    sentiment_momentum: float | None = None
    sector_positioning: float | None = None


@dataclass
class PortfolioHolding:
    """A single holding in the constructed portfolio."""

    rank: int
    company_id: str
    cis_score: float
    weight: float
    """Position weight as a fraction [0, 1]."""

    ticker: str | None = None
    name: str | None = None
    sector: str | None = None

    # Factor scores (for audit trail and narrative)
    fundamental_quality: float | None = None
    fundamental_momentum: float | None = None
    idiosyncratic_sentiment: float | None = None
    sentiment_momentum: float | None = None
    sector_positioning: float | None = None


@dataclass
class PortfolioRun:
    """A complete portfolio construction run snapshot. PIM-4.4.

    Versioned by run_id (UUID). Persisted to pim_portfolio_runs and
    pim_portfolio_holdings for audit trail and UI display.
    """

    run_id: str
    tenant_id: str
    holdings: list[PortfolioHolding]
    constraints: PositionConstraints
    regime_at_run: str | None
    n_candidates: int
    n_holdings: int
    avg_cis_score: float
    """Weighted-average CIS score of selected holdings."""
    total_cis_score: float
    """Sum of CIS scores across all holdings (unweighted, for reference)."""

    # LLM narrative (PIM-4.5) — populated by generate_narrative()
    narrative: str | None = None
    narrative_top_picks: str | None = None
    narrative_risk_note: str | None = None
    narrative_regime_context: str | None = None

    limitations: str = field(default_factory=lambda: _LIMITATIONS)


# ---------------------------------------------------------------------------
# Portfolio constructor (PIM-4.2 + PIM-4.3)
# ---------------------------------------------------------------------------


def build_portfolio(
    candidates: list[PortfolioCandidate],
    constraints: PositionConstraints | None = None,
    current_regime: str | None = None,
    tenant_id: str = "",
) -> PortfolioRun:
    """Greedy portfolio constructor — rank by CIS, apply constraints, assign weights.

    PIM-4.2: Select top-N companies by CIS score.
    PIM-4.3: Enforce min_cis_score, min_liquidity_usd, max_sector_pct, max_weight_pct.

    Weight allocation: equal-weight among selected holdings, scaled down if
    equal-weight would exceed max_weight_pct.

    Sector cap is applied greedily: at each step, the prospective sector weight
    (sector_count + 1) / (selected + 1) is checked against max_sector_pct.
    If it would breach the cap, the candidate is skipped and the next is tried.

    Args:
        candidates: Companies with CIS scores and optional factor data.
        constraints: Position constraints (defaults to PositionConstraints()).
        current_regime: Economic regime at run time (expansion/contraction/transition).
        tenant_id: Tenant identifier for the run record.

    Returns:
        PortfolioRun with selected holdings and equal-weight allocations.
    """
    constraints = constraints or PositionConstraints()
    constraints.validate()

    n_candidates = len(candidates)

    # Step 1: Minimum CIS score filter
    eligible = [c for c in candidates if c.cis_score >= constraints.min_cis_score]

    # Step 2: Minimum liquidity filter (market cap proxy)
    if constraints.min_liquidity_usd is not None:
        eligible = [
            c for c in eligible
            if c.market_cap_usd is None or c.market_cap_usd >= constraints.min_liquidity_usd
        ]

    # Step 3: Sort descending by CIS score (greedy ranking — PIM-4.2)
    eligible.sort(key=lambda c: c.cis_score, reverse=True)

    # Step 4: Greedy selection with sector cap (PIM-4.3)
    selected: list[PortfolioCandidate] = []
    sector_counts: dict[str, int] = {}
    for candidate in eligible:
        if len(selected) >= constraints.top_n:
            break
        sector = candidate.sector or "__unknown__"
        # Prospective sector weight: (sector_count + 1) / top_n
        # Using top_n as denominator gives the sector weight relative to the
        # target portfolio size, preventing the first selection always failing.
        prospective_count = sector_counts.get(sector, 0) + 1
        prospective_weight = prospective_count / constraints.top_n
        if prospective_weight > constraints.max_sector_pct:
            continue  # Would breach sector cap — skip
        selected.append(candidate)
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    if not selected:
        return PortfolioRun(
            run_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            holdings=[],
            constraints=constraints,
            regime_at_run=current_regime,
            n_candidates=n_candidates,
            n_holdings=0,
            avg_cis_score=0.0,
            total_cis_score=0.0,
        )

    # Step 5: Equal-weight allocation with max_weight_pct cap (PIM-4.3)
    n = len(selected)
    equal_weight = 1.0 / n
    if equal_weight <= constraints.max_weight_pct:
        weights = [equal_weight] * n
    else:
        # Cap each holding at max_weight_pct and re-normalise
        raw = [constraints.max_weight_pct] * n
        total = sum(raw)
        weights = [w / total for w in raw]

    holdings: list[PortfolioHolding] = []
    for rank, (candidate, weight) in enumerate(zip(selected, weights, strict=True), start=1):
        holdings.append(
            PortfolioHolding(
                rank=rank,
                company_id=candidate.company_id,
                ticker=candidate.ticker,
                name=candidate.name,
                cis_score=candidate.cis_score,
                weight=weight,
                sector=candidate.sector,
                fundamental_quality=candidate.fundamental_quality,
                fundamental_momentum=candidate.fundamental_momentum,
                idiosyncratic_sentiment=candidate.idiosyncratic_sentiment,
                sentiment_momentum=candidate.sentiment_momentum,
                sector_positioning=candidate.sector_positioning,
            )
        )

    # Weighted-average CIS (weights already sum to 1.0)
    avg_cis = sum(h.cis_score * h.weight for h in holdings)
    total_cis = sum(h.cis_score for h in holdings)

    return PortfolioRun(
        run_id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        holdings=holdings,
        constraints=constraints,
        regime_at_run=current_regime,
        n_candidates=n_candidates,
        n_holdings=len(holdings),
        avg_cis_score=avg_cis,
        total_cis_score=total_cis,
    )


# ---------------------------------------------------------------------------
# Persistence (PIM-4.4)
# ---------------------------------------------------------------------------


async def persist_run(run: PortfolioRun, conn: Any) -> None:
    """Persist a portfolio run to pim_portfolio_runs and pim_portfolio_holdings.

    PIM-4.4: Upserts the run record (allowing narrative to be backfilled after
    LLM generation). Holdings use ON CONFLICT DO NOTHING — they are immutable
    once written.
    """
    constraints_json = json.dumps({
        "top_n": run.constraints.top_n,
        "max_weight_pct": run.constraints.max_weight_pct,
        "max_sector_pct": run.constraints.max_sector_pct,
        "min_cis_score": run.constraints.min_cis_score,
        "min_liquidity_usd": run.constraints.min_liquidity_usd,
    })

    await conn.execute(
        """INSERT INTO pim_portfolio_runs (
               run_id, tenant_id, n_candidates, n_holdings, avg_cis_score,
               total_cis_score, regime_at_run, constraints_json,
               narrative, narrative_top_picks, narrative_risk_note, narrative_regime_context
           ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9, $10, $11, $12)
           ON CONFLICT (tenant_id, run_id) DO UPDATE SET
               narrative = EXCLUDED.narrative,
               narrative_top_picks = EXCLUDED.narrative_top_picks,
               narrative_risk_note = EXCLUDED.narrative_risk_note,
               narrative_regime_context = EXCLUDED.narrative_regime_context,
               updated_at = now()""",
        run.run_id,
        run.tenant_id,
        run.n_candidates,
        run.n_holdings,
        run.avg_cis_score,
        run.total_cis_score,
        run.regime_at_run,
        constraints_json,
        run.narrative,
        run.narrative_top_picks,
        run.narrative_risk_note,
        run.narrative_regime_context,
    )

    for holding in run.holdings:
        await conn.execute(
            """INSERT INTO pim_portfolio_holdings (
                   run_id, tenant_id, rank, company_id, ticker, name,
                   cis_score, weight, sector,
                   fundamental_quality, fundamental_momentum, idiosyncratic_sentiment,
                   sentiment_momentum, sector_positioning
               ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
               ON CONFLICT (tenant_id, run_id, company_id) DO NOTHING""",
            run.run_id,
            run.tenant_id,
            holding.rank,
            holding.company_id,
            holding.ticker,
            holding.name,
            holding.cis_score,
            holding.weight,
            holding.sector,
            holding.fundamental_quality,
            holding.fundamental_momentum,
            holding.idiosyncratic_sentiment,
            holding.sentiment_momentum,
            holding.sector_positioning,
        )

    logger.info(
        "portfolio_run_persisted",
        run_id=run.run_id,
        tenant_id=run.tenant_id,
        n_holdings=run.n_holdings,
    )


# ---------------------------------------------------------------------------
# LLM narrative (PIM-4.5)
# ---------------------------------------------------------------------------


async def generate_narrative(run: PortfolioRun, llm_router: Any) -> PortfolioRun:
    """Generate LLM portfolio narrative using pim_portfolio_narrative task label.

    PIM-4.5: temperature=0.2 (FR-3.6 — narrative with high fidelity to data).
    Updates run.narrative, narrative_top_picks, narrative_risk_note, and
    narrative_regime_context in-place. Returns the updated run.

    On LLM failure: logs a warning and sets run.narrative to an error message.
    Never raises — LLM failure is non-fatal for portfolio construction.
    """
    if not run.holdings:
        run.narrative = (
            "No holdings selected — all candidates were filtered by portfolio constraints."
        )
        return run

    top_holdings_text = "\n".join(
        f"  {h.rank}. {h.name or h.company_id} ({h.ticker or 'N/A'}): "
        f"CIS={h.cis_score:.1f}, weight={h.weight * 100:.1f}%, sector={h.sector or 'N/A'}"
        for h in run.holdings[:5]
    )

    sector_breakdown: dict[str, float] = {}
    for h in run.holdings:
        sector = h.sector or "Unknown"
        sector_breakdown[sector] = sector_breakdown.get(sector, 0.0) + h.weight

    sector_text = ", ".join(
        f"{s}: {w * 100:.1f}%"
        for s, w in sorted(sector_breakdown.items(), key=lambda x: -x[1])
    )

    portfolio_summary = (
        f"Portfolio Run Summary:\n"
        f"Holdings: {run.n_holdings} selected from {run.n_candidates} candidates\n"
        f"Weighted-Average CIS: {run.avg_cis_score:.1f}/100\n"
        f"Economic Regime at Run: {run.regime_at_run or 'unknown'}\n"
        f"Constraints: top-{run.constraints.top_n}, "
        f"max {run.constraints.max_weight_pct * 100:.0f}% per position, "
        f"max {run.constraints.max_sector_pct * 100:.0f}% per sector\n\n"
        f"Top Holdings (by rank):\n{top_holdings_text}\n\n"
        f"Sector Allocation:\n{sector_text}\n"
    )

    try:
        response = await llm_router.complete_with_routing(
            run.tenant_id,
            [
                {"role": "system", "content": _PORTFOLIO_NARRATIVE_SYSTEM},
                {"role": "user", "content": portfolio_summary},
            ],
            _PORTFOLIO_NARRATIVE_SCHEMA,
            "pim_portfolio_narrative",
            max_tokens=1024,
            temperature=0.2,
        )
        content = response.content or {}
        if not isinstance(content, dict):
            logger.warning(
                "pim_portfolio_narrative_not_dict",
                content_type=type(content).__name__,
                run_id=run.run_id,
            )
            content = {}
        run.narrative = content.get("summary", "")
        run.narrative_top_picks = content.get("top_picks", "")
        run.narrative_risk_note = content.get("risk_note", "")
        run.narrative_regime_context = content.get("regime_context", "")
    except LLMError as e:
        logger.warning(
            "portfolio_narrative_llm_failed",
            run_id=run.run_id,
            tenant_id=run.tenant_id,
            error=str(e),
        )
        run.narrative = f"Narrative unavailable: {e.message}"

    return run
