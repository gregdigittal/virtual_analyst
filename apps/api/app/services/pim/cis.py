"""Composite Investment Score (CIS) computation — PIM-2.6 + PIM-2.7.

CIS is a weighted sum of 5 sub-scores, each normalised to [0, 100]:

  Factor                  Default Weight  Description
  ─────────────────────── ──────────────  ─────────────────────────────────
  Fundamental Quality     35%             DCF/financial ratio quality score
  Fundamental Momentum    20%             Quarter-over-quarter improvement
  Idiosyncratic Sentiment 25%             Company-specific sentiment (PIM-1.3)
  Sentiment Momentum      10%             Sentiment trend direction
  Sector Positioning      10%             Sector regime alignment score

FR-3.1: CIS = weighted sum of 5 sub-scores (configurable weights, default above).
FR-3.2: Default weights as above.
SR-1 (ISA 520): All sub-scores derived from observable data; no fabrication.
SR-6 (SR-6 limitations): Scores are model estimates, not investment advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CISWeights:
    """Configurable CIS factor weights. Must sum to 1.0."""

    fundamental_quality: float = 0.35
    fundamental_momentum: float = 0.20
    idiosyncratic_sentiment: float = 0.25
    sentiment_momentum: float = 0.10
    sector_positioning: float = 0.10

    def validate(self) -> None:
        total = sum([
            self.fundamental_quality,
            self.fundamental_momentum,
            self.idiosyncratic_sentiment,
            self.sentiment_momentum,
            self.sector_positioning,
        ])
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"CIS weights must sum to 1.0; got {total:.6f}")


@dataclass
class CISFactorScores:
    """Normalised [0, 100] factor scores for one company."""

    company_id: str
    fundamental_quality: float | None  # [0, 100] from DCF/ratio analysis
    fundamental_momentum: float | None  # [0, 100] from QoQ metric change
    idiosyncratic_sentiment: float | None  # [0, 100] from sentiment aggregates
    sentiment_momentum: float | None  # [0, 100] from trend direction
    sector_positioning: float | None  # [0, 100] from sector vs regime alignment
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CISResult:
    """CIS output for one company."""

    company_id: str
    cis_score: float  # [0, 100] final weighted composite
    factor_scores: CISFactorScores
    weights_used: CISWeights
    factors_available: int  # count of non-null sub-scores
    factors_total: int = 5
    limitations: str = (
        "CIS is a model-based estimate derived from historical data and AI-generated signals. "
        "It does not constitute investment advice. Past performance does not predict future results."
    )


def _clamp(value: float | None, lo: float = 0.0, hi: float = 100.0) -> float | None:
    """Clamp to [lo, hi]; return None if input is None."""
    if value is None:
        return None
    return max(lo, min(hi, value))


def _sentiment_to_score(avg_sentiment: float | None) -> float | None:
    """Map sentiment [-1, +1] to CIS sub-score [0, 100]. Linear mapping."""
    if avg_sentiment is None:
        return None
    return round((avg_sentiment + 1.0) / 2.0 * 100.0, 2)


def _trend_to_momentum_score(trend_direction: str | None) -> float | None:
    """Map sentiment trend direction to momentum sub-score [0, 100]."""
    mapping = {
        "improving": 75.0,
        "stable": 50.0,
        "declining": 25.0,
    }
    return mapping.get(trend_direction or "", None)


def _sector_regime_alignment(
    sector: str | None,
    regime: str | None,
    sector_regime_weights: dict[str, dict[str, float]] | None = None,
) -> float | None:
    """Return sector positioning score [0, 100] for a sector in the current regime.

    Default scoring table reflects sector cyclicality:
    - expansion: cyclicals (tech, consumer discretionary, industrials) score high
    - contraction: defensives (utilities, healthcare, consumer staples) score high
    - transition: all sectors regress to 50 (neutral)
    """
    if sector is None or regime is None:
        return None
    if sector_regime_weights:
        sector_map = sector_regime_weights.get(sector, {})
        return sector_map.get(regime, 50.0)
    # Default heuristic scoring table
    _DEFAULT_TABLE: dict[str, dict[str, float]] = {
        "technology":             {"expansion": 80, "contraction": 35, "transition": 50},
        "consumer_discretionary": {"expansion": 75, "contraction": 30, "transition": 50},
        "industrials":            {"expansion": 70, "contraction": 35, "transition": 50},
        "financials":             {"expansion": 65, "contraction": 40, "transition": 50},
        "communication":          {"expansion": 65, "contraction": 45, "transition": 50},
        "materials":              {"expansion": 60, "contraction": 40, "transition": 50},
        "energy":                 {"expansion": 55, "contraction": 50, "transition": 50},
        "real_estate":            {"expansion": 55, "contraction": 45, "transition": 50},
        "consumer_staples":       {"expansion": 40, "contraction": 70, "transition": 55},
        "healthcare":             {"expansion": 45, "contraction": 75, "transition": 60},
        "utilities":              {"expansion": 35, "contraction": 80, "transition": 60},
    }
    row = _DEFAULT_TABLE.get(sector.lower().replace(" ", "_"), {})
    return float(row.get(regime, 50.0))


def compute_factor_scores(
    company_id: str,
    *,
    # Fundamental quality: derived from DCF/financial ratio analysis
    dcf_upside_pct: float | None = None,  # (fair_value - market_price) / market_price * 100
    roe: float | None = None,             # Return on equity % (normalised to [0,100] via clamp)
    debt_to_equity: float | None = None,  # lower is better
    # Fundamental momentum: QoQ improvement
    revenue_growth_qoq: float | None = None,  # QoQ revenue growth %
    ebitda_margin_change: float | None = None,  # QoQ EBITDA margin change pp
    # Sentiment: from pim_sentiment_aggregates (monthly)
    avg_sentiment_score: float | None = None,  # [-1, +1]
    trend_direction: str | None = None,         # 'improving' | 'stable' | 'declining'
    # Sector / regime
    sector: str | None = None,
    current_regime: str | None = None,
    sector_regime_weights: dict[str, dict[str, float]] | None = None,
) -> CISFactorScores:
    """Compute normalised [0, 100] sub-scores for each CIS factor.

    Inputs are raw financial/sentiment signals; outputs are normalised scores.
    Missing inputs produce None sub-scores (excluded from weighted average).
    """
    # --- Factor 1: Fundamental Quality [0, 100] ---
    quality_components = []
    if dcf_upside_pct is not None:
        # Map DCF upside: -50% → 0, 0% → 50, +50% → 100 (clamped)
        q_dcf = _clamp((dcf_upside_pct + 50.0) / 100.0 * 100.0)
        quality_components.append(q_dcf)
    if roe is not None:
        # ROE: 0% → 0, 20% → 100 (capped)
        q_roe = _clamp(roe / 20.0 * 100.0)
        quality_components.append(q_roe)
    if debt_to_equity is not None:
        # D/E: 0 → 100, 2 → 0 (inverse linear)
        q_de = _clamp((1.0 - min(debt_to_equity / 2.0, 1.0)) * 100.0)
        quality_components.append(q_de)
    fundamental_quality = (
        round(sum(quality_components) / len(quality_components), 2)
        if quality_components
        else None
    )

    # --- Factor 2: Fundamental Momentum [0, 100] ---
    momentum_components = []
    if revenue_growth_qoq is not None:
        # Rev growth: -20% → 0, 0% → 50, +20% → 100
        m_rev = _clamp((revenue_growth_qoq + 20.0) / 40.0 * 100.0)
        momentum_components.append(m_rev)
    if ebitda_margin_change is not None:
        # EBITDA margin change: -10pp → 0, 0pp → 50, +10pp → 100
        m_ebitda = _clamp((ebitda_margin_change + 10.0) / 20.0 * 100.0)
        momentum_components.append(m_ebitda)
    fundamental_momentum = (
        round(sum(momentum_components) / len(momentum_components), 2)
        if momentum_components
        else None
    )

    # --- Factor 3: Idiosyncratic Sentiment [0, 100] ---
    idiosyncratic_sentiment = _sentiment_to_score(avg_sentiment_score)
    if idiosyncratic_sentiment is not None:
        idiosyncratic_sentiment = round(idiosyncratic_sentiment, 2)

    # --- Factor 4: Sentiment Momentum [0, 100] ---
    sentiment_momentum = _trend_to_momentum_score(trend_direction)

    # --- Factor 5: Sector Positioning [0, 100] ---
    sector_positioning = _sector_regime_alignment(sector, current_regime, sector_regime_weights)

    return CISFactorScores(
        company_id=company_id,
        fundamental_quality=fundamental_quality,
        fundamental_momentum=fundamental_momentum,
        idiosyncratic_sentiment=idiosyncratic_sentiment,
        sentiment_momentum=sentiment_momentum,
        sector_positioning=sector_positioning,
    )


def compute_cis(
    factor_scores: CISFactorScores,
    weights: CISWeights | None = None,
) -> CISResult:
    """Compute final CIS score from factor sub-scores.

    Uses weighted average over available (non-None) factors.
    Weights are renormalised if some factors are missing (SR-1: no fabrication).
    """
    w = weights or CISWeights()
    w.validate()

    factor_weight_pairs: list[tuple[float | None, float]] = [
        (factor_scores.fundamental_quality, w.fundamental_quality),
        (factor_scores.fundamental_momentum, w.fundamental_momentum),
        (factor_scores.idiosyncratic_sentiment, w.idiosyncratic_sentiment),
        (factor_scores.sentiment_momentum, w.sentiment_momentum),
        (factor_scores.sector_positioning, w.sector_positioning),
    ]

    available = [(score, weight) for score, weight in factor_weight_pairs if score is not None]
    factors_available = len(available)

    if not available:
        return CISResult(
            company_id=factor_scores.company_id,
            cis_score=50.0,  # neutral fallback when no data
            factor_scores=factor_scores,
            weights_used=w,
            factors_available=0,
        )

    # Renormalise weights over available factors
    total_available_weight = sum(weight for _, weight in available)
    cis_score = sum(score * (weight / total_available_weight) for score, weight in available)
    cis_score = round(max(0.0, min(100.0, cis_score)), 2)

    return CISResult(
        company_id=factor_scores.company_id,
        cis_score=cis_score,
        factor_scores=factor_scores,
        weights_used=w,
        factors_available=factors_available,
    )
