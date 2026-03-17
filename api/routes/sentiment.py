"""POST /sentiment — live multi-source sentiment analysis."""
from __future__ import annotations

import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from data.adapters.india_news_scraper import IndiaNewsScraperClient, StockTwitsClient
from data.adapters.yfinance_client import YFinanceClient
from sentiment.composite_sentiment import get_composite_sentiment
from sentiment.finbert_analyzer import get_finbert_analyzer

logger = structlog.get_logger(__name__)
router = APIRouter()


class SentimentRequest(BaseModel):
    ticker: str
    sources: Optional[List[str]] = None


class ArticleItem(BaseModel):
    source: str
    headline: str
    sentiment: float
    label: str
    date: str


class SentimentResponse(BaseModel):
    ticker: str
    composite_score: float
    composite_label: str
    fear_greed_index: float
    fear_greed_label: str
    articles: List[ArticleItem]


def _normalize_finbert_label(label: str) -> str:
    mapping = {
        "positive": "POSITIVE",
        "negative": "NEGATIVE",
        "neutral": "NEUTRAL",
    }
    return mapping.get(str(label).lower(), "NEUTRAL")


async def build_live_sentiment_response(
    ticker: str,
    sources: Optional[List[str]] = None,
) -> SentimentResponse:
    scraper = IndiaNewsScraperClient()
    stocktwits = StockTwitsClient()
    sentiment_engine = get_composite_sentiment()
    finbert = get_finbert_analyzer()
    yf = YFinanceClient()

    articles = await scraper.get_ticker_news(ticker)
    news_texts = [a.get("title", "").strip() for a in articles if a.get("title")]

    if not news_texts:
        return SentimentResponse(
            ticker=ticker,
            composite_score=0.0,
            composite_label="NEUTRAL",
            fear_greed_index=50.0,
            fear_greed_label="NEUTRAL",
            articles=[],
        )

    finbert_batch, st_messages, vix_df = await asyncio.gather(
        finbert.analyze_texts(news_texts),
        stocktwits.get_symbol_messages(ticker),
        yf.get_india_vix(period="1mo"),
        return_exceptions=True,
    )

    if isinstance(finbert_batch, Exception):
        raise finbert_batch

    if isinstance(st_messages, Exception):
        st_messages = []

    current_vix = None
    if not isinstance(vix_df, Exception) and vix_df is not None and not vix_df.empty:
        current_vix = float(vix_df["vix"].iloc[-1])

    bullish = sum(1 for m in st_messages if m.get("sentiment") == "Bullish")
    bearish = sum(1 for m in st_messages if m.get("sentiment") == "Bearish")
    neutral = len(st_messages) - bullish - bearish
    social_texts = [m.get("body", "") for m in st_messages if m.get("body")]

    composite = await sentiment_engine.analyze(
        ticker=ticker,
        news_texts=news_texts,
        social_texts=social_texts,
        stocktwits_bullish=bullish,
        stocktwits_bearish=bearish,
        stocktwits_neutral=neutral,
        current_vix=current_vix,
    )

    scored_articles: List[ArticleItem] = []
    for article, score_result in zip(articles, finbert_batch.results):
        scored_articles.append(
            ArticleItem(
                source=article.get("source", "news"),
                headline=article.get("title", ""),
                sentiment=round(score_result.score, 4),
                label=_normalize_finbert_label(score_result.label),
                date=article.get("published", ""),
            )
        )

    if sources:
        allowed = {src.lower() for src in sources}
        scored_articles = [a for a in scored_articles if a.source.lower() in allowed]

    return SentimentResponse(
        ticker=ticker,
        composite_score=round(composite.score, 4),
        composite_label=composite.label,
        fear_greed_index=round(composite.fear_greed_index, 2),
        fear_greed_label=composite.fear_greed_label,
        articles=scored_articles,
    )


@router.post("", response_model=SentimentResponse)
async def analyze_sentiment(req: SentimentRequest) -> SentimentResponse:
    logger.info("api.sentiment.request", ticker=req.ticker)
    try:
        return await build_live_sentiment_response(req.ticker, req.sources)
    except Exception as exc:
        logger.error("api.sentiment.error", error=str(exc))
        raise HTTPException(status_code=503, detail=f"Live sentiment unavailable: {exc}") from exc
