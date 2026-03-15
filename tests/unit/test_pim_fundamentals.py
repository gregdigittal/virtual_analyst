"""Unit tests for PIM fundamental data ingestion — PIM-3.6."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.pim.fundamentals import (
    FundamentalsError,
    FundamentalsSnapshot,
    _extract_latest_value,
    fetch_fundamentals,
    fetch_edgar_fundamentals,
    fetch_yahoo_fundamentals,
)


# ---------------------------------------------------------------------------
# _extract_latest_value helper
# ---------------------------------------------------------------------------


class TestExtractLatestValue:
    def _facts(self, values: list[dict]) -> dict:
        return {"facts": {"us-gaap": {"Revenues": {"units": {"USD": values}}}}}

    def test_returns_none_for_missing_concept(self):
        val, period = _extract_latest_value({}, "us-gaap", "Revenues")
        assert val is None
        assert period is None

    def test_returns_most_recent_nonzero(self):
        facts = self._facts([
            {"val": 1000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"},
            {"val": 900, "end": "2022-12-31", "filed": "2023-02-01", "form": "10-K"},
        ])
        val, period = _extract_latest_value(facts, "us-gaap", "Revenues", "10-K")
        assert val == 1000.0
        assert period == "2023-12-31"

    def test_skips_zero_values(self):
        facts = self._facts([
            {"val": 0, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"},
            {"val": 500, "end": "2022-12-31", "filed": "2023-02-01", "form": "10-K"},
        ])
        val, _ = _extract_latest_value(facts, "us-gaap", "Revenues", "10-K")
        assert val == 500.0

    def test_falls_back_when_form_filter_missing(self):
        facts = self._facts([
            {"val": 800, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-Q"},
        ])
        # Filter for 10-K but only 10-Q exists → falls back to any form
        val, _ = _extract_latest_value(facts, "us-gaap", "Revenues", "10-K")
        assert val == 800.0

    def test_handles_malformed_facts(self):
        val, period = _extract_latest_value({"facts": None}, "us-gaap", "Revenues")
        assert val is None


# ---------------------------------------------------------------------------
# fetch_edgar_fundamentals
# ---------------------------------------------------------------------------


class TestFetchEdgarFundamentals:
    @pytest.fixture
    def mock_facts(self):
        return {
            "facts": {
                "us-gaap": {
                    "Revenues": {"units": {"USD": [{"val": 1_000_000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"}]}},
                    "NetIncomeLoss": {"units": {"USD": [{"val": 100_000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"}]}},
                    "Assets": {"units": {"USD": [{"val": 5_000_000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"}]}},
                    "StockholdersEquity": {"units": {"USD": [{"val": 2_000_000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"}]}},
                    "Liabilities": {"units": {"USD": [{"val": 3_000_000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"}]}},
                    "LongTermDebt": {"units": {"USD": [{"val": 500_000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"}]}},
                    "GrossProfit": {"units": {"USD": [{"val": 400_000, "end": "2023-12-31", "filed": "2024-02-01", "form": "10-K"}]}},
                }
            }
        }

    @pytest.mark.asyncio
    async def test_fetches_revenue_and_net_income(self, mock_facts):
        with patch(
            "apps.api.app.services.pim.fundamentals._edgar_company_facts",
            new_callable=AsyncMock,
            return_value=mock_facts,
        ):
            result = await fetch_edgar_fundamentals("co-1", "TEST", "123456", "annual")

        assert result.revenue == 1_000_000.0
        assert result.net_income == 100_000.0
        assert result.source == "edgar"
        assert result.ticker == "TEST"

    @pytest.mark.asyncio
    async def test_computes_roe(self, mock_facts):
        with patch(
            "apps.api.app.services.pim.fundamentals._edgar_company_facts",
            new_callable=AsyncMock,
            return_value=mock_facts,
        ):
            result = await fetch_edgar_fundamentals("co-1", "TEST", "123456", "annual")

        # ROE = net_income / equity * 100 = 100_000 / 2_000_000 * 100 = 5.0
        assert result.roe == pytest.approx(5.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_computes_gross_margin(self, mock_facts):
        with patch(
            "apps.api.app.services.pim.fundamentals._edgar_company_facts",
            new_callable=AsyncMock,
            return_value=mock_facts,
        ):
            result = await fetch_edgar_fundamentals("co-1", "TEST", "123456", "annual")

        # gross_margin = 400_000 / 1_000_000 * 100 = 40.0
        assert result.gross_margin_pct == pytest.approx(40.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_http_error_raises_fundamentals_error(self):
        import httpx

        with patch(
            "apps.api.app.services.pim.fundamentals._edgar_company_facts",
            new_callable=AsyncMock,
            side_effect=FundamentalsError("EDGAR HTTP 404 for CIK 0000000001"),
        ):
            with pytest.raises(FundamentalsError, match="EDGAR"):
                await fetch_edgar_fundamentals("co-1", "TEST", "1", "annual")


# ---------------------------------------------------------------------------
# fetch_yahoo_fundamentals
# ---------------------------------------------------------------------------


class TestFetchYahooFundamentals:
    @pytest.mark.asyncio
    async def test_fetches_market_data(self):
        mock_info = {
            "currentPrice": 150.0,
            "marketCap": 2_400_000_000_000,
            "trailingPE": 28.5,
            "enterpriseToEbitda": 22.1,
            "ebitda": 120_000_000_000,
            "totalDebt": 90_000_000_000,
            "totalRevenue": 380_000_000_000,
        }
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info

        with patch("apps.api.app.services.pim.fundamentals._YFINANCE_AVAILABLE", True), \
             patch("apps.api.app.services.pim.fundamentals._yf") as mock_yf:
            mock_yf.Ticker.return_value = mock_ticker
            result = await fetch_yahoo_fundamentals("co-aapl", "AAPL")

        assert result.price == 150.0
        assert result.market_cap == 2_400_000_000_000
        assert result.pe_ratio == 28.5
        assert result.source == "yahoo"

    @pytest.mark.asyncio
    async def test_raises_when_yfinance_not_available(self):
        with patch("apps.api.app.services.pim.fundamentals._YFINANCE_AVAILABLE", False):
            with pytest.raises(FundamentalsError, match="yfinance not installed"):
                await fetch_yahoo_fundamentals("co-1", "TEST")


# ---------------------------------------------------------------------------
# fetch_fundamentals (combined)
# ---------------------------------------------------------------------------


class TestFetchFundamentals:
    @pytest.mark.asyncio
    async def test_returns_yahoo_when_no_cik(self):
        mock_snapshot = FundamentalsSnapshot(
            company_id="co-1", ticker="TEST", cik=None,
            period_end="", period_type="ttm",
            price=100.0, source="yahoo",
        )
        with patch("apps.api.app.services.pim.fundamentals._YFINANCE_AVAILABLE", True), \
             patch(
                "apps.api.app.services.pim.fundamentals.fetch_yahoo_fundamentals",
                new_callable=AsyncMock,
                return_value=mock_snapshot,
             ):
            result = await fetch_fundamentals("co-1", "TEST", cik=None)

        assert result.source == "yahoo"

    @pytest.mark.asyncio
    async def test_merges_edgar_and_yahoo(self):
        edgar_snap = FundamentalsSnapshot(
            company_id="co-1", ticker="TEST", cik="0000000001",
            period_end="2023-12-31", period_type="annual",
            revenue=1_000_000.0, source="edgar",
        )
        yahoo_snap = FundamentalsSnapshot(
            company_id="co-1", ticker="TEST", cik=None,
            period_end="", period_type="ttm",
            price=50.0, market_cap=500_000_000.0, source="yahoo",
        )
        with patch("apps.api.app.services.pim.fundamentals._YFINANCE_AVAILABLE", True), \
             patch(
                "apps.api.app.services.pim.fundamentals.fetch_edgar_fundamentals",
                new_callable=AsyncMock,
                return_value=edgar_snap,
             ), patch(
                "apps.api.app.services.pim.fundamentals.fetch_yahoo_fundamentals",
                new_callable=AsyncMock,
                return_value=yahoo_snap,
             ):
            result = await fetch_fundamentals("co-1", "TEST", cik="0000000001")

        assert result.source == "edgar+yahoo"
        assert result.revenue == 1_000_000.0  # from EDGAR
        assert result.price == 50.0            # from Yahoo
        assert result.market_cap == 500_000_000.0

    @pytest.mark.asyncio
    async def test_falls_back_to_yahoo_on_edgar_failure(self):
        yahoo_snap = FundamentalsSnapshot(
            company_id="co-1", ticker="TEST", cik=None,
            period_end="", period_type="ttm",
            price=50.0, source="yahoo",
        )
        with patch("apps.api.app.services.pim.fundamentals._YFINANCE_AVAILABLE", True), \
             patch(
                "apps.api.app.services.pim.fundamentals.fetch_edgar_fundamentals",
                new_callable=AsyncMock,
                side_effect=FundamentalsError("EDGAR error"),
             ), patch(
                "apps.api.app.services.pim.fundamentals.fetch_yahoo_fundamentals",
                new_callable=AsyncMock,
                return_value=yahoo_snap,
             ):
            result = await fetch_fundamentals("co-1", "TEST", cik="123456")

        assert result.source == "yahoo"

    @pytest.mark.asyncio
    async def test_raises_when_all_sources_fail(self):
        with patch("apps.api.app.services.pim.fundamentals._YFINANCE_AVAILABLE", True), \
             patch(
                "apps.api.app.services.pim.fundamentals.fetch_edgar_fundamentals",
                new_callable=AsyncMock,
                side_effect=FundamentalsError("EDGAR error"),
             ), patch(
                "apps.api.app.services.pim.fundamentals.fetch_yahoo_fundamentals",
                new_callable=AsyncMock,
                side_effect=FundamentalsError("Yahoo error"),
             ):
            with pytest.raises(FundamentalsError, match="All data sources failed"):
                await fetch_fundamentals("co-1", "TEST", cik="123456")
