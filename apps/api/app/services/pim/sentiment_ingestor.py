"""PIM-1.4: Sentiment ingestion service.

Fetches news from Polygon.io, extracts sentiment via LLM, stores raw signals,
and computes weekly/monthly aggregates.

FR-1.1: Ingest from >= 2 text sources (news API + earnings transcripts)
FR-1.2: Per-company sentiment score in [-1, +1] with confidence in [0, 1]
FR-1.3: Aggregate to weekly and monthly time-series per company
FR-1.5: Tenant-scoped storage; no cross-tenant data leakage
FR-1.6: LLM extraction uses pim_sentiment_extraction label (temp = 0.1)
"""

from __future__ import annotations

import hashlib
import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx
import structlog

logger = structlog.get_logger()

# ------------------------------------------------------------------
# LLM response schema for sentiment extraction
# ------------------------------------------------------------------
SENTIMENT_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sentiment_score": {
            "type": "number",
            "description": "Sentiment score from -1.0 (very negative) to +1.0 (very positive)",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence in the sentiment assessment from 0.0 to 1.0",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief explanation of the sentiment assessment",
        },
    },
    "required": ["sentiment_score", "confidence", "reasoning"],
    "additionalProperties": False,
}

# Polygon.io news API base URL
POLYGON_NEWS_URL = "https://api.polygon.io/v2/reference/news"


def _signal_id(tenant_id: str, source_type: str, source_ref: str) -> str:
    """Deterministic signal ID to prevent duplicates."""
    raw = f"{tenant_id}:{source_type}:{source_ref}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _monday_of(d: date) -> date:
    """Return the Monday of the week containing *d*."""
    return d - timedelta(days=d.weekday())


def _first_of_month(d: date) -> date:
    """Return the first day of the month containing *d*."""
    return d.replace(day=1)


