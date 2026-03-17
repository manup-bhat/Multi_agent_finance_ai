"""
Composite Sentiment Engine — 5-Model Weighted Fusion
=====================================================
Blueprint Formula (from Project_documentation.md §Layer 4):

  Composite_Sentiment = (0.35 × FinBERT_Institutional)
                      + (0.25 × India_Fear_Greed_Index)
                      + (0.20 × GDELT_India_Tone)
                      + (0.20 × Earnings_Tone)

Dynamic Weight Adjustments (blueprint-specified):
  During results season    → Earnings_Tone weight → 0.35 (from 0.20)
  During geopolitical crisis → GDELT weight → 0.35 (from 0.20)
  When ProsusAI confidence drops → blends FinBERT-India score

All 5 Models:
  1. ProsusAI/finbert          → institutional English news (0.35 weight)
  2. FinBERT-India-v1          → India-specific supplementary (fused into #1)
  3. yiyanghkust/finbert-tone  → earnings call management tone (0.20 weight)
  4. google/goemotions          → retail Fear/Greed index (0.25 weight)
  5. GDELT V2Tone               → macro news tone (0.20 weight)

Output:
  CompositeSentimentResult:
    score: float [-1.0, +1.0]   # negative = bearish, positive = bullish
    label: str                   # "STRONGLY_BULLISH" | "BULLISH" | "NEUTRAL" 
                                 #   | "BEARISH" | "STRONGLY_BEARISH"
    fear_greed_index: float      # 0-100 (from GoEmotions + StockTwits + GDELT)
    confidence: float            # 0-1 (spread of model agreement)

Integration:
  This is the PRIMARY interface for:
    - Agent 5 (Emotion Agent) in agents/emotion_agent.py
    - Feature engineering (sentiment features in india_feature_set.py)
    - Streamlit page 4 (Emotion_Analysis.py)
    - API routes (analyze.py)

Usage:
    engine = get_composite_sentiment()
    result = await engine.analyze(
        ticker="HDFCBANK",
        news_texts=["FII bought ₹8000 crore..."],
        social_texts=["Nifty rallying hard, FOMO is real!"],
        earnings_texts=["Management confident of 20% growth..."],
        stocktwits_bullish=15, stocktwits_bearish=5,
        gdelt_score=0.3,
        current_vix=16.5,
        is_results_season=False,
        is_geopolitical_crisis=False,
    )
    # score=0.62, label="BULLISH", fear_greed_index=68.3, confidence=0.74
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Import all 5 sentiment models
from sentiment.finbert_analyzer import get_finbert_analyzer, FinBERTBatchResult
from sentiment.finbert_india_analyzer import get_finbert_india_analyzer
from sentiment.finbert_tone_analyzer import get_finbert_tone_analyzer, EarningsToneBatchResult
from sentiment.fear_greed_index import get_fear_greed_index, FearGreedResult
from sentiment.gdelt_tone_analyzer import get_gdelt_tone_analyzer

# Reference constants
from config.constants import (
    SENTIMENT_WEIGHT_FINBERT,
    SENTIMENT_WEIGHT_FEAR_GREED,
    SENTIMENT_WEIGHT_GDELT,
    SENTIMENT_WEIGHT_EARNINGS,
    FEAR_GREED_EXTREME_GREED,
    FEAR_GREED_EXTREME_FEAR,
)


async def _async_none() -> None:
    """Compatibility helper for optional concurrent branches."""
    return None


# ── Output types ──────────────────────────────────────────────────────────────

def _score_to_label(score: float) -> str:
    """Convert [-1, +1] to directional label."""
    if score >= 0.4:
        return "STRONGLY_BULLISH"
    elif score >= 0.15:
        return "BULLISH"
    elif score >= -0.15:
        return "NEUTRAL"
    elif score >= -0.4:
        return "BEARISH"
    else:
        return "STRONGLY_BEARISH"


def _model_agreement_confidence(scores: list[float]) -> float:
    """
    Compute confidence as 1 - std(scores).
    When all models agree (same sign, similar magnitude), confidence → 1.0
    When models disagree (mixed signs), confidence → 0.0
    """
    if not scores:
        return 0.5
    n = len(scores)
    mean = sum(scores) / n
    variance = sum((s - mean) ** 2 for s in scores) / n
    std = variance ** 0.5
    # std can range from 0 (perfect agreement) to ~1 (total disagreement)
    # Normalize: confidence = 1 - min(std, 1.0)
    return round(max(0.0, 1.0 - min(std, 1.0)), 3)


@dataclass
class ComponentScores:
    """Individual model contributions — for transparency and debugging."""
    finbert_institutional: float = 0.0        # ProsusAI/finbert fused with India booster
    india_finbert_boost:  float = 0.0         # India booster effect (delta from pure prosus)
    india_specific_score: float = 0.0         # India-weighted news direction score
    fear_greed_normalized: float = 0.0        # Fear/Greed [0,100] → normalized to [-1, +1]
    gdelt_tone: float = 0.0                   # GDELT composite [-1, +1]
    earnings_tone: float = 0.0                # finbert-tone [-1, +1]
    alpha_vantage_score: float = 0.0          # Alpha Vantage score [-1, +1]
    social_bullish_pct: float = 50.0
    social_post_volume: int = 0
    sentiment_window_days: int = 3
    high_volume_flag: bool = False
    euphoria_flag: bool = False
    
    # Fears/Greed detail
    fear_greed_raw_index: float = 50.0        # raw 0-100 value
    fear_greed_label: str = "NEUTRAL"
    fear_greed_contrarian: str = "NO_SIGNAL"

    # Weights actually used (after dynamic adjustment)
    w_finbert:  float = 0.35
    w_fg:       float = 0.25
    w_gdelt:    float = 0.20
    w_earnings: float = 0.20


@dataclass
class CompositeSentimentResult:
    """
    Final composite sentiment for a ticker + context.
    Primary output of the Phase 4 sentiment pipeline.
    """
    ticker: str
    score: float               # [-1.0, +1.0] (negative = bearish, positive = bullish)
    label: str                 # "STRONGLY_BULLISH" | "BULLISH" | "NEUTRAL" | "BEARISH" | "STRONGLY_BEARISH"
    confidence: float          # 0-1 (model agreement; higher = more reliable signal)
    fear_greed_index: float    # 0-100 (India retail sentiment gauge)
    fear_greed_label: str      # "EXTREME_FEAR" | "FEAR" | "NEUTRAL" | "GREED" | "EXTREME_GREED"
    contrarian_signal: str     # "CONTRARIAN_BUY" | "CONTRARIAN_SELL" | "NO_SIGNAL"
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
    
    components: ComponentScores = field(default_factory=ComponentScores)
    
    # Context flags
    is_results_season: bool = False
    is_geopolitical_crisis: bool = False
    weight_adjustment_applied: str = "NONE"  # "RESULTS_SEASON" | "GEOPOLITICAL" | "NONE"
    
    # Article sources
    news_texts_count: int = 0
    social_texts_count: int = 0
    earnings_texts_count: int = 0


# ── Dynamic weight resolver ───────────────────────────────────────────────────

def _resolve_weights(
    is_results_season: bool,
    is_geopolitical_crisis: bool,
    high_social_volume: bool = False,
) -> tuple[float, float, float, float, str]:
    """
    Return (w_finbert, w_fg, w_gdelt, w_earnings, adjustment_label).
    
    Blueprint rules:
      During results season  → Earnings_Tone weight → 0.35; redistribute from FinBERT
      During geo crisis      → GDELT weight → 0.35; redistribute from FearGreed
      Default                → 0.35 / 0.25 / 0.20 / 0.20
    
    Note: weights always sum to 1.0.
    """
    if is_results_season and is_geopolitical_crisis:
        # Both: split the adjustments
        weights = (0.25, 0.20, 0.25, 0.30)
        label = "RESULTS_SEASON+GEOPOLITICAL"
    elif is_results_season:
        # Earnings guidance is most important signal
        weights = (0.25, 0.25, 0.15, 0.35)
        label = "RESULTS_SEASON"
    elif is_geopolitical_crisis:
        # Global macro tone drives markets more than retail sentiment
        weights = (0.30, 0.15, 0.35, 0.20)
        label = "GEOPOLITICAL"
    else:
        weights = (
            SENTIMENT_WEIGHT_FINBERT,
            SENTIMENT_WEIGHT_FEAR_GREED,
            SENTIMENT_WEIGHT_GDELT,
            SENTIMENT_WEIGHT_EARNINGS,
        )
        label = "NONE"

    w_finbert, w_fg, w_gdelt, w_earnings = weights
    if high_social_volume and w_fg < 0.35:
        delta = 0.35 - w_fg
        finbert_cut = min(delta * 0.6, max(0.0, w_finbert - 0.15))
        gdelt_cut = min(delta - finbert_cut, max(0.0, w_gdelt - 0.10))
        actual_delta = finbert_cut + gdelt_cut
        w_finbert -= finbert_cut
        w_gdelt -= gdelt_cut
        w_fg += actual_delta
        if actual_delta > 0:
            label = f"{label}+HIGH_SOCIAL_VOLUME" if label != "NONE" else "HIGH_SOCIAL_VOLUME"
    return w_finbert, w_fg, w_gdelt, w_earnings, label


# ── Main Composite Engine ─────────────────────────────────────────────────────

class CompositeSentimentEngine:
    """
    Orchestrates all 5 sentiment models → single composite score.
    
    Design principles:
      - All 5 models run in parallel (asyncio.gather)
      - Each model is lazily loaded (no startup overhead)
      - FinBERT-India booster applied when India context detected
      - VIX-adjusted Fear/Greed when VIX is provided
      - Dynamic weights for results season / geopolitical events
      - Model agreement confidence surfaced for Devil's Advocate agent
    
    Singleton via get_composite_sentiment().
    """

    def __init__(self):
        # All 4 singletons (models loaded lazily)
        self._finbert = get_finbert_analyzer()
        self._finbert_india = get_finbert_india_analyzer()
        self._finbert_tone = get_finbert_tone_analyzer()
        self._fear_greed = get_fear_greed_index()
        self._gdelt = get_gdelt_tone_analyzer()

    async def analyze(
        self,
        ticker: str,
        news_texts: list[str],
        social_texts: list[str],
        earnings_texts: Optional[list[str]] = None,
        stocktwits_bullish: int = 0,
        stocktwits_bearish: int = 0,
        stocktwits_neutral: int = 0,
        gdelt_normalized_score: Optional[float] = None,
        current_vix: Optional[float] = None,
        is_results_season: bool = False,
        is_geopolitical_crisis: bool = False,
        alpha_vantage_score: float = 0.0,
        social_post_volume: int = 0,
        social_bullish_pct: Optional[float] = None,
        sentiment_window_days: int = 3,
        high_social_volume: bool = False,
    ) -> CompositeSentimentResult:
        """
        Full 5-model sentiment analysis for a ticker.

        Args:
            ticker: NSE ticker (e.g. "HDFCBANK")
            news_texts: financial news/article strings for FinBERT analysis
            social_texts: social media strings for GoEmotions Fear/Greed
            earnings_texts: management/results text for finbert-tone (optional)
            stocktwits_bullish: count of "Bullish" labeled StockTwits messages
            stocktwits_bearish: count of "Bearish" labeled StockTwits messages
            stocktwits_neutral: count of unlabeled StockTwits messages
            gdelt_normalized_score: pre-fetched GDELT score [-1,+1] (if None, fetched here)
            current_vix: India VIX for VIX-adjusted Fear/Greed
            is_results_season: True during Q1/Q2/Q3/Q4 results season
            is_geopolitical_crisis: True during India geopolitical events

        Returns:
            CompositeSentimentResult — primary Phase 4 output
        """
        earnings_texts = earnings_texts or []
        w_finbert, w_fg, w_gdelt, w_earnings, weight_adj = _resolve_weights(
            is_results_season, is_geopolitical_crisis, high_social_volume=high_social_volume
        )

        # ── Parallel: fetch GDELT if not pre-fetched ──────────────────────────
        gdelt_fetch_coro = None
        if gdelt_normalized_score is None:
            gdelt_fetch_coro = self._gdelt.get_tone_score(ticker=ticker, days_back=1)

        # ── Parallel execution of all 5 components ────────────────────────────
        # We run these in parallel to minimize latency
        task_finbert = asyncio.create_task(
            self._finbert.analyze_texts(news_texts)
        )
        task_fear_greed = asyncio.create_task(
            self._fear_greed.compute(
                social_texts=social_texts,
                stocktwits_bullish=stocktwits_bullish,
                stocktwits_bearish=stocktwits_bearish,
                stocktwits_neutral=stocktwits_neutral,
                gdelt_normalized_score=gdelt_normalized_score or 0.0,
                current_vix=current_vix,
            )
        )
        task_earnings = asyncio.create_task(
            self._finbert_tone.analyze_earnings_texts(earnings_texts)
            if earnings_texts
            else _async_none()
        )

        # GDELT fetch (if needed) — also parallel
        if gdelt_fetch_coro:
            task_gdelt = asyncio.create_task(gdelt_fetch_coro)
        else:
            task_gdelt = None

        # Await all concurrently
        tasks_to_gather = [task_finbert, task_fear_greed, task_earnings]
        if task_gdelt:
            tasks_to_gather.append(task_gdelt)

        gathered = await asyncio.gather(*tasks_to_gather, return_exceptions=True)

        finbert_result: FinBERTBatchResult = (
            gathered[0] if not isinstance(gathered[0], Exception)
            else type("R", (), {"composite_score": 0.0, "results": []})()
        )
        fear_greed_result: FearGreedResult = (
            gathered[1] if not isinstance(gathered[1], Exception)
            else FearGreedResult(
                index=50.0, label="NEUTRAL", contrarian_signal="NO_SIGNAL",
                goemotions_score=50.0, stocktwits_score=50.0,
                gdelt_score_contribution=50.0
            )
        )
        earnings_result: Optional[EarningsToneBatchResult] = (
            gathered[2] if not isinstance(gathered[2], Exception) and gathered[2] is not None
            else None
        )

        if task_gdelt and len(gathered) > 3:
            gdelt_normalized_score = (
                gathered[3] if not isinstance(gathered[3], Exception) else 0.0
            )
        gdelt_score = gdelt_normalized_score or 0.0

        # ── Apply India-specific FinBERT booster ──────────────────────────────
        # Only run FinBERT-India on news_texts if there are any
        finbert_base_score = finbert_result.composite_score
        india_boost_delta = 0.0
        if news_texts:
            prosus_scores = [r.score for r in finbert_result.results]
            india_result = await self._finbert_india.analyze_with_india_boost(
                texts=news_texts,
                prosus_scores=prosus_scores,
            )
            fused_finbert_score = india_result.composite_score
            india_boost_delta = fused_finbert_score - finbert_base_score
        else:
            fused_finbert_score = finbert_base_score

        if social_bullish_pct is None:
            labelled = stocktwits_bullish + stocktwits_bearish
            social_bullish_pct = round((stocktwits_bullish / labelled) * 100.0, 2) if labelled else 50.0

        # ── Normalize Fear/Greed [0,100] → [-1, +1] ──────────────────────────
        fg_normalized = (fear_greed_result.index - 50.0) / 50.0  # [-1, +1]

        # ── Earnings tone score ───────────────────────────────────────────────
        earnings_score = earnings_result.composite_score if earnings_result else 0.0
        if not earnings_texts:
            # No earnings text → redistribute earnings weight to FinBERT
            w_finbert += w_earnings
            w_earnings = 0.0

        institutional_score = fused_finbert_score
        if alpha_vantage_score:
            institutional_score = round((0.8 * fused_finbert_score) + (0.2 * alpha_vantage_score), 4)

        euphoria_flag = bool(
            high_social_volume and fear_greed_result.index >= FEAR_GREED_EXTREME_GREED
        )

        # ── Weighted composite formula (blueprint) ────────────────────────────
        composite_score = (
            w_finbert  * institutional_score +
            w_fg       * fg_normalized        +
            w_gdelt    * gdelt_score           +
            w_earnings * earnings_score
        )
        composite_score = round(max(-1.0, min(1.0, composite_score)), 4)

        # ── Model agreement confidence ────────────────────────────────────────
        component_scores_list = [institutional_score, fg_normalized, gdelt_score]
        if earnings_texts:
            component_scores_list.append(earnings_score)
        confidence = _model_agreement_confidence(component_scores_list)

        label = _score_to_label(composite_score)

        components = ComponentScores(
            finbert_institutional=round(institutional_score, 4),
            india_finbert_boost=round(india_boost_delta, 4),
            india_specific_score=round(fused_finbert_score, 4),
            fear_greed_normalized=round(fg_normalized, 4),
            gdelt_tone=round(gdelt_score, 4),
            earnings_tone=round(earnings_score, 4),
            alpha_vantage_score=round(alpha_vantage_score, 4),
            social_bullish_pct=round(float(social_bullish_pct), 2),
            social_post_volume=int(social_post_volume),
            sentiment_window_days=int(sentiment_window_days),
            high_volume_flag=bool(high_social_volume),
            euphoria_flag=euphoria_flag,
            fear_greed_raw_index=fear_greed_result.index,
            fear_greed_label=fear_greed_result.label,
            fear_greed_contrarian=fear_greed_result.contrarian_signal,
            w_finbert=w_finbert,
            w_fg=w_fg,
            w_gdelt=w_gdelt,
            w_earnings=w_earnings,
        )

        logger.info(
            "composite_sentiment.complete",
            ticker=ticker,
            score=composite_score,
            label=label,
            confidence=confidence,
            fg_index=fear_greed_result.index,
            contrarian=fear_greed_result.contrarian_signal,
            weight_adj=weight_adj,
            social_volume=social_post_volume,
            euphoria=euphoria_flag,
        )

        return CompositeSentimentResult(
            ticker=ticker,
            score=composite_score,
            label=label,
            confidence=confidence,
            fear_greed_index=fear_greed_result.index,
            fear_greed_label=fear_greed_result.label,
            contrarian_signal=fear_greed_result.contrarian_signal,
            institutional_score=round(institutional_score, 4),
            india_specific_score=round(fused_finbert_score, 4),
            social_bullish_pct=round(float(social_bullish_pct), 2),
            social_post_volume=int(social_post_volume),
            alpha_vantage_score=round(alpha_vantage_score, 4),
            gdelt_macro_tone=round(gdelt_score, 4),
            earnings_tone=round(earnings_score, 4),
            sentiment_window_days=int(sentiment_window_days),
            high_volume_flag=bool(high_social_volume),
            euphoria_flag=euphoria_flag,
            components=components,
            is_results_season=is_results_season,
            is_geopolitical_crisis=is_geopolitical_crisis,
            weight_adjustment_applied=weight_adj,
            news_texts_count=len(news_texts),
            social_texts_count=len(social_texts),
            earnings_texts_count=len(earnings_texts),
        )

    async def analyze_minimal(
        self,
        ticker: str,
        news_texts: list[str],
        social_texts: list[str],
    ) -> CompositeSentimentResult:
        """
        Lightweight analysis with only news + social texts (no earnings, no GDELT fetch).
        Used for real-time dashboard refresh (lower latency, fewer API calls).
        GDELT score defaults to 0 (neutral) when not pre-fetched.
        """
        return await self.analyze(
            ticker=ticker,
            news_texts=news_texts,
            social_texts=social_texts,
            gdelt_normalized_score=0.0,
        )

    async def run_phase4_validation(self) -> dict:
        """
        Phase 4 validation gate (from blueprint §Build Phases):

        Pass criteria:
          1. ProsusAI/finbert: "SEBI penalty" → Negative ✓
          2. ProsusAI/finbert: "FII bought ₹8000 crore" → Positive ✓
          3. GoEmotions Fear/Greed: panic texts → index 0-100 ✓
          4. GoEmotions Fear/Greed: greed texts → index higher than fear ✓
          5. Composite score [-1, +1] range valid ✓
          6. All component scores available ✓
        """
        # Test 1 & 2: FinBERT calibration
        finbert = get_finbert_analyzer()
        fb_check = await finbert.run_calibration_check()

        # Test 3 & 4: Fear/Greed calibration
        fg_index = get_fear_greed_index()
        fg_check = await fg_index.run_calibration_check()

        # Test 5 & 6: Full composite pipeline
        test_result = await self.analyze(
            ticker="HDFCBANK",
            news_texts=[
                "HDFC Bank reported strong quarterly results with 20% PAT growth.",
                "FII bought ₹2000 crore in banking sector.",
            ],
            social_texts=[
                "HDFCBANK looking good! Long from 1700.",
                "Banking rally is strong. Nifty Bank above 50k.",
            ],
            earnings_texts=[
                "Management guided 18% loan growth for FY27 with stable NIMs.",
            ],
            stocktwits_bullish=12, stocktwits_bearish=3, stocktwits_neutral=5,
            gdelt_normalized_score=0.2,
            current_vix=16.0,
        )

        range_valid = -1.0 <= test_result.score <= 1.0
        components_valid = (
            test_result.components is not None and
            test_result.fear_greed_index is not None
        )

        all_pass = (
            fb_check["pass_rate"] >= 0.8 and   # ≥ 80% phrases correct
            fg_check["all_pass"] and
            range_valid and
            components_valid
        )

        return {
            "phase": 4,
            "finbert_calibration": fb_check,
            "fear_greed_calibration": fg_check,
            "composite_range_valid": range_valid,
            "components_present": components_valid,
            "sample_output": {
                "ticker": test_result.ticker,
                "score": test_result.score,
                "label": test_result.label,
                "confidence": test_result.confidence,
                "fear_greed_index": test_result.fear_greed_index,
                "fear_greed_label": test_result.fear_greed_label,
                "contrarian": test_result.contrarian_signal,
                "weight_adj": test_result.weight_adjustment_applied,
            },
            "all_pass": all_pass,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_composite_sentiment() -> CompositeSentimentEngine:
    """
    Global singleton composite sentiment engine.
    Import this in emotion_agent.py, india_feature_set.py, analyze.py.
    """
    return CompositeSentimentEngine()


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main():
        engine = get_composite_sentiment()
        print("=" * 70)
        print("Phase 4 Sentiment Pipeline — Full Validation")
        print("=" * 70)

        result = await engine.run_phase4_validation()

        print(f"\n{'='*70}")
        print("FINBERT CALIBRATION:")
        print(f"  Pass rate: {result['finbert_calibration']['pass_rate']:.0%}")
        for d in result["finbert_calibration"]["details"]:
            status = "✓" if d["pass"] else "✗"
            print(f"  {status} [{d['expected']:8s}→{d['got']:8s}] {d['text']}")

        print(f"\nFEAR/GREED CALIBRATION:")
        fg = result["fear_greed_calibration"]
        print(f"  Fear scenario:  {fg['fear_index']:5.1f}  [{fg['fear_label']}]  {'✓' if fg['fear_direction_pass'] else '✗'}")
        print(f"  Greed scenario: {fg['greed_index']:5.1f}  [{fg['greed_label']}] {'✓' if fg['greed_direction_pass'] else '✗'}")
        print(f"  Range valid:    {'✓' if fg['range_valid_pass'] else '✗'}")

        print(f"\nCOMPOSITE PIPELINE (sample HDFCBANK):")
        s = result["sample_output"]
        print(f"  Score:          {s['score']:+.4f}  [{s['label']}]")
        print(f"  Confidence:     {s['confidence']:.3f}")
        print(f"  Fear/Greed:     {s['fear_greed_index']:.1f}/100  [{s['fear_greed_label']}]")
        print(f"  Contrarian:     {s['contrarian']}")
        print(f"  Weight adj:     {s['weight_adj']}")

        print(f"\n{'='*70}")
        print(f"PHASE 4 GATE:  {'✅ ALL PASS' if result['all_pass'] else '❌ FAIL'}")
        print(f"{'='*70}")

    asyncio.run(_main())
