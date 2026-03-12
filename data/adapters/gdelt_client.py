"""
GDELT v2 adapter — global macro event tone filtered to India (IN).
No API key. Free, unlimited. Real-time.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential
from config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class GDELTClient:

    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def get_india_tone(
        self,
        query: str = "India economy stock market NSE Nifty",
        days_back: int = 1,
        max_records: int = 50,
    ) -> list[dict]:
        """
        India-filtered GDELT articles with V2Tone score (-10 to +10).
        Positive = positive sentiment, Negative = fear/negativity.
        """
        end   = datetime.utcnow()
        start = end - timedelta(days=days_back)
        params = {
            "query":       f"{query} sourcecountry:IN",
            "mode":        "artlist",
            "maxrecords":  max_records,
            "startdatetime": start.strftime("%Y%m%d%H%M%S"),
            "enddatetime":   end.strftime("%Y%m%d%H%M%S"),
            "format":      "json",
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            articles = []
            for art in data.get("articles", []):
                tone_str = art.get("tone", "0")
                try:
                    tone = float(tone_str.split(",")[0]) if "," in str(tone_str) else float(tone_str)
                except (ValueError, TypeError):
                    tone = 0.0
                articles.append({
                    "title":   art.get("title", ""),
                    "url":     art.get("url", ""),
                    "source":  art.get("domain", ""),
                    "tone":    tone,            # V2Tone: positive = good news
                    "seendate": art.get("seendate", ""),
                })
            avg_tone = sum(a["tone"] for a in articles) / max(len(articles), 1)
            logger.info("gdelt.fetched", count=len(articles), avg_tone=round(avg_tone, 2))
            return articles
        except Exception as e:
            logger.warning("gdelt.error", error=str(e))
            return []

    async def get_india_tone_score(self, days_back: int = 1) -> float:
        """Single composite India tone score (-10 to +10) for agent consumption."""
        articles = await self.get_india_tone(days_back=days_back)
        if not articles:
            return 0.0
        return sum(a["tone"] for a in articles) / len(articles)

    async def health_check(self) -> dict:
        try:
            score = await self.get_india_tone_score()
            return {"status": "ok", "india_tone_score": round(score, 2)}
        except Exception as e:
            return {"status": "error", "error": str(e)}