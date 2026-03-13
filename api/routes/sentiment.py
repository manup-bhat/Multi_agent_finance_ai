"""POST /sentiment — Complex multi-model news and social sentiment analysis."""
from fastapi import APIRouter
from pydantic import BaseModel
import structlog
from typing import List, Optional

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

@router.post("", response_model=SentimentResponse)
async def analyze_sentiment(req: SentimentRequest):
    """Run real FinBERT/composite sentiment on fetched macro/news headlines."""
    logger.info("api.sentiment.request", ticker=req.ticker)
    try:
        from sentiment.composite_sentiment import get_composite_sentiment
        from data.adapters.india_news_scraper import IndiaNewsScraperClient
        
        # 1. Fetch real news
        scraper = IndiaNewsScraperClient()
        articles = await scraper.get_ticker_news(req.ticker)
        
        # 2. Run real composite sentiment
        engine = get_composite_sentiment()
        
        # Simple string-list extraction for the models
        news_texts = [a.get("title", "") for a in articles]
        
        if not news_texts:
             return SentimentResponse(
                 ticker=req.ticker,
                 composite_score=0.0,
                 composite_label="NEUTRAL",
                 fear_greed_index=50.0,
                 fear_greed_label="NEUTRAL",
                 articles=[]
             )
        
        # Analyze using engine (runs FinBERT, GoEmotions, etc.)
        result = await engine.analyze(
            ticker=req.ticker,
            news_texts=news_texts,
            social_texts=[], # Optional PRAW hook logic could go here later
            earnings_texts=[]
        )
        
        # Map back to articles structure
        scored_articles = []
        for i, article in enumerate(articles):
             score = result.components.finbert.score # Fallback approximation for individual scores if batch isn't neatly mapped
             # To be safe, try to get specific score if available from module
             try:
                 score = result.components.finbert.batch_scores[i] if hasattr(result.components.finbert, "batch_scores") else result.components.finbert.score
             except Exception:
                 pass
             
             label = "POSITIVE" if score > 0.2 else ("NEGATIVE" if score < -0.2 else "NEUTRAL")
             scored_articles.append(ArticleItem(
                 source=article.get("source", "News"),
                 headline=article.get("title", ""),
                 sentiment=round(score, 2),
                 label=label,
                 date=article.get("published", "")
             ))
             
        # Filter if requested
        if req.sources:
             scored_articles = [a for a in scored_articles if a.source in req.sources]
             
        comp_score = result.composite_score
        comp_label = "BULLISH" if comp_score > 0.2 else ("BEARISH" if comp_score < -0.2 else "NEUTRAL")
        
        return SentimentResponse(
             ticker=req.ticker,
             composite_score=round(comp_score, 2),
             composite_label=comp_label,
             fear_greed_index=round(result.fear_greed_index, 1),
             fear_greed_label=result.fear_greed_label,
             articles=scored_articles
        )
        
    except Exception as e:
        logger.error("api.sentiment.error", error=str(e))
        return SentimentResponse(
            ticker=req.ticker,
            composite_score=0.0,
            composite_label="NEUTRAL",
            fear_greed_index=50.0,
            fear_greed_label="NEUTRAL",
            articles=[ArticleItem(source="System", headline=f"Error analyzing sentiment: {str(e)[:50]}", sentiment=0.0, label="NEUTRAL", date="")]
        )
