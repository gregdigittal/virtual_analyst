"""EDGAR / Yahoo Finance fundamental data ingestion — PIM-3.6.

Two ingestion paths:
  1. EDGAR (SEC EDGAR Company Facts API) — annual/quarterly financials from 10-K/10-Q
  2. Yahoo Finance (yfinance library) — price, market cap, analyst estimates

SR-1: All data sourced from public APIs — no fabrication.
SR-6: Limitations disclaimer included in all returned payloads.

Rate limiting:
  - EDGAR: 10 req/s user-agent-identified per SEC guidelines.
  - yfinance: no official limit; back off on errors.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

_EDGAR_BASE = "https://data.sec.gov/api/xbrl/companyfacts"
_EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"

# SEC requires a User-Agent header identifying the application and contact email
_EDGAR_HEADERS = {
    "User-Agent": "VirtualAnalyst/1.0 platform@virtual-analyst.ai",
    "Accept-Encoding": "gzip, deflate",
}

# yfinance is optional — graceful degradation when not installed
try:
    import yfinance as _yf  # type: ignore[import]

    _YFINANCE_AVAILABLE = True
except ImportError:  # pragma: no cover
    _yf = None  # type: ignore[assignment]
    _YFINANCE_AVAILABLE = False


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class FundamentalsSnapshot:
    """Fundamental financial data for one company at one point in time.  (PIM-3.6)"""

    company_id: str
    ticker: str
    cik: str | None            # SEC CIK (10-digit padded)
    period_end: str            # ISO date — fiscal period end
    period_type: str           # "annual" | "quarterly"

    # Income statement
    revenue: float | None = None              # USD
    gross_profit: float | None = None         # USD
    ebitda: float | None = None               # USD (derived or reported)
    net_income: float | None = None           # USD
    eps_diluted: float | None = None

    # Balance sheet
    total_assets: float | None = None         # USD
    total_liabilities: float | None = None    # USD
    total_equity: float | None = None         # USD
    cash_and_equivalents: float | None = None # USD
    total_debt: float | None = None           # USD

    # Derived ratios
    roe: float | None = None                  # net_income / equity %
    debt_to_equity: float | None = None       # total_debt / equity
    gross_margin_pct: float | None = None
    net_margin_pct: float | None = None

    # Market data (Yahoo)
    market_cap: float | None = None           # USD
    price: float | None = None                # current price USD
    pe_ratio: float | None = None
    ev_ebitda: float | None = None

    # QoQ / YoY momentum
    revenue_growth_qoq: float | None = None   # % change vs prior quarter
    ebitda_margin_change: float | None = None # pp change vs prior quarter

    # Data quality
    source: str = "unknown"                   # "edgar" | "yahoo" | "edgar+yahoo"
    limitations: str = (
        "Fundamental data sourced from public APIs (EDGAR/Yahoo Finance). "
        "Values are as-reported and may differ from adjusted figures. "
        "Not investment advice (SR-6)."
    )
    raw: dict[str, Any] = field(default_factory=dict)


class FundamentalsError(Exception):
    """Raised when fundamental data cannot be fetched."""


# ---------------------------------------------------------------------------
# EDGAR ingestion
# ---------------------------------------------------------------------------


async def _edgar_company_facts(cik_padded: str) -> dict[str, Any]:
    """Fetch EDGAR company facts for one CIK.

    Returns the raw SEC XBRL facts dict.  Raises FundamentalsError on failure.
    """
    url = f"{_EDGAR_BASE}/CIK{cik_padded}.json"
    async with httpx.AsyncClient(timeout=30.0, headers=_EDGAR_HEADERS) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()  # type: ignore[no-any-return]
        except httpx.HTTPStatusError as e:
            raise FundamentalsError(
                f"EDGAR HTTP {e.response.status_code} for CIK {cik_padded}"
            ) from e
        except httpx.RequestError as e:
            raise FundamentalsError(f"EDGAR request error: {e}") from e


def _extract_latest_value(
    facts: dict[str, Any],
    namespace: str,   # "us-gaap" | "dei"
    concept: str,     # e.g. "Revenues"
    form_filter: str | None = None,  # e.g. "10-K" or "10-Q"
) -> tuple[float | None, str | None]:
    """Extract the most recent reported value for a US-GAAP concept.

    Returns (value_usd, period_end_iso) or (None, None) if not found.
    """
    try:
        units = facts["facts"][namespace][concept]["units"]
        usd_series: list[dict[str, Any]] = units.get("USD", [])
        if not usd_series:
            return None, None
        # Filter to target form if specified; fall back to any form
        candidates = [r for r in usd_series if not form_filter or r.get("form") == form_filter]
        if not candidates:
            candidates = usd_series
        # Sort by filed date descending, pick most recent non-zero
        candidates.sort(key=lambda r: r.get("filed", ""), reverse=True)
        for rec in candidates:
            val = rec.get("val")
            if val is not None and val != 0:
                return float(val), rec.get("end")
    except (KeyError, TypeError):
        pass
    return None, None


async def fetch_edgar_fundamentals(
    company_id: str,
    ticker: str,
    cik: str,
    period_type: str = "annual",
) -> FundamentalsSnapshot:
    """Fetch fundamental financials from EDGAR for a given company.

    PIM-3.6 — EDGAR ingestion path.
    Pulls revenue, net income, total assets, equity, debt from US-GAAP XBRL facts.
    """
    cik_padded = cik.lstrip("0").zfill(10)
    facts = await _edgar_company_facts(cik_padded)

    form = "10-K" if period_type == "annual" else "10-Q"

    # Revenue — try multiple GAAP concepts in order of preference
    revenue, period_end = _extract_latest_value(facts, "us-gaap", "Revenues", form)
    if revenue is None:
        revenue, period_end = _extract_latest_value(facts, "us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax", form)
    if revenue is None:
        revenue, period_end = _extract_latest_value(facts, "us-gaap", "SalesRevenueNet", form)

    net_income, _ = _extract_latest_value(facts, "us-gaap", "NetIncomeLoss", form)
    total_assets, _ = _extract_latest_value(facts, "us-gaap", "Assets", form)
    total_equity, _ = _extract_latest_value(facts, "us-gaap", "StockholdersEquity", form)
    total_liabilities, _ = _extract_latest_value(facts, "us-gaap", "Liabilities", form)
    cash, _ = _extract_latest_value(facts, "us-gaap", "CashAndCashEquivalentsAtCarryingValue", form)
    long_term_debt, _ = _extract_latest_value(facts, "us-gaap", "LongTermDebt", form)
    gross_profit, _ = _extract_latest_value(facts, "us-gaap", "GrossProfit", form)
    eps_diluted, _ = _extract_latest_value(facts, "us-gaap", "EarningsPerShareDiluted", form)

    # Derived ratios — guard all divisions
    roe: float | None = None
    if net_income is not None and total_equity and total_equity != 0:
        roe = round(net_income / total_equity * 100.0, 2)

    debt_to_equity: float | None = None
    if long_term_debt is not None and total_equity and total_equity != 0:
        debt_to_equity = round(long_term_debt / total_equity, 4)

    gross_margin: float | None = None
    if gross_profit is not None and revenue and revenue != 0:
        gross_margin = round(gross_profit / revenue * 100.0, 2)

    net_margin: float | None = None
    if net_income is not None and revenue and revenue != 0:
        net_margin = round(net_income / revenue * 100.0, 2)

    return FundamentalsSnapshot(
        company_id=company_id,
        ticker=ticker,
        cik=cik_padded,
        period_end=period_end or "",
        period_type=period_type,
        revenue=revenue,
        gross_profit=gross_profit,
        net_income=net_income,
        eps_diluted=eps_diluted,
        total_assets=total_assets,
        total_liabilities=total_liabilities,
        total_equity=total_equity,
        cash_and_equivalents=cash,
        total_debt=long_term_debt,
        roe=roe,
        debt_to_equity=debt_to_equity,
        gross_margin_pct=gross_margin,
        net_margin_pct=net_margin,
        source="edgar",
        raw={"cik": cik_padded, "facts_keys": list(facts.get("facts", {}).get("us-gaap", {}).keys())[:20]},
    )


# ---------------------------------------------------------------------------
# Yahoo Finance ingestion
# ---------------------------------------------------------------------------


def _fetch_yahoo_sync(ticker: str) -> dict[str, Any]:
    """Fetch Yahoo Finance data synchronously (yfinance is not async).

    Returns dict with price, market_cap, pe_ratio, ev_ebitda.
    """
    if not _YFINANCE_AVAILABLE or _yf is None:
        raise FundamentalsError("yfinance not installed — cannot fetch Yahoo data")
    try:
        info = _yf.Ticker(ticker).info
        return {
            "price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "market_cap": info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ebitda": info.get("ebitda"),
            "total_debt": info.get("totalDebt"),
            "revenue": info.get("totalRevenue"),
        }
    except Exception as e:  # noqa: BLE001 — yfinance raises various errors
        raise FundamentalsError(f"Yahoo Finance error for {ticker}: {e}") from e


async def fetch_yahoo_fundamentals(
    company_id: str,
    ticker: str,
    cik: str | None = None,
) -> FundamentalsSnapshot:
    """Fetch market and fundamental data from Yahoo Finance.  (PIM-3.6)

    Runs synchronous yfinance call in executor to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(None, _fetch_yahoo_sync, ticker)

    revenue = data.get("revenue")
    ebitda = data.get("ebitda")
    total_debt = data.get("total_debt")

    return FundamentalsSnapshot(
        company_id=company_id,
        ticker=ticker,
        cik=cik,
        period_end="",   # Yahoo doesn't give a specific period end for TTM data
        period_type="ttm",
        revenue=float(revenue) if revenue else None,
        ebitda=float(ebitda) if ebitda else None,
        total_debt=float(total_debt) if total_debt else None,
        market_cap=float(data["market_cap"]) if data.get("market_cap") else None,
        price=float(data["price"]) if data.get("price") else None,
        pe_ratio=float(data["pe_ratio"]) if data.get("pe_ratio") else None,
        ev_ebitda=float(data["ev_ebitda"]) if data.get("ev_ebitda") else None,
        source="yahoo",
        raw=data,
    )


