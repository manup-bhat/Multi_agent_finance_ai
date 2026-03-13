"""
India RSS + StockTwits adapter. No API key needed.
Replaces praw (Reddit API removed). Social sentiment via StockTwits .IN + RSS.
"""
from __future__ import annotations
import asyncio
from datetime import datetime
import feedparser
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

RSS_FEEDS: dict[str, str] = {
    "et_markets":        "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms",
    "et_stocks":         "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms",
    "livemint_markets":  "https://www.livemint.com/rss/markets",
    "business_standard": "https://www.business-standard.com/rss/markets-106.rss",
    "the_hindu_markets": "https://www.thehindu.com/business/markets/feeder/default.rss",
}


class IndiaNewsScraperClient:

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=8))
    def _fetch_rss_sync(self, source: str, url: str) -> list[dict]:
        try:
            feed = feedparser.parse(url)
            articles = []
            for entry in feed.entries[:20]:
                articles.append({
                    "source":     source,
                    "title":      entry.get("title", ""),
                    "summary":    entry.get("summary", entry.get("description", "")),
                    "url":        entry.get("link", ""),
                    "published":  entry.get("published", ""),
                    "fetched_at": datetime.now().isoformat(),
                })
            logger.info("rss.fetched", source=source, count=len(articles))
            return articles
        except Exception as e:
            logger.warning("rss.error", source=source, error=str(e))
            return []

    async def get_all_feeds(self) -> list[dict]:
        loop = asyncio.get_event_loop()
        tasks = [
            loop.run_in_executor(None, self._fetch_rss_sync, src, url)
            for src, url in RSS_FEEDS.items()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        articles: list[dict] = []
        for r in results:
            if isinstance(r, list):
                articles.extend(r)
        logger.info("rss.all_done", total=len(articles))
        return articles

    async def get_ticker_news(self, ticker: str, max_articles: int = 10) -> list[dict]:
        term = ticker.upper().replace(".NS", "").replace(".BO", "")
        # Add basic aliases for common Indian stocks to catch more news
        aliases = [term]
        if term == "RELIANCE": aliases.extend(["AMBANI", "JIO"])
        elif term == "TCS": aliases.extend(["TATA CONSULTANCY"])
        elif term == "INFY": aliases.extend(["INFOSYS"])
        elif term == "HDFCBANK": aliases.extend(["HDFC"])
        elif term == "SBIN": aliases.extend(["STATE BANK", "SBI"])
        elif term == "ICICIBANK": aliases.extend(["ICICI"])
        elif term == "ITC": aliases.extend(["ITC LTD"])
        elif term == "LT": aliases.extend(["LARSEN"])
        
        all_a = await self.get_all_feeds()
        matched = []
        for a in all_a:
            text = (a["title"] + " " + a["summary"]).upper()
            if any(alias in text for alias in aliases):
                matched.append(a)
                
        # If still empty, just return the latest general market news to avoid a blank UI box
        if not matched:
            matched = all_a[:max_articles]
            
        return matched[:max_articles]

    async def health_check(self) -> dict:
        try:
            articles = await self.get_all_feeds()
            return {"status": "ok", "total_articles": len(articles)}
        except Exception as e:
            return {"status": "error", "error": str(e)}


class StockTwitsClient:
    """StockTwits — no key. Symbol format: RELIANCE.IN  Rate: 200/hr → 18s delay."""

    async def get_symbol_messages(self, nse_symbol: str, max_messages: int = 30) -> list[dict]:
        st_sym = f"{nse_symbol.upper().replace('.NS','').replace('.BO','')}.IN"
        url    = f"{settings.stocktwits_base_url}/{st_sym}.json"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
            messages = []
            for msg in data.get("messages", [])[:max_messages]:
                sent = msg.get("entities", {}).get("sentiment", {})
                messages.append({
                    "source":     "stocktwits",
                    "body":       msg.get("body", ""),
                    "sentiment":  sent.get("basic", ""),  # "Bullish"|"Bearish"|""
                    "created_at": msg.get("created_at", ""),
                    "user":       msg.get("user", {}).get("username", ""),
                    "symbol":     st_sym,
                })
            logger.info("stocktwits.fetched", symbol=st_sym, count=len(messages))
            await asyncio.sleep(settings.stocktwits_rate_limit_delay)
            return messages
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning("stocktwits.not_found", symbol=st_sym)
                return []
            return []
        except Exception as e:
            logger.warning("stocktwits.error", symbol=st_sym, error=str(e))
            return []

    async def health_check(self) -> dict:
        msgs = await self.get_symbol_messages("RELIANCE")
        return {"status": "ok", "stocktwits_messages": len(msgs)}