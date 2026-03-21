"""POST /sentiment — live multi-source sentiment analysis."""
from __future__ import annotations

import asyncio
import threading
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List, Optional

import feedparser
from fastapi import APIRouter
from pydantic import BaseModel, Field
import structlog

from config.india_calendar import get_market_calendar_context, resolve_sentiment_window_days
from config.settings import get_settings
from data.adapters.india_news_scraper import IndiaNewsScraperClient, StockTwitsClient
from data.adapters.yfinance_client import YFinanceClient
from sentiment.composite_sentiment import get_composite_sentiment
from sentiment.finbert_analyzer import get_finbert_analyzer
from utils.ollama_client import filter_india_news

logger = structlog.get_logger(__name__)
router = APIRouter()


def _fetch_google_finance_rss(ticker: str, max_articles: int = 10) -> list[dict]:
    """Fallback: Google Finance RSS for a ticker. No API key required."""
    clean = ticker.upper().replace(".NS", "").replace(".BO", "")
    urls = [
        f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={clean}.NS&region=IN&lang=en-IN",
        f"https://news.google.com/rss/search?q={clean}+NSE+stock+India&hl=en-IN&gl=IN&ceid=IN:en",
    ]
    articles: list[dict] = []
    now = datetime.now(timezone.utc).isoformat()
    for url in urls:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_articles]:
                title = entry.get("title", "")
                summary = entry.get("summary", entry.get("description", ""))
                if title or summary:
                    articles.append({
                        "source": "google_finance_rss",
                        "title": title,
                        "summary": summary,
                        "url": entry.get("link", ""),
                        "published": entry.get("published", now),
                    })
            if articles:
                logger.info("google_finance_rss.fetched", ticker=clean, count=len(articles), url=url)
                break
        except Exception as exc:
            logger.warning("google_finance_rss.error", ticker=clean, error=str(exc))
    return articles[:max_articles]


def _settings():
    return get_settings()

_CACHE_LOCK = threading.Lock()
_SENTIMENT_CACHE: dict[str, tuple[float, "SentimentResponse"]] = {}
_SOCIAL_VOLUME_HISTORY: dict[str, list[tuple[float, int]]] = {}


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
    institutional_score: float = 0.0
    india_specific_score: float = 0.0
    social_bullish_pct: float = 50.0
    social_post_volume: int = 0
    alpha_vantage_score: float = 0.0
    gdelt_macro_tone: float = 0.0
    earnings_tone: float = 0.0
    sentiment_window_days: int = 3
    high_volume_flag: bool = False
    euphoria_flag: bool = False
    warnings: List[str] = Field(default_factory=list)
    articles: List[ArticleItem]


def _cache_key(
    ticker: str,
    sources: Optional[List[str]],
    window_days: int,
    current_vix: float | None,
    alpha_vantage_enabled: bool,
) -> str:
    source_key = ",".join(sorted(src.lower() for src in (sources or []))) or "*"
    vix_key = "none" if current_vix is None else f"{current_vix:.2f}"
    av_key = "av1" if alpha_vantage_enabled else "av0"
    return f"{ticker.upper()}|{source_key}|{window_days}|{vix_key}|{av_key}"


def _get_cached_response(key: str) -> SentimentResponse | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        cached = _SENTIMENT_CACHE.get(key)
        if cached is None:
            return None
        expires_at, response = cached
        if expires_at <= now:
            _SENTIMENT_CACHE.pop(key, None)
            return None
        return response.model_copy(deep=True)


def _set_cached_response(key: str, response: SentimentResponse) -> SentimentResponse:
    ttl_seconds = _settings().sentiment_cache_ttl_minutes * 60
    with _CACHE_LOCK:
        _SENTIMENT_CACHE[key] = (time.monotonic() + ttl_seconds, response.model_copy(deep=True))
    return response


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
    return parsed >= (datetime.now(timezone.utc) - timedelta(days=max(1, window_days)))


def _normalize_finbert_label(label: str) -> str:
    mapping = {
        "positive": "POSITIVE",
        "negative": "NEGATIVE",
        "neutral": "NEUTRAL",
    }
    return mapping.get(str(label).lower(), "NEUTRAL")


def _article_text(article: dict) -> str:
    title = str(article.get("title", "")).strip()
    summary = str(article.get("summary", "")).strip()
    return ". ".join(part for part in (title, summary) if part)[:600]


def _alpha_vantage_average(articles: list[dict]) -> float:
    rows = [article for article in articles if article.get("source") == "alpha_vantage"]
    if not rows:
        return 0.0
    weighted_sum = 0.0
    total_weight = 0.0
    for row in rows:
        weight = float(row.get("relevance_score", 1.0) or 1.0)
        score = float(row.get("sentiment_score", 0.0) or 0.0)
        weighted_sum += score * weight
        total_weight += weight
    return round(weighted_sum / total_weight, 4) if total_weight else 0.0


