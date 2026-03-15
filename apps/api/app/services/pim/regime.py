"""Economic regime classifier — PIM-2.3.

Statistical (not LLM) classification of macroeconomic regime as:
  - expansion:   majority of indicators point to healthy growth
  - contraction: majority of indicators signal economic weakness
  - transition:  signals are mixed or insufficient

Classification is threshold-based, rule-derived from NBER/Fed research:
  - GDP growth >  2% annualised → expansion signal
  - GDP growth <  0%            → contraction signal
  - Unemployment < 5%           → expansion signal
  - Unemployment > 6.5%         → contraction signal
  - Yield spread > 0%           → expansion signal (normal curve)
  - Yield spread < -0.3%        → contraction signal (inverted)
  - ISM PMI      > 50           → expansion signal
  - ISM PMI      < 45           → contraction signal
  - CPI YoY  1–4%               → expansion signal (controlled inflation)
  - CPI YoY  > 6% or < 0%       → contraction signal (overheating / deflation)

Confidence = (agreeing_indicators / indicators_with_data).
Regime = majority vote; ties resolve to 'transition'.

FR-2.2: Classify economic regime: expansion / contraction / transition.
SR-1 (ISA 520): statistical basis, no fabrication; thresholds documented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RegimeResult:
    regime: str  # 'expansion' | 'contraction' | 'transition'
    regime_confidence: float  # [0.0, 1.0]
    indicators_agreeing: int
    indicators_total: int
    signal_breakdown: dict[str, str]  # indicator → 'expansion' | 'contraction' | 'neutral' | 'missing'


def _gdp_signal(value: float | None) -> str:
    if value is None:
        return "missing"
    if value > 2.0:
        return "expansion"
    if value < 0.0:
        return "contraction"
    return "neutral"


def _unemployment_signal(value: float | None) -> str:
    if value is None:
        return "missing"
    if value < 5.0:
        return "expansion"
    if value > 6.5:
        return "contraction"
    return "neutral"


def _yield_spread_signal(value: float | None) -> str:
    if value is None:
        return "missing"
    if value > 0.0:
        return "expansion"
    if value < -0.3:
        return "contraction"
    return "neutral"


def _pmi_signal(value: float | None) -> str:
    if value is None:
        return "missing"
    if value > 50.0:
        return "expansion"
    if value < 45.0:
        return "contraction"
    return "neutral"


def _cpi_signal(value: float | None) -> str:
    if value is None:
        return "missing"
    if 1.0 <= value <= 4.0:
        return "expansion"
    if value > 6.0 or value < 0.0:
        return "contraction"
    return "neutral"


def classify_regime(indicators: dict[str, Any]) -> RegimeResult:
    """Classify economic regime from FRED indicator values.

    Args:
        indicators: dict with keys gdp_growth_pct, cpi_yoy_pct,
            unemployment_rate, yield_spread_10y2y, ism_pmi — all float | None.

    Returns RegimeResult with regime, confidence, and signal breakdown.
    """
    signals = {
        "gdp": _gdp_signal(indicators.get("gdp_growth_pct")),
        "unemployment": _unemployment_signal(indicators.get("unemployment_rate")),
        "yield_spread": _yield_spread_signal(indicators.get("yield_spread_10y2y")),
        "pmi": _pmi_signal(indicators.get("ism_pmi")),
        "cpi": _cpi_signal(indicators.get("cpi_yoy_pct")),
    }

    expansion_count = sum(1 for v in signals.values() if v == "expansion")
    contraction_count = sum(1 for v in signals.values() if v == "contraction")
    available_count = sum(1 for v in signals.values() if v != "missing")

    if available_count == 0:
        return RegimeResult(
            regime="transition",
            regime_confidence=0.0,
            indicators_agreeing=0,
            indicators_total=0,
            signal_breakdown=signals,
        )

    if expansion_count > contraction_count and expansion_count > available_count / 2:
        regime = "expansion"
        agreeing = expansion_count
    elif contraction_count > expansion_count and contraction_count > available_count / 2:
        regime = "contraction"
        agreeing = contraction_count
    else:
        regime = "transition"
        agreeing = max(expansion_count, contraction_count)

    confidence = round(agreeing / available_count, 3)

    return RegimeResult(
        regime=regime,
        regime_confidence=confidence,
        indicators_agreeing=agreeing,
        indicators_total=available_count,
        signal_breakdown=signals,
    )
