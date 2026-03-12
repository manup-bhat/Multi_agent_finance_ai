"""
Social Sentiment Adapter — Reddit-free Implementation
Replaces praw/reddit_client.py

Sources (all zero-key, zero-cost):
  1. StockTwits API  — real-time India stock messages + built-in sentiment
  2. India RSS feeds — ET Markets, LiveMint, Business Standard, TheHindu

Why no Reddit:
  - Reddit API now requires verified developer account + app approval
  - StockTwits has native sentiment labels (Bullish/Bearish) per message
  - RSS feeds cover institutional and retail India financial news directly

Usage:
  client = SocialSentimentClient()
  data = await client.get_sentiment("RELIANCE")
"""
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp
import feedparser
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

# ── StockTwits India symbols (NSE → StockTwits format) ───────────────────────
# StockTwits uses NSE symbol + .IN suffix for Indian stocks
NSE_TO_STOCKTWITS = {
    "RELIANCE": "RELIANCE.IN",
    "TCS": "TCS.IN",
    "HDFCBANK": "HDFCBANK.IN",
    "INFY": "INFY.IN",
    "ICICIBANK": "ICICIBANK.IN",
    "HINDUNILVR": "HINDUNILVR.IN",
    "WIPRO": "WIPRO.IN",
    "AXISBANK": "AXISBANK.IN",
    "KOTAKBANK": "KOTAKBANK.IN",
    "BAJFINANCE": "BAJFINANCE.IN",
    "LT": "LT.IN",
    "SBIN": "SBIN.IN",
    "ASIANPAINT": "ASIANPAINT.IN",
    "MARUTI": "MARUTI.IN",
    "TITAN": "TITAN.IN",
    "ULTRACEMCO": "ULTRACEMCO.IN",
    "NESTLEIND": "NESTLEIND.IN",
    "SUNPHARMA": "SUNPHARMA.IN",
    "POWERGRID": "POWERGRID.IN",
    "NTPC": "NTPC.IN",
}

# ── RSS Feed URLs (from .env — pre-verified March 2026) ──────────────────────
RSS_FEEDS = {
    "economic_times_markets":  "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "economic_times_stocks":   "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "livemint_markets":        "https://www.livemint.com/rss/markets",
    "business_standard":       "https://www.business-standard.com/rss/markets-106.rss",
    "the_hindu_markets":       "https://www.thehindu.com/business/markets/feeder/default.rss",
}

STOCKTWITS_BASE_URL = "https://api.stocktwits.com/api/2/streams/symbol"
RATE_LIMIT_DELAY = 18  # seconds between StockTwits calls (200 req/hour limit)

_last_stocktwits_call: float = 0.0


@dataclass
class StockTwitMessage:
    id: int
    body: str
    sentiment: Optional[str]   # "Bullish" | "Bearish" | None
    created_at: str
    user_followers: int = 0


@dataclass
class RSSArticle:
    title: str
    summary: str
    link: str
    published: str
    source: str


@dataclass
class SocialSentimentData:
    symbol: str
    stocktwits_messages: list[StockTwitMessage] = field(default_factory=list)
    rss_articles: list[RSSArticle] = field(default_factory=list)
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    # Computed ratio: +1.0 = all bullish, -1.0 = all bearish
    sentiment_ratio: float = 0.0
    raw_sentiment_label: str = "NEUTRAL"  # BULLISH | BEARISH | NEUTRAL