def _record_social_volume(ticker: str, volume: int) -> None:
    now = time.time()
    history_days = 7
    with _CACHE_LOCK:
        rows = _SOCIAL_VOLUME_HISTORY.setdefault(ticker.upper(), [])
        rows.append((now, volume))
        cutoff = now - (history_days * 86400)
        _SOCIAL_VOLUME_HISTORY[ticker.upper()] = [(ts, count) for ts, count in rows if ts >= cutoff]


def _social_volume_baseline(ticker: str) -> float:
    with _CACHE_LOCK:
        rows = list(_SOCIAL_VOLUME_HISTORY.get(ticker.upper(), []))
    if not rows:
        return 0.0
    return sum(count for _, count in rows) / len(rows)


def _resolve_high_social_volume(ticker: str, social_post_volume: int) -> bool:
    cfg = _settings()
    baseline = _social_volume_baseline(ticker)
    if baseline <= 0:
        return social_post_volume >= cfg.social_volume_min_baseline * cfg.social_volume_spike_multiple
    threshold = max(
        float(cfg.social_volume_min_baseline),
        baseline * cfg.social_volume_spike_multiple,
    )
    return social_post_volume >= threshold


def build_fallback_sentiment_response(ticker: str, detail: str) -> SentimentResponse:
    return SentimentResponse(
        ticker=ticker,
        composite_score=0.0,
        composite_label="NEUTRAL",
        fear_greed_index=50.0,
        fear_greed_label="NEUTRAL",
        sentiment_window_days=resolve_sentiment_window_days(),
        warnings=[f"LIVE_SENTIMENT_FALLBACK: {detail}"],
        articles=[],
    )


