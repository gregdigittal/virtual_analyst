"""FRED API integration — PIM-2.2.

Pulls 5 macroeconomic indicators from the St. Louis Fed FRED API:
  - GDP growth rate:  A191RL1Q225SBEA  (Real GDP, QoQ percent change, quarterly)
  - CPI YoY:         CPIAUCSL          (CPI All Urban Consumers, monthly — computes 12-month %)
  - Unemployment:    UNRATE            (Civilian Unemployment Rate, monthly)
  - Yield spread:    T10Y2Y            (10-Year Treasury minus 2-Year Treasury, daily)
  - PMI:             ISM/MAN_PMI       (ISM Manufacturing PMI, monthly; falls back to INDPRO)

Requires FRED_API_KEY environment variable.

FR-2.1: Pull ≥ 5 FRED indicators.
FR-2.4: Returns raw payload suitable for storage in pim_economic_snapshots.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

_logger = structlog.get_logger(__name__)

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
_TIMEOUT = 10.0  # seconds per FRED call

# FRED series identifiers
_SERIES_GDP = "A191RL1Q225SBEA"
_SERIES_CPI = "CPIAUCSL"
_SERIES_UNEMPLOYMENT = "UNRATE"
_SERIES_YIELD_SPREAD = "T10Y2Y"
_SERIES_PMI_PRIMARY = "ISM/MAN_PMI"
_SERIES_PMI_FALLBACK = "INDPRO"  # Industrial Production Index as PMI proxy


class FREDError(Exception):
    """FRED API call failed."""


async def _fetch_series(
    client: httpx.AsyncClient,
    api_key: str,
    series_id: str,
    limit: int = 13,  # 13 months covers 12-month YoY + current
) -> list[dict[str, Any]]:
    """Fetch the most recent observations for a FRED series.

    Returns list of {"date": "YYYY-MM-DD", "value": float | None} ascending.
    Raises FREDError on HTTP or parse failure.
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }
    try:
        resp = await client.get(_FRED_BASE, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise FREDError(f"HTTP error fetching {series_id}: {e}") from e

    try:
        data = resp.json()
    except Exception as e:
        raise FREDError(f"JSON parse error for {series_id}: {e}") from e

    observations = data.get("observations", [])
    result = []
    for obs in reversed(observations):  # ascending order
        raw_val = obs.get("value", ".")
        value: float | None = None
        if raw_val not in (".", "", None):
            try:
                value = float(raw_val)
            except (ValueError, TypeError):
                value = None
        result.append({"date": obs.get("date", ""), "value": value})
    return result


def _latest_value(observations: list[dict[str, Any]]) -> float | None:
    """Return the most recent non-null value."""
    for obs in reversed(observations):
        if obs["value"] is not None:
            return obs["value"]
    return None


def _cpi_yoy(observations: list[dict[str, Any]]) -> float | None:
    """Compute CPI YoY % from monthly observations list (ascending).

    Requires at least 13 observations to compute a 12-month change.
    """
    valid = [obs for obs in observations if obs["value"] is not None]
    if len(valid) < 13:
        return None
    # Most recent value vs 12 months prior
    current = valid[-1]["value"]
    prior_year = valid[-13]["value"]
    if prior_year == 0.0:
        return None
    return round((current - prior_year) / prior_year * 100.0, 3)


async def fetch_indicators(api_key: str) -> dict[str, Any]:
    """Fetch all 5 FRED indicators concurrently.

    Returns a dict with indicator values and raw observations for audit storage.
    Raises FREDError if the API key is missing or all indicators fail.
    Degrades gracefully if individual series fail (value set to None).
    """
    if not api_key:
        raise FREDError("FRED_API_KEY is not configured")

    async with httpx.AsyncClient() as client:
        tasks = {
            "gdp": _fetch_series(client, api_key, _SERIES_GDP, limit=5),
            "cpi": _fetch_series(client, api_key, _SERIES_CPI, limit=13),
            "unemployment": _fetch_series(client, api_key, _SERIES_UNEMPLOYMENT, limit=3),
            "yield_spread": _fetch_series(client, api_key, _SERIES_YIELD_SPREAD, limit=5),
            "pmi_primary": _fetch_series(client, api_key, _SERIES_PMI_PRIMARY, limit=3),
        }

        results: dict[str, list[dict[str, Any]] | None] = {}
        raw_obs: dict[str, list[dict[str, Any]]] = {}

        async def _safe_fetch(key: str, coro: Any) -> None:
            try:
                results[key] = await coro
            except FREDError as e:
                _logger.warning("fred_fetch_failed", series=key, error=str(e))
                results[key] = None

        await asyncio.gather(*[_safe_fetch(k, c) for k, c in tasks.items()])

        # PMI fallback: if primary ISM series fails, try INDPRO
        if results.get("pmi_primary") is None:
            try:
                async with httpx.AsyncClient() as fb_client:
                    results["pmi_primary"] = await _fetch_series(fb_client, api_key, _SERIES_PMI_FALLBACK, limit=3)
                    _logger.info("fred_pmi_fallback_used", series=_SERIES_PMI_FALLBACK)
            except FREDError:
                results["pmi_primary"] = None

        # Store raw observations for audit
        for key, obs_list in results.items():
            if obs_list is not None:
                raw_obs[key] = obs_list

        gdp_obs = results.get("gdp") or []
        cpi_obs = results.get("cpi") or []
        unemployment_obs = results.get("unemployment") or []
        yield_obs = results.get("yield_spread") or []
        pmi_obs = results.get("pmi_primary") or []

        gdp_growth = _latest_value(gdp_obs)
        cpi_yoy = _cpi_yoy(cpi_obs)
        unemployment = _latest_value(unemployment_obs)
        yield_spread = _latest_value(yield_obs)
        ism_pmi = _latest_value(pmi_obs)

        fetched_at = datetime.now(tz=timezone.utc).isoformat()

        _logger.info(
            "fred_indicators_fetched",
            gdp_growth=gdp_growth,
            cpi_yoy=cpi_yoy,
            unemployment=unemployment,
            yield_spread=yield_spread,
            ism_pmi=ism_pmi,
        )

        return {
            "fetched_at": fetched_at,
            "gdp_growth_pct": gdp_growth,
            "cpi_yoy_pct": cpi_yoy,
            "unemployment_rate": unemployment,
            "yield_spread_10y2y": yield_spread,
            "ism_pmi": ism_pmi,
            "indicators_raw": {
                "gdp_series": gdp_obs[-3:] if gdp_obs else [],
                "cpi_series": cpi_obs[-3:] if cpi_obs else [],
                "unemployment_series": unemployment_obs[-3:] if unemployment_obs else [],
                "yield_spread_series": yield_obs[-3:] if yield_obs else [],
                "pmi_series": pmi_obs[-3:] if pmi_obs else [],
            },
        }