class SentimentIngestor:
    """Orchestrates Polygon.io news fetch → LLM extraction → DB storage → aggregation."""

    def __init__(
        self,
        polygon_api_key: str | None,
        llm_router: Any | None = None,
        db_pool: Any | None = None,
    ) -> None:
        self._polygon_key = polygon_api_key
        self._llm = llm_router
        self._pool = db_pool

    # ------------------------------------------------------------------
    # 1. Fetch news from Polygon.io
    # ------------------------------------------------------------------

    async def fetch_news(self, ticker: str, limit: int = 50) -> list[dict[str, Any]]:
        """Fetch recent news articles from Polygon.io for a ticker.

        Returns list of dicts with keys: article_url, title, description, published_utc.
        """
        if not self._polygon_key:
            logger.warning("polygon_api_key not configured; skipping news fetch")
            return []

        params: dict[str, Any] = {
            "ticker": ticker,
            "limit": min(limit, 100),
            "order": "desc",
            "sort": "published_utc",
            "apiKey": self._polygon_key,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(POLYGON_NEWS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        results: list[dict[str, Any]] = []
        for article in data.get("results", []):
            results.append({
                "article_url": article.get("article_url", ""),
                "title": article.get("title", ""),
                "description": article.get("description", ""),
                "published_utc": article.get("published_utc", ""),
                "publisher_name": (article.get("publisher") or {}).get("name", ""),
            })
        return results

    # ------------------------------------------------------------------
    # 2. Extract sentiment via LLM
    # ------------------------------------------------------------------

    async def extract_sentiment(
        self,
        tenant_id: str,
        headline: str,
        text_excerpt: str,
        company_name: str,
    ) -> dict[str, Any]:
        """Call LLM with pim_sentiment_extraction label to score an article.

        Returns dict with sentiment_score, confidence, reasoning, model.
        """
        if self._llm is None:
            raise RuntimeError("LLM router not configured on SentimentIngestor")

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a financial sentiment analyst. Analyse the following news "
                    f"headline and excerpt about {company_name}. "
                    "Return a sentiment_score in [-1.0, +1.0] where -1 is extremely negative "
                    "and +1 is extremely positive, a confidence in [0.0, 1.0], "
                    "and a brief reasoning."
                ),
            },
            {
                "role": "user",
                "content": f"Headline: {headline}\n\nExcerpt: {text_excerpt[:2000]}",
            },
        ]

        resp = await self._llm.complete_with_routing(
            tenant_id=tenant_id,
            messages=messages,
            response_schema=SENTIMENT_EXTRACTION_SCHEMA,
            task_label="pim_sentiment_extraction",
        )

        content = resp.content
        # Clamp values to valid ranges
        score = max(-1.0, min(1.0, float(content.get("sentiment_score", 0))))
        conf = max(0.0, min(1.0, float(content.get("confidence", 0.5))))

        return {
            "sentiment_score": score,
            "confidence": conf,
            "reasoning": content.get("reasoning", ""),
            "model": resp.model,
        }

    # ------------------------------------------------------------------
    # 3. Store raw signal
    # ------------------------------------------------------------------

    async def store_signal(
        self,
        tenant_id: str,
        company_id: str,
        source_type: str,
        source_ref: str,
        headline: str,
        published_at: datetime,
        sentiment_score: float,
        confidence: float,
        raw_text_excerpt: str | None = None,
        llm_model: str | None = None,
        extraction_meta: dict[str, Any] | None = None,
    ) -> str:
        """Insert a raw sentiment signal into pim_sentiment_signals.

        Returns the signal_id. Skips on duplicate (ON CONFLICT DO NOTHING).
        """
        if self._pool is None:
            raise RuntimeError("DB pool not configured on SentimentIngestor")

        signal_id = _signal_id(tenant_id, source_type, source_ref)
        import json as _json

        async with self._pool.acquire() as conn:
            await conn.execute("SET app.tenant_id = $1", tenant_id)
            try:
                await conn.execute(
                    """INSERT INTO pim_sentiment_signals
                       (tenant_id, signal_id, company_id, source_type, source_ref,
                        headline, published_at, sentiment_score, confidence,
                        raw_text_excerpt, llm_model, extraction_meta)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12::jsonb)
                       ON CONFLICT (tenant_id, signal_id, published_at) DO NOTHING""",
                    tenant_id,
                    signal_id,
                    company_id,
                    source_type,
                    source_ref,
                    headline[:500] if headline else None,
                    published_at,
                    sentiment_score,
                    confidence,
                    (raw_text_excerpt[:2000] if raw_text_excerpt else None),
                    llm_model,
                    _json.dumps(extraction_meta or {}),
                )
            finally:
                await conn.execute("SET app.tenant_id = ''")

        return signal_id

    # ------------------------------------------------------------------
    # 4. Ingest pipeline for one company
    # ------------------------------------------------------------------

    async def ingest_for_company(
        self,
        tenant_id: str,
        company_id: str,
        ticker: str,
        company_name: str,
    ) -> int:
        """Full pipeline: fetch news → extract sentiment → store signals.

        Returns the number of new signals stored.
        """
        articles = await self.fetch_news(ticker)
        if not articles:
            return 0

        stored = 0
        for article in articles:
            url = article.get("article_url", "")
            title = article.get("title", "")
            description = article.get("description", "")
            published_str = article.get("published_utc", "")

            if not url or not title:
                continue

            # Parse published_at
            try:
                published_at = datetime.fromisoformat(published_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                published_at = datetime.now(UTC)

            # Extract sentiment via LLM
            try:
                result = await self.extract_sentiment(
                    tenant_id=tenant_id,
                    headline=title,
                    text_excerpt=description or title,
                    company_name=company_name,
                )
            except Exception:
                logger.warning(
                    "sentiment_extraction_failed",
                    tenant_id=tenant_id,
                    company_id=company_id,
                    article_url=url,
                    exc_info=True,
                )
                continue

            await self.store_signal(
                tenant_id=tenant_id,
                company_id=company_id,
                source_type="news_api",
                source_ref=url,
                headline=title,
                published_at=published_at,
                sentiment_score=result["sentiment_score"],
                confidence=result["confidence"],
                raw_text_excerpt=description[:2000] if description else None,
                llm_model=result.get("model"),
                extraction_meta={"reasoning": result.get("reasoning", "")},
            )
            stored += 1

        return stored

    # ------------------------------------------------------------------
    # 5. Compute aggregates
    # ------------------------------------------------------------------

    async def aggregate(self, tenant_id: str, company_id: str) -> int:
        """Recompute weekly and monthly aggregates from raw signals.

        Uses a rolling window: last 12 months of signals.
        Returns the number of aggregate rows upserted.
        """
        if self._pool is None:
            raise RuntimeError("DB pool not configured on SentimentIngestor")

        cutoff = datetime.now(UTC) - timedelta(days=365)
        import json as _json

        async with self._pool.acquire() as conn:
            await conn.execute("SET app.tenant_id = $1", tenant_id)
            try:
                # Fetch raw signals
                rows = await conn.fetch(
                    """SELECT published_at, sentiment_score, confidence, source_type
                       FROM pim_sentiment_signals
                       WHERE tenant_id = $1 AND company_id = $2 AND published_at >= $3
                       ORDER BY published_at""",
                    tenant_id,
                    company_id,
                    cutoff,
                )

                if not rows:
                    return 0

                # Group by week and month
                weekly: dict[date, list[dict[str, Any]]] = {}
                monthly: dict[date, list[dict[str, Any]]] = {}
                for row in rows:
                    pub_date = row["published_at"].date() if hasattr(row["published_at"], "date") else row["published_at"]
                    entry = {
                        "score": float(row["sentiment_score"]),
                        "confidence": float(row["confidence"]),
                        "source_type": row["source_type"],
                    }
                    wk = _monday_of(pub_date)
                    weekly.setdefault(wk, []).append(entry)
                    mo = _first_of_month(pub_date)
                    monthly.setdefault(mo, []).append(entry)

                upserted = 0

                for period_type, buckets in [("weekly", weekly), ("monthly", monthly)]:
                    for period_start, signals in buckets.items():
                        scores = [s["score"] for s in signals]
                        confidences = [s["confidence"] for s in signals]

                        # Weighted average by confidence
                        total_weight = sum(confidences)
                        if total_weight > 0:
                            avg_sent = sum(s * c for s, c in zip(scores, confidences)) / total_weight
                        else:
                            avg_sent = statistics.mean(scores)
                        avg_sent = max(-1.0, min(1.0, avg_sent))

                        median_sent = statistics.median(scores) if scores else None
                        min_sent = min(scores) if scores else None
                        max_sent = max(scores) if scores else None
                        std_sent = statistics.stdev(scores) if len(scores) >= 2 else None
                        avg_conf = statistics.mean(confidences) if confidences else None

                        # Source breakdown
                        src_breakdown: dict[str, int] = {}
                        for s in signals:
                            st = s["source_type"]
                            src_breakdown[st] = src_breakdown.get(st, 0) + 1

                        # Trend direction (compare to previous period)
                        trend = None  # Computed externally or in future pass

                        if period_type == "weekly":
                            period_end = period_start + timedelta(days=6)
                        else:
                            # End of month
                            next_month = (period_start.replace(day=28) + timedelta(days=4)).replace(day=1)
                            period_end = next_month - timedelta(days=1)

                        await conn.execute(
                            """INSERT INTO pim_sentiment_aggregates
                               (tenant_id, company_id, period_type, period_start, period_end,
                                avg_sentiment, median_sentiment, min_sentiment, max_sentiment,
                                std_sentiment, signal_count, avg_confidence, source_breakdown,
                                trend_direction)
                               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14)
                               ON CONFLICT (tenant_id, company_id, period_type, period_start)
                               DO UPDATE SET
                                 avg_sentiment = EXCLUDED.avg_sentiment,
                                 median_sentiment = EXCLUDED.median_sentiment,
                                 min_sentiment = EXCLUDED.min_sentiment,
                                 max_sentiment = EXCLUDED.max_sentiment,
                                 std_sentiment = EXCLUDED.std_sentiment,
                                 signal_count = EXCLUDED.signal_count,
                                 avg_confidence = EXCLUDED.avg_confidence,
                                 source_breakdown = EXCLUDED.source_breakdown,
                                 trend_direction = EXCLUDED.trend_direction,
                                 period_end = EXCLUDED.period_end""",
                            tenant_id,
                            company_id,
                            period_type,
                            period_start,
                            period_end,
                            avg_sent,
                            median_sent,
                            min_sent,
                            max_sent,
                            std_sent,
                            len(signals),
                            avg_conf,
                            _json.dumps(src_breakdown),
                            trend,
                        )
                        upserted += 1

                return upserted
            finally:
                await conn.execute("SET app.tenant_id = ''")

    # ------------------------------------------------------------------
    # 6. Refresh all companies in a tenant's universe
    # ------------------------------------------------------------------

    async def refresh_all(self, tenant_id: str) -> dict[str, int]:
        """Refresh sentiment for all active companies in the tenant's universe.

        Returns dict of {company_id: signals_stored}.
        """
        if self._pool is None:
            raise RuntimeError("DB pool not configured on SentimentIngestor")

        async with self._pool.acquire() as conn:
            await conn.execute("SET app.tenant_id = $1", tenant_id)
            try:
                companies = await conn.fetch(
                    """SELECT company_id, ticker, company_name
                       FROM pim_universes
                       WHERE tenant_id = $1 AND is_active = true""",
                    tenant_id,
                )
            finally:
                await conn.execute("SET app.tenant_id = ''")

        results: dict[str, int] = {}
        for company in companies:
            cid = company["company_id"]
            try:
                count = await self.ingest_for_company(
                    tenant_id=tenant_id,
                    company_id=cid,
                    ticker=company["ticker"],
                    company_name=company["company_name"],
                )
                results[cid] = count
                # Recompute aggregates after ingestion
                if count > 0:
                    await self.aggregate(tenant_id, cid)
            except Exception:
                logger.warning(
                    "sentiment_refresh_company_failed",
                    tenant_id=tenant_id,
                    company_id=cid,
                    exc_info=True,
                )
                results[cid] = 0

        return results
