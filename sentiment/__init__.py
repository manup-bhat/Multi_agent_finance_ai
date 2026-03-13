"""
Sentiment Pipeline — Phase 4
============================
5-model Multi-Layer Sentiment for India Financial Markets.

Public API (singletons):
    from sentiment.composite_sentiment import get_composite_sentiment
    from sentiment.fear_greed_index import get_fear_greed_index
    from sentiment.finbert_analyzer import get_finbert_analyzer
    from sentiment.finbert_india_analyzer import get_finbert_india_analyzer
    from sentiment.finbert_tone_analyzer import get_finbert_tone_analyzer
    from sentiment.goemotions_analyzer import get_goemotions_analyzer
    from sentiment.gdelt_tone_analyzer import get_gdelt_tone_analyzer

Primary entry point for agents:
    engine = get_composite_sentiment()
    result = await engine.analyze(ticker, news_texts, social_texts, ...)

Blueprint formula (constants.py):
    Composite = 0.35 × FinBERT_Institutional
              + 0.25 × India_Fear_Greed_Index
              + 0.20 × GDELT_India_Tone
              + 0.20 × Earnings_Tone
    (Dynamic: during results season → Earnings weight → 0.35)
    (Dynamic: during geopolitical crisis → GDELT weight → 0.35)

Models:
    1. ProsusAI/finbert           → 98.9% accuracy (Financial PhraseBank)
    2. Vansh180/FinBERT-India-v1  → 76.8% accuracy (Indian news dataset)
    3. yiyanghkust/finbert-tone   → earnings call management confidence
    4. SamLowe/roberta-base-go_emotions  → 27-emotion Fear/Greed mapping
    5. GDELT V2Tone               → no-key India macro news tone
"""

from sentiment.composite_sentiment import (
    CompositeSentimentEngine,
    CompositeSentimentResult,
    ComponentScores,
    get_composite_sentiment,
)
from sentiment.fear_greed_index import (
    IndiaFearGreedIndex,
    FearGreedResult,
    get_fear_greed_index,
)
from sentiment.finbert_analyzer import (
    FinBERTAnalyzer,
    FinBERTBatchResult,
    FinBERTResult,
    get_finbert_analyzer,
)
from sentiment.finbert_india_analyzer import (
    FinBERTIndiaAnalyzer,
    IndiaFinBERTBatchResult,
    IndiaFinBERTResult,
    get_finbert_india_analyzer,
)
from sentiment.finbert_tone_analyzer import (
    FinBERTToneAnalyzer,
    EarningsToneBatchResult,
    EarningsToneResult,
    get_finbert_tone_analyzer,
)
from sentiment.goemotions_analyzer import (
    GoEmotionsAnalyzer,
    IndiaFearGreedResult,
    GoEmotionsResult,
    get_goemotions_analyzer,
)
from sentiment.gdelt_tone_analyzer import (
    GDELTToneAnalyzer,
    GDELTToneResult,
    GDELTIndiaResult,
    get_gdelt_tone_analyzer,
)

__all__ = [
    # Primary interface
    "get_composite_sentiment",
    "CompositeSentimentEngine",
    "CompositeSentimentResult",
    "ComponentScores",
    # Fear/Greed
    "get_fear_greed_index",
    "IndiaFearGreedIndex",
    "FearGreedResult",
    # FinBERT models
    "get_finbert_analyzer",
    "FinBERTAnalyzer",
    "FinBERTBatchResult",
    "FinBERTResult",
    "get_finbert_india_analyzer",
    "FinBERTIndiaAnalyzer",
    "IndiaFinBERTBatchResult",
    "IndiaFinBERTResult",
    "get_finbert_tone_analyzer",
    "FinBERTToneAnalyzer",
    "EarningsToneBatchResult",
    "EarningsToneResult",
    # GoEmotions
    "get_goemotions_analyzer",
    "GoEmotionsAnalyzer",
    "IndiaFearGreedResult",
    "GoEmotionsResult",
    # GDELT
    "get_gdelt_tone_analyzer",
    "GDELTToneAnalyzer",
    "GDELTToneResult",
    "GDELTIndiaResult",
]
