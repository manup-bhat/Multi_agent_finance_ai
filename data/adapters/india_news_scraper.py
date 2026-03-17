"""
India RSS + social-news adapter.

This remains the single integration point for zero-key market/news sentiment
sources and now supports:
  - India financial RSS feeds
  - StockTwits symbol streams
  - Yahoo Finance ticker RSS
  - Moneycontrol page/comment scraping (best effort)
  - Alpha Vantage news sentiment (optional when API key is configured)
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

from config.settings import get_settings
from data.adapters.base_adapter import BaseAdapter

try:
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - optional dependency
    BeautifulSoup = None

logger = structlog.get_logger(__name__)
settings = get_settings()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        parsed = parsedate_to_datetime(raw)
        return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _within_window(value: str | None, window_days: int) -> bool:
    parsed = _parse_datetime(value)
    if parsed is None:
        return True
    return parsed >= (_utc_now() - timedelta(days=max(1, window_days)))


def _ticker_aliases(ticker: str) -> list[str]:
    term = ticker.upper().replace(".NS", "").replace(".BO", "")
    aliases = [term]
    if term == "RELIANCE":
        aliases.extend(["AMBANI", "JIO"])
    elif term == "TCS":
        aliases.extend(["TATA CONSULTANCY"])
    elif term == "INFY":
        aliases.extend(["INFOSYS"])
    elif term == "HDFCBANK":
        aliases.extend(["HDFC BANK", "HDFC"])
    elif term == "SBIN":
        aliases.extend(["STATE BANK", "SBI"])
    elif term == "ICICIBANK":
        aliases.extend(["ICICI"])
    elif term == "ITC":
        aliases.extend(["ITC LTD"])
    elif term == "LT":
        aliases.extend(["LARSEN", "L&T"])
    return aliases


def _article_matches_ticker(article: dict, ticker: str) -> bool:
    text = " ".join(
        str(article.get(key, ""))
        for key in ("title", "summary", "headline", "text", "body", "ticker")
    ).upper()
    return any(alias in text for alias in _ticker_aliases(ticker))


class IndiaNewsScraperClient(BaseAdapter):
    def _rss_sources(self) -> dict[str, str]:
        return settings.india_rss_feeds

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _fetch_rss_sync(self, source: str, url: str, max_per_feed: int = 20) -> list[dict]:
        cache_key = self._cache_key("rss", source, url, max_per_feed)
        ttl_seconds = settings.rss_cache_ttl_minutes * 60

        def _load() -> list[dict]:
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[:max_per_feed]:
                articles.append(
                    {
                        "source": source,
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", "")),
                        "url": entry.get("link", ""),
                        "published": entry.get("published", entry.get("updated", "")),
                        "fetched_at": _utc_now().isoformat(),
                    }
                )
            logger.info("rss.fetched", source=source, count=len(articles))
            return articles

        try:
            return self._cached(key=cache_key, ttl_seconds=ttl_seconds, loader=_load)
        except Exception as exc:
            logger.warning("rss.error", source=source, error=str(exc))
            return []

    async def get_all_feeds(self, window_days: int = 3, max_per_feed: int = 20) -> list[dict]:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self._fetch_rss_sync, src, url, max_per_feed)
            for src, url in self._rss_sources().items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles: list[dict] = []
        for result in results:
            if isinstance(result, list):
                articles.extend(article for article in result if _within_window(article.get("published"), window_days))
        logger.info("rss.all_done", total=len(articles), window_days=window_days)
        return articles

    async def get_yahoo_finance_rss(self, ticker: str, window_days: int = 3, max_articles: int = 10) -> list[dict]:
        symbol = ticker.upper().replace(".NS", "").replace(".BO", "")
        url = settings.yahoo_finance_rss_url.format(ticker=f"{symbol}.NS")

        def _load() -> list[dict]:
            feed = feedparser.parse(url)
            articles: list[dict] = []
            for entry in feed.entries[:max_articles]:
                articles.append(
                    {
                        "source": "yahoo_finance",
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", entry.get("description", "")),
                        "url": entry.get("link", ""),
                        "published": entry.get("published", entry.get("updated", "")),
                    }
                )
            return articles

        cache_key = self._cache_key("yahoo_rss", symbol, window_days, max_articles)
        articles = self._cached(
            key=cache_key,
            ttl_seconds=settings.rss_cache_ttl_minutes * 60,
            loader=_load,
        )
        return [article for article in articles if _within_window(article.get("published"), window_days)]

    async def get_alpha_vantage_news_sentiment(
        self,
        ticker: str,
        window_days: int = 3,
        max_articles: int = 10,
    ) -> list[dict]:
        if not settings.alpha_vantage_api_key:
            return []

        symbol = ticker.upper().replace(".NS", "").replace(".BO", "")
        cache_key = self._cache_key("alpha_vantage", symbol, window_days, max_articles)

        def _load() -> list[dict]:
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": f"{symbol}.NSE",
                "apikey": settings.alpha_vantage_api_key,
                "limit": max_articles,
                "sort": "LATEST",
            }
            with httpx.Client(timeout=15.0) as client:
                response = client.get(settings.alpha_vantage_base_url, params=params)
                response.raise_for_status()
                payload = response.json()

            items: list[dict] = []
            for row in payload.get("feed", [])[:max_articles]:
                items.append(
                    {
                        "source": "alpha_vantage",
                        "title": row.get("title", ""),
                        "summary": row.get("summary", ""),
                        "url": row.get("url", ""),
                        "published": row.get("time_published", ""),
                        "sentiment_score": float(row.get("overall_sentiment_score", 0.0) or 0.0),
                        "sentiment_label": row.get("overall_sentiment_label", "Neutral"),
                        "relevance_score": float(row.get("relevance_score", 0.0) or 0.0),
                    }
                )
            return items

        try:
            items = self._cached(
                key=cache_key,
                ttl_seconds=60 * 60,
                loader=_load,
            )
        except Exception as exc:
            logger.warning("alpha_vantage.error", ticker=symbol, error=str(exc))
            return []

        return [item for item in items if _within_window(item.get("published"), window_days)]

    async def get_moneycontrol_comments(
        self,
        ticker: str,
        window_days: int = 3,
        max_items: int = 20,
    ) -> list[dict]:
        if BeautifulSoup is None:
            return []

        symbol = ticker.upper().replace(".NS", "").replace(".BO", "")
        cache_key = self._cache_key("moneycontrol", symbol, window_days, max_items)

        def _load() -> list[dict]:
            url = settings.moneycontrol_news_url
            with httpx.Client(
                timeout=20.0,
                headers={"User-Agent": settings.nse_user_agent},
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

            items: list[dict] = []
            selectors = [
                ".comment-item",
                ".commentBox li",
                "[data-role='comment']",
                ".MCComments li",
                ".clearfix.comment",
            ]
            for selector in selectors:
                for node in soup.select(selector):
                    text = " ".join(node.stripped_strings)
                    if text and any(alias in text.upper() for alias in _ticker_aliases(symbol)):
                        items.append(
                            {
                                "source": "moneycontrol",
                                "text": text[:500],
                                "date": "",
                                "ticker": symbol,
                            }
                        )
                    if len(items) >= max_items:
                        break
                if len(items) >= max_items:
                    break

            if not items:
                for node in soup.select("article, li, p, h2, h3, a"):
                    text = " ".join(node.stripped_strings)
                    if text and any(alias in text.upper() for alias in _ticker_aliases(symbol)):
                        items.append(
                            {
                                "source": "moneycontrol",
                                "text": text[:500],
                                "date": "",
                                "ticker": symbol,
                            }
                        )
                    if len(items) >= max_items:
                        break

            time.sleep(settings.moneycontrol_scrape_delay)
            return items[:max_items]

        try:
            items = self._cached(
                key=cache_key,
                ttl_seconds=settings.rss_cache_ttl_minutes * 60,
                loader=_load,
            )
        except Exception as exc:
            logger.warning("moneycontrol.error", ticker=symbol, error=str(exc))
            return []

        return [item for item in items if _within_window(item.get("date"), window_days)]

    async def get_ticker_news(
        self,
        ticker: str,
        max_articles: int = 10,
        window_days: int = 3,
        include_extras: bool = True,
    ) -> list[dict]:
        base_feeds_task = asyncio.create_task(self.get_all_feeds(window_days=window_days))
        extra_tasks = []
        if include_extras:
            extra_tasks.extend(
                [
                    asyncio.create_task(self.get_yahoo_finance_rss(ticker, window_days=window_days, max_articles=max_articles)),
                    asyncio.create_task(self.get_alpha_vantage_news_sentiment(ticker, window_days=window_days, max_articles=max_articles)),
                ]
            )

        gathered = await asyncio.gather(base_feeds_task, *extra_tasks, return_exceptions=True)
        raw_articles: list[dict] = []
        for result in gathered:
            if isinstance(result, list):
                raw_articles.extend(result)

        matched = [article for article in raw_articles if _article_matches_ticker(article, ticker)]
        if not matched:
            matched = raw_articles[:max_articles]

        deduped: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for article in matched:
            key = (str(article.get("source", "")), str(article.get("title", article.get("url", ""))))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(article)
            if len(deduped) >= max_articles:
                break
        return deduped

    async def health_check(self) -> dict:
        try:
            articles = await self.get_all_feeds()
            return {"status": "ok", "total_articles": len(articles)}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}


class StockTwitsClient:
    """StockTwits — no key. Symbol format: RELIANCE.IN. Rate: 200/hr."""

    async def get_symbol_messages(self, nse_symbol: str, max_messages: int = 30) -> list[dict]:
        st_sym = f"{nse_symbol.upper().replace('.NS', '').replace('.BO', '')}.IN"
        url = f"{settings.stocktwits_base_url}/{st_sym}.json"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            messages = []
            for msg in data.get("messages", [])[:max_messages]:
                sent = msg.get("entities", {}).get("sentiment", {})
                messages.append(
                    {
                        "source": "stocktwits",
                        "body": msg.get("body", ""),
                        "sentiment": sent.get("basic", ""),
                        "created_at": msg.get("created_at", ""),
                        "user": msg.get("user", {}).get("username", ""),
                        "symbol": st_sym,
                    }
                )
            logger.info("stocktwits.fetched", symbol=st_sym, count=len(messages))
            await asyncio.sleep(settings.stocktwits_rate_limit_delay)
            return messages
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                logger.warning("stocktwits.not_found", symbol=st_sym)
                return []
            logger.warning("stocktwits.status_error", symbol=st_sym, error=str(exc))
            return []
        except Exception as exc:
            logger.warning("stocktwits.error", symbol=st_sym, error=str(exc))
            return []

    async def health_check(self) -> dict:
        msgs = await self.get_symbol_messages("RELIANCE")
        return {"status": "ok", "stocktwits_messages": len(msgs)}
