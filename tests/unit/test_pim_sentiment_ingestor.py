"""PIM-1.4: Sentiment ingestor unit tests."""
from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from apps.api.app.services.pim.sentiment_ingestor import (
    SentimentIngestor,
    _first_of_month,
    _monday_of,
    _signal_id,
)

TENANT = "tenant-ingestor-test"


# --- Helper function tests ---


def test_signal_id_is_deterministic() -> None:
    id1 = _signal_id(TENANT, "polygon_news", "https://example.com/article-1")
    id2 = _signal_id(TENANT, "polygon_news", "https://example.com/article-1")
    assert id1 == id2
    assert len(id1) == 24


def test_signal_id_differs_for_different_inputs() -> None:
    id1 = _signal_id(TENANT, "polygon_news", "https://example.com/article-1")
    id2 = _signal_id(TENANT, "polygon_news", "https://example.com/article-2")
    assert id1 != id2


def test_monday_of_returns_monday() -> None:
    wednesday = date(2026, 3, 11)
    result = _monday_of(wednesday)
    assert result == date(2026, 3, 9)
    assert result.weekday() == 0  # Monday


def test_monday_of_monday_returns_same_day() -> None:
    monday = date(2026, 3, 9)
    result = _monday_of(monday)
    assert result == monday


def test_monday_of_sunday_returns_prior_monday() -> None:
    sunday = date(2026, 3, 15)
    result = _monday_of(sunday)
    assert result == date(2026, 3, 9)


def test_first_of_month_returns_first() -> None:
    mid_month = date(2026, 3, 15)
    result = _first_of_month(mid_month)
    assert result == date(2026, 3, 1)


def test_first_of_month_already_first() -> None:
    first = date(2026, 3, 1)
    result = _first_of_month(first)
    assert result == date(2026, 3, 1)


# --- fetch_news tests ---


async def test_fetch_news_no_api_key() -> None:
    ingestor = SentimentIngestor(polygon_api_key=None)
    result = await ingestor.fetch_news("AAPL")
    assert result == []


async def test_fetch_news_http_error() -> None:
    """fetch_news propagates httpx errors — callers (ingest_for_company) catch them."""
    import httpx

    # The inner client object (returned by __aenter__) raises on .get()
    inner_client = MagicMock()
    inner_client.get = AsyncMock(side_effect=httpx.RequestError("connection failed"))

    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=inner_client)
    mock_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("apps.api.app.services.pim.sentiment_ingestor.httpx.AsyncClient", return_value=mock_cm):
        ingestor = SentimentIngestor(polygon_api_key="test-key")
        with pytest.raises(httpx.RequestError):
            await ingestor.fetch_news("AAPL")


# --- extract_sentiment tests ---


async def test_extract_sentiment_calls_llm() -> None:
    llm_mock = MagicMock()
    resp_mock = MagicMock()
    resp_mock.content = {"sentiment_score": 0.5, "confidence": 0.8, "reasoning": "positive outlook"}
    resp_mock.model = "claude-3-haiku"
    llm_mock.complete_with_routing = AsyncMock(return_value=resp_mock)

    ingestor = SentimentIngestor(polygon_api_key=None, llm_router=llm_mock)
    result = await ingestor.extract_sentiment(
        tenant_id=TENANT,
        headline="Apple reports record earnings",
        text_excerpt="Apple Inc. posted record quarterly results...",
        company_name="Apple Inc",
    )

    assert result["sentiment_score"] == pytest.approx(0.5)
    assert result["confidence"] == pytest.approx(0.8)
    assert result["reasoning"] == "positive outlook"
    assert result["model"] == "claude-3-haiku"


async def test_extract_sentiment_clamps_score() -> None:
    llm_mock = MagicMock()
    resp_mock = MagicMock()
    resp_mock.content = {"sentiment_score": 2.0, "confidence": 0.9, "reasoning": "very positive"}
    resp_mock.model = "claude-3-haiku"
    llm_mock.complete_with_routing = AsyncMock(return_value=resp_mock)

    ingestor = SentimentIngestor(polygon_api_key=None, llm_router=llm_mock)
    result = await ingestor.extract_sentiment(
        tenant_id=TENANT,
        headline="Test headline",
        text_excerpt="Test excerpt",
        company_name="Test Co",
    )

    assert result["sentiment_score"] == pytest.approx(1.0)


async def test_extract_sentiment_clamps_confidence() -> None:
    llm_mock = MagicMock()
    resp_mock = MagicMock()
    resp_mock.content = {"sentiment_score": 0.3, "confidence": -0.5, "reasoning": "uncertain"}
    resp_mock.model = "claude-3-haiku"
    llm_mock.complete_with_routing = AsyncMock(return_value=resp_mock)

    ingestor = SentimentIngestor(polygon_api_key=None, llm_router=llm_mock)
    result = await ingestor.extract_sentiment(
        tenant_id=TENANT,
        headline="Test headline",
        text_excerpt="Test excerpt",
        company_name="Test Co",
    )

    assert result["confidence"] == pytest.approx(0.0)


async def test_extract_sentiment_uses_temperature_01() -> None:
    llm_mock = MagicMock()
    resp_mock = MagicMock()
    resp_mock.content = {"sentiment_score": 0.0, "confidence": 0.5, "reasoning": "neutral"}
    resp_mock.model = "claude-3-haiku"
    llm_mock.complete_with_routing = AsyncMock(return_value=resp_mock)

    ingestor = SentimentIngestor(polygon_api_key=None, llm_router=llm_mock)
    await ingestor.extract_sentiment(
        tenant_id=TENANT,
        headline="Neutral headline",
        text_excerpt="Neutral excerpt",
        company_name="Neutral Corp",
    )

    call_kwargs = llm_mock.complete_with_routing.call_args
    assert call_kwargs.kwargs.get("temperature") == pytest.approx(0.1)


# --- ingest_for_company tests ---


async def test_ingest_no_news() -> None:
    llm_mock = MagicMock()
    llm_mock.complete_with_routing = AsyncMock()

    ingestor = SentimentIngestor(polygon_api_key=None, llm_router=llm_mock)
    # patch fetch_news to confirm it returns []
    ingestor.fetch_news = AsyncMock(return_value=[])  # type: ignore[method-assign]

    result = await ingestor.ingest_for_company(
        tenant_id=TENANT,
        company_id="pco_1",
        ticker="AAPL",
        company_name="Apple Inc",
    )

    assert result == 0
    # store_signal should never be called when there are no articles
    llm_mock.complete_with_routing.assert_not_called()