# ---------------------------------------------------------------------------
# Combined ingestion (EDGAR + Yahoo merged)
# ---------------------------------------------------------------------------


async def fetch_fundamentals(
    company_id: str,
    ticker: str,
    cik: str | None = None,
    period_type: str = "annual",
    prefer_edgar: bool = True,
) -> FundamentalsSnapshot:
    """Fetch fundamentals from best available source, merging where possible.  (PIM-3.6)

    Strategy:
    - If CIK provided and prefer_edgar=True: fetch EDGAR first, merge Yahoo market data.
    - If CIK not provided: Yahoo only.
    - On EDGAR failure: fall back to Yahoo.
    - On Yahoo failure: return EDGAR only.
    """
    edgar_result: FundamentalsSnapshot | None = None
    yahoo_result: FundamentalsSnapshot | None = None

    # Fetch in parallel when both are possible
    tasks: list[Any] = []
    if cik and prefer_edgar:
        tasks.append(fetch_edgar_fundamentals(company_id, ticker, cik, period_type))
    if _YFINANCE_AVAILABLE:
        tasks.append(fetch_yahoo_fundamentals(company_id, ticker, cik))

    if not tasks:
        raise FundamentalsError(f"No data source available for {ticker} (no CIK and yfinance not installed)")

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for res in results:
        if isinstance(res, FundamentalsSnapshot):
            if res.source == "edgar":
                edgar_result = res
            elif res.source in ("yahoo", "ttm"):
                yahoo_result = res
        elif isinstance(res, Exception):
            logger.warning("fundamentals_fetch_error", ticker=ticker, error=str(res))

    if edgar_result is None and yahoo_result is None:
        raise FundamentalsError(f"All data sources failed for {ticker}")

    if edgar_result is None:
        return yahoo_result  # type: ignore[return-value]

    if yahoo_result is None:
        return edgar_result

    # Merge: EDGAR for historical financials, Yahoo for market data
    edgar_result.market_cap = yahoo_result.market_cap
    edgar_result.price = yahoo_result.price
    edgar_result.pe_ratio = yahoo_result.pe_ratio
    edgar_result.ev_ebitda = yahoo_result.ev_ebitda
    # Prefer Yahoo EBITDA if EDGAR didn't have it
    if edgar_result.ebitda is None:
        edgar_result.ebitda = yahoo_result.ebitda
    # Prefer Yahoo debt if EDGAR didn't have it
    if edgar_result.total_debt is None:
        edgar_result.total_debt = yahoo_result.total_debt
    edgar_result.source = "edgar+yahoo"
    return edgar_result