async def build_live_sentiment_response(
    ticker: str,
    sources: Optional[List[str]] = None,
    current_vix: float | None = None,
) -> SentimentResponse:
    calendar_context = get_market_calendar_context()
    window_days = resolve_sentiment_window_days()
    cfg = _settings()
    cache_key = _cache_key(
        ticker,
        sources,
        window_days,
        current_vix,
        alpha_vantage_enabled=bool(cfg.alpha_vantage_api_key),
    )
    cached = _get_cached_response(cache_key)
    if cached is not None:
        return cached

    scraper = IndiaNewsScraperClient()
    stocktwits = StockTwitsClient()
    sentiment_engine = get_composite_sentiment()
    finbert = get_finbert_analyzer()
    yf = YFinanceClient()
    warnings: list[str] = []

    tasks = [
        scraper.get_ticker_news(ticker, max_articles=15, window_days=window_days, include_extras=True),
        stocktwits.get_symbol_messages(ticker),
        scraper.get_moneycontrol_comments(ticker, window_days=window_days, max_items=20),
    ]
    if current_vix is None:
        tasks.append(yf.get_india_vix(period="1mo"))

    results = await asyncio.gather(*tasks, return_exceptions=True)
    news_articles = results[0] if isinstance(results[0], list) else []
    st_messages = results[1] if isinstance(results[1], list) else []
    moneycontrol_items = results[2] if isinstance(results[2], list) else []
    vix_df = results[3] if len(results) > 3 else None

    if isinstance(results[0], Exception):
        warnings.append(f"NEWS_SOURCE_FAILED: {results[0]}")
    if isinstance(results[1], Exception):
        warnings.append(f"STOCKTWITS_FAILED: {results[1]}")
    if isinstance(results[2], Exception):
        warnings.append(f"MONEYCONTROL_FAILED: {results[2]}")
    if not cfg.alpha_vantage_api_key:
        warnings.append("ALPHA_VANTAGE_API_KEY_NOT_CONFIGURED")

    news_articles = filter_india_news(news_articles)
    st_messages = [msg for msg in st_messages if _within_window(msg.get("created_at"), window_days)]
    moneycontrol_items = [item for item in moneycontrol_items if _within_window(item.get("date"), window_days)]

    if sources:
        allowed = {src.lower() for src in sources}
        news_articles = [article for article in news_articles if str(article.get("source", "")).lower() in allowed]
        st_messages = [msg for msg in st_messages if str(msg.get("source", "")).lower() in allowed]
        moneycontrol_items = [item for item in moneycontrol_items if str(item.get("source", "")).lower() in allowed]

    news_texts = [_article_text(article) for article in news_articles if _article_text(article)]
    social_texts = [msg.get("body", "") for msg in st_messages if msg.get("body")]
    social_texts.extend(item.get("text", "") for item in moneycontrol_items if item.get("text"))

    # ── Google Finance RSS fallback when primary scrapers return nothing ──────
    # Common for NSE tickers: India RSS feeds don't always have ticker-specific items
    if not news_texts and not social_texts:
        logger.warning("sentiment.primary_scrapers_empty", ticker=ticker, news_count=len(news_articles), social_count=len(st_messages))
        warnings.append("SCRAPER_RETURNED_EMPTY: Primary scrapers returned no texts — trying Google Finance RSS fallback")
        loop = asyncio.get_event_loop()
        fallback_articles = await loop.run_in_executor(None, _fetch_google_finance_rss, ticker, 10)
        if fallback_articles:
            fallback_texts = [_article_text(a) for a in fallback_articles if _article_text(a)]
            if fallback_texts:
                news_articles = fallback_articles
                news_texts = fallback_texts
                warnings.append(f"GOOGLE_FINANCE_RSS_FALLBACK: Using {len(fallback_texts)} articles from fallback RSS")
                logger.info("sentiment.fallback_rss_used", ticker=ticker, count=len(fallback_texts))

    # If still empty after fallback, return NEUTRAL with explanation
    if not news_texts and not social_texts:
        warnings.append("ALL_SOURCES_EMPTY: All news sources returned no content — returning neutral score")
        response = SentimentResponse(
            ticker=ticker,
            composite_score=0.0,
            composite_label="NEUTRAL",
            fear_greed_index=50.0,
            fear_greed_label="NEUTRAL",
            sentiment_window_days=window_days,
            warnings=warnings,
            articles=[],
        )
        return _set_cached_response(cache_key, response)

    resolved_vix = current_vix
    if resolved_vix is None and not isinstance(vix_df, Exception) and vix_df is not None and not vix_df.empty:
        resolved_vix = float(vix_df["vix"].iloc[-1])

    bullish = sum(1 for msg in st_messages if msg.get("sentiment") == "Bullish")
    bearish = sum(1 for msg in st_messages if msg.get("sentiment") == "Bearish")
    neutral = len(st_messages) - bullish - bearish
    labelled_total = bullish + bearish
    social_bullish_pct = round((bullish / labelled_total) * 100.0, 2) if labelled_total else 50.0
    social_post_volume = len(st_messages) + len(moneycontrol_items)
    high_social_volume = _resolve_high_social_volume(ticker, social_post_volume)
    alpha_vantage_score = _alpha_vantage_average(news_articles)

    composite = await sentiment_engine.analyze(
        ticker=ticker,
        news_texts=news_texts,
        social_texts=social_texts,
        stocktwits_bullish=bullish,
        stocktwits_bearish=bearish,
        stocktwits_neutral=neutral,
        current_vix=resolved_vix,
        is_results_season=bool(calendar_context["is_result_week"]),
        alpha_vantage_score=alpha_vantage_score,
        social_post_volume=social_post_volume,
        social_bullish_pct=social_bullish_pct,
        sentiment_window_days=window_days,
        high_social_volume=high_social_volume,
    )

    scored_articles: List[ArticleItem] = []
    if news_texts:
        finbert_batch = await finbert.analyze_texts(news_texts)
        for article, score_result in zip(news_articles, finbert_batch.results):
            scored_articles.append(
                ArticleItem(
                    source=article.get("source", "news"),
                    headline=article.get("title", ""),
                    sentiment=round(score_result.score, 4),
                    label=_normalize_finbert_label(score_result.label),
                    date=str(article.get("published", "")),
                )
            )

    response = SentimentResponse(
        ticker=ticker,
        composite_score=round(composite.score, 4),
        composite_label=composite.label,
        fear_greed_index=round(composite.fear_greed_index, 2),
        fear_greed_label=composite.fear_greed_label,
        institutional_score=round(composite.institutional_score, 4),
        india_specific_score=round(composite.india_specific_score, 4),
        social_bullish_pct=round(composite.social_bullish_pct, 2),
        social_post_volume=composite.social_post_volume,
        alpha_vantage_score=round(composite.alpha_vantage_score, 4),
        gdelt_macro_tone=round(composite.gdelt_macro_tone, 4),
        earnings_tone=round(composite.earnings_tone, 4),
        sentiment_window_days=composite.sentiment_window_days,
        high_volume_flag=composite.high_volume_flag,
        euphoria_flag=composite.euphoria_flag,
        warnings=warnings,
        articles=scored_articles,
    )
    _record_social_volume(ticker, social_post_volume)
    return _set_cached_response(cache_key, response)


@router.post("", response_model=SentimentResponse)
async def analyze_sentiment(req: SentimentRequest) -> SentimentResponse:
    logger.info("api.sentiment.request", ticker=req.ticker)
    try:
        return await build_live_sentiment_response(req.ticker, req.sources)
    except Exception as exc:
        logger.error("api.sentiment.error", error=str(exc))
        return build_fallback_sentiment_response(req.ticker, str(exc))