class SocialSentimentClient:
    """
    Async client for StockTwits + India RSS feeds.
    No Reddit API required. No keys needed.

    Rate limits:
      StockTwits: 200 req/hour → enforce 18s delay between calls
      RSS: No limit (self-throttle to 2s between feeds)
    """

    def __init__(self):
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "User-Agent": "IndiaFinanceEngine/1.0 (market research tool)",
                    "Accept": "application/json",
                },
                timeout=aiohttp.ClientTimeout(total=15),
            )
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── StockTwits ────────────────────────────────────────────────────────────

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    async def get_stocktwits(self, nse_symbol: str) -> list[StockTwitMessage]:
        """
        Fetch recent messages for an NSE stock from StockTwits.
        No API key required. Returns up to 30 most recent messages.

        Args:
            nse_symbol: NSE symbol e.g. "RELIANCE", "HDFCBANK"
        Returns:
            List of StockTwitMessage with native Bullish/Bearish labels
        """
        global _last_stocktwits_call

        # Enforce rate limit: 200 req/hour = 18s between calls
        elapsed = time.time() - _last_stocktwits_call
        if elapsed < RATE_LIMIT_DELAY:
            await asyncio.sleep(RATE_LIMIT_DELAY - elapsed)

        st_symbol = NSE_TO_STOCKTWITS.get(nse_symbol, f"{nse_symbol}.IN")
        url = f"{STOCKTWITS_BASE_URL}/{st_symbol}.json"

        session = await self._get_session()
        try:
            async with session.get(url) as resp:
                _last_stocktwits_call = time.time()
                if resp.status == 429:
                    logger.warning("stocktwits.rate_limit", symbol=st_symbol)
                    await asyncio.sleep(60)
                    return []
                if resp.status != 200:
                    logger.warning(
                        "stocktwits.bad_status",
                        symbol=st_symbol,
                        status=resp.status,
                    )
                    return []
                data = await resp.json(content_type=None)

        except Exception as e:
            logger.error("stocktwits.fetch_error", symbol=nse_symbol, error=str(e))
            return []

        messages = []
        for msg in data.get("messages", []):
            sentiment_obj = msg.get("entities", {}).get("sentiment", None)
            sentiment = sentiment_obj.get("basic") if sentiment_obj else None
            messages.append(
                StockTwitMessage(
                    id=msg.get("id", 0),
                    body=msg.get("body", ""),
                    sentiment=sentiment,        # "Bullish" | "Bearish" | None
                    created_at=msg.get("created_at", ""),
                    user_followers=msg.get("user", {}).get("followers", 0),
                )
            )

        logger.info(
            "stocktwits.fetched",
            symbol=nse_symbol,
            count=len(messages),
            st_symbol=st_symbol,
        )
        return messages

    # ── RSS Feeds ─────────────────────────────────────────────────────────────

    async def get_india_rss(
        self,
        symbol_filter: Optional[str] = None,
        max_per_feed: int = 10,
    ) -> list[RSSArticle]:
        """
        Fetch India financial news from RSS feeds.
        No API key required. Filtered optionally by stock symbol.

        Args:
            symbol_filter: Optional NSE symbol to filter headlines (e.g. "RELIANCE")
            max_per_feed: Max articles to return per RSS source
        Returns:
            List of RSSArticle from all India RSS feeds
        """
        articles = []
        for source_name, url in RSS_FEEDS.items():
            try:
                feed = await asyncio.get_event_loop().run_in_executor(
                    None, feedparser.parse, url
                )
                for entry in feed.entries[:max_per_feed]:
                    title = entry.get("title", "")
                    summary = entry.get("summary", "")

                    # Filter by symbol if requested
                    if symbol_filter:
                        combined = f"{title} {summary}".upper()
                        if symbol_filter.upper() not in combined:
                            continue

                    articles.append(
                        RSSArticle(
                            title=title,
                            summary=summary,
                            link=entry.get("link", ""),
                            published=entry.get("published", ""),
                            source=source_name,
                        )
                    )
                # Polite delay between feeds
                await asyncio.sleep(random.uniform(1.5, 2.5))

            except Exception as e:
                logger.warning(
                    "rss.fetch_error",
                    source=source_name,
                    error=str(e),
                )
                continue

        logger.info(
            "rss.fetched",
            total_articles=len(articles),
            symbol_filter=symbol_filter,
        )
        return articles

    # ── Combined ──────────────────────────────────────────────────────────────

    async def get_sentiment(self, nse_symbol: str) -> SocialSentimentData:
        """
        Main entry point. Fetches StockTwits + RSS and returns combined data.

        Args:
            nse_symbol: NSE symbol e.g. "RELIANCE"
        Returns:
            SocialSentimentData with messages, articles, and sentiment_ratio
        """
        # Run StockTwits and RSS fetch concurrently
        stocktwits_task = asyncio.create_task(self.get_stocktwits(nse_symbol))
        rss_task = asyncio.create_task(
            self.get_india_rss(symbol_filter=nse_symbol, max_per_feed=5)
        )

        messages, articles = await asyncio.gather(
            stocktwits_task, rss_task, return_exceptions=False
        )

        # Compute sentiment from StockTwits native labels
        bullish = sum(1 for m in messages if m.sentiment == "Bullish")
        bearish = sum(1 for m in messages if m.sentiment == "Bearish")
        neutral = len(messages) - bullish - bearish

        total_labelled = bullish + bearish
        if total_labelled > 0:
            ratio = (bullish - bearish) / total_labelled
        else:
            ratio = 0.0

        if ratio > 0.2:
            label = "BULLISH"
        elif ratio < -0.2:
            label = "BEARISH"
        else:
            label = "NEUTRAL"

        return SocialSentimentData(
            symbol=nse_symbol,
            stocktwits_messages=messages,
            rss_articles=articles,
            bullish_count=bullish,
            bearish_count=bearish,
            neutral_count=neutral,
            sentiment_ratio=ratio,
            raw_sentiment_label=label,
        )


# ── Quick test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    async def _test():
        client = SocialSentimentClient()
        print("Testing StockTwits + RSS (no Reddit needed)...")
        data = await client.get_sentiment("RELIANCE")
        print(f"Symbol:          {data.symbol}")
        print(f"StockTwits msgs: {len(data.stocktwits_messages)}")
        print(f"RSS articles:    {len(data.rss_articles)}")
        print(f"Bullish:         {data.bullish_count}")
        print(f"Bearish:         {data.bearish_count}")
        print(f"Sentiment ratio: {data.sentiment_ratio:.3f}")
        print(f"Label:           {data.raw_sentiment_label}")
        await client.close()

    asyncio.run(_test())