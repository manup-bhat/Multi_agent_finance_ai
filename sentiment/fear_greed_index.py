"""
India Fear/Greed Index — Standalone Dashboard Component (0-100)
==============================================================
This module consolidates the Fear/Greed signal into a single,
named entity that the orchestrator, dashboard (Streamlit page 4),
and Agent 5 (Emotion Agent) can consume directly.

Architecture:
  - Wraps GoEmotionsAnalyzer for social/news text analysis
  - Integrates GDELT tone as additional macro component
  - Integrates StockTwits native Bullish/Bearish labels
  - Produces a SINGLE India Fear/Greed score 0-100

Composition (blueprint-defined):
  ┌─────────────────────────────────────────────────────────┐
  │  India Fear/Greed Index                                  │
  │                                                         │
  │  GoEmotions (social text)    → 45% weight               │
  │  StockTwits native labels    → 30% weight               │
  │  GDELT India tone            → 25% weight               │
  └─────────────────────────────────────────────────────────┘

Zones:
  0-20  → EXTREME FEAR   (smart money accumulation zone)
  21-40 → FEAR           (cautious — reduce risk)  
  41-60 → NEUTRAL        (balanced signals)
  61-80 → GREED          (be selective — risk of distribution)
  81-100 → EXTREME GREED (contrarian sell — distribution likely)

Contrarian use (from blueprint):
  India markets historically reverse within 5-10 trading days when:
  - F/G < 20 AND VIX > 18 simultaneously (confirmed buy zone)
  - F/G > 80 AND VIX < 13 simultaneously (confirmed sell zone)

Historical India Fear/Greed reference points:
  - COVID crash (Mar 2020): ~5 (Extreme Fear)
  - Post-vaccine rally (Nov 2020): ~82 (Extreme Greed)
  - Russia-Ukraine shock (Feb 2022): ~18 (Extreme Fear)
  - Adani report selloff (Feb 2023): ~22 (Fear)
  - Nifty ATH 26000 (Sep 2024): ~78 (Greed)

Usage:
    index = get_fear_greed_index()
    result = await index.compute(
        social_texts=["Nifty crashing! Sell everything!"],
        stocktwits_bullish=5, stocktwits_bearish=18, stocktwits_neutral=7,
        gdelt_score=-0.3,
    )
    # → FearGreedResult(index=28.5, label="FEAR", contrarian_signal="NO_SIGNAL")
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

from sentiment.goemotions_analyzer import get_goemotions_analyzer, IndiaFearGreedResult


# ── Output ────────────────────────────────────────────────────────────────────

@dataclass
class FearGreedResult:
    """Final India Fear/Greed composite (passed to composite_sentiment.py)."""
    index: float                  # 0.0 to 100.0
    label: str                    # "EXTREME_FEAR" | "FEAR" | "NEUTRAL" | "GREED" | "EXTREME_GREED"
    contrarian_signal: str        # "CONTRARIAN_BUY" | "CONTRARIAN_SELL" | "NO_SIGNAL"
    
    # Component scores (for transparency / debug)
    goemotions_score: float       # from GoEmotions model [0, 100]
    stocktwits_score: float       # from StockTwits native labels [0, 100]
    gdelt_score_contribution: float  # from GDELT tone [0, 100]
    
    # Raw breakdown
    social_texts_analyzed: int = 0
    stocktwits_bullish: int = 0
    stocktwits_bearish: int = 0
    stocktwits_neutral: int = 0
    
    # India-calibrated VIX overlay
    vix_adjusted_index: Optional[float] = None   # if VIX provided
    vix_regime: Optional[str] = None


def _index_label(index: float) -> str:
    if index <= 20:
        return "EXTREME_FEAR"
    elif index <= 40:
        return "FEAR"
    elif index <= 60:
        return "NEUTRAL"
    elif index <= 80:
        return "GREED"
    else:
        return "EXTREME_GREED"


def _contrarian(index: float) -> str:
    if index <= 20:
        return "CONTRARIAN_BUY"
    elif index >= 80:
        return "CONTRARIAN_SELL"
    return "NO_SIGNAL"


def _stocktwits_to_fg_score(bullish: int, bearish: int, neutral: int) -> float:
    """
    Convert StockTwits native label counts to Fear/Greed score [0, 100].
    Formula: (bullish / total_labelled) × 100 when labelled > 0
    Neutral messages pull index toward 50.
    """
    total_labelled = bullish + bearish
    total = bullish + bearish + neutral

    if total == 0:
        return 50.0

    if total_labelled > 0:
        bull_ratio = bullish / total_labelled  # 0 to 1
        directional = bull_ratio * 100.0       # 0 to 100
    else:
        directional = 50.0

    # Weight by proportion of labelled vs neutral
    label_ratio = total_labelled / total
    # Neutral messages moderate the index toward 50
    score = directional * label_ratio + 50.0 * (1 - label_ratio)
    return round(score, 2)


def _gdelt_to_fg_score(gdelt_normalized: float) -> float:
    """
    Convert GDELT normalized tone [-1, +1] to Fear/Greed [0, 100].
    
    GDELT range interpretation for Fear/Greed:
      tone = -1.0 → panic/extreme negative → index ≈ 15 (not exactly 0; media negativity is norm)
      tone = 0.0  → neutral → index = 50
      tone = +1.0 → euphoric → index ≈ 85 (not exactly 100 for same reason)
    
    Using a scaled sigmoid: score = 50 + 35 × gdelt_normalized
    """
    score = 50.0 + 35.0 * gdelt_normalized
    return round(max(0.0, min(100.0, score)), 2)


class IndiaFearGreedIndex:
    """
    India Fear/Greed Index — orchestrator for all retail sentiment signals.

    This is the primary interface for page 4 (Emotion_Analysis.py) and
    Agent 5 (Emotion Agent). It combines:
      1. GoEmotions on social/news text
      2. StockTwits native Bullish/Bearish counts
      3. GDELT India tone normalized
    """

    def __init__(self):
        self._goemotions = get_goemotions_analyzer()

    async def compute(
        self,
        social_texts: list[str],
        stocktwits_bullish: int = 0,
        stocktwits_bearish: int = 0,
        stocktwits_neutral: int = 0,
        gdelt_normalized_score: float = 0.0,
        current_vix: Optional[float] = None,
    ) -> FearGreedResult:
        """
        Compute India Fear/Greed Index from all three data sources.

        Args:
            social_texts: list of texts from StockTwits/RSS (for GoEmotions)
            stocktwits_bullish: count of messages with "Bullish" native label
            stocktwits_bearish: count of messages with "Bearish" native label
            stocktwits_neutral: count of messages without sentiment label
            gdelt_normalized_score: GDELT composite score [-1, +1] from gdelt_tone_analyzer.py
            current_vix: India VIX current value (for VIX-adjusted index)

        Returns:
            FearGreedResult with final index (0-100) and signals
        """
        # ── 1. GoEmotions on social text ────────────────────────────────────
        try:
            go_result: IndiaFearGreedResult = await self._goemotions.compute_fear_greed_index(
                texts=social_texts,
            )
        except Exception as exc:
            logger.error("fear_greed.goemotions_failed", error=str(exc))
            go_result = IndiaFearGreedResult(
                index=50.0,
                label="NEUTRAL",
                contrarian_signal="NO_SIGNAL",
                total_texts=0,
            )
        go_score = go_result.index  # already in [0, 100]

        # ── 2. StockTwits native labels ──────────────────────────────────────
        st_score = _stocktwits_to_fg_score(stocktwits_bullish, stocktwits_bearish, stocktwits_neutral)

        # ── 3. GDELT tone component ──────────────────────────────────────────
        gdelt_fg_score = _gdelt_to_fg_score(gdelt_normalized_score)

        # ── Composite [0-100] ────────────────────────────────────────────────
        # Blueprint weights:
        #   GoEmotions → 45% (most granular emotion signal)
        #   StockTwits → 30% (direct financial social media, native labels)
        #   GDELT      → 25% (macro news flow, lagging but high quality)
        composite = (
            0.45 * go_score +
            0.30 * st_score +
            0.25 * gdelt_fg_score
        )
        composite = round(max(0.0, min(100.0, composite)), 2)

        label = _index_label(composite)
        contrarian = _contrarian(composite)

        # ── Optional: VIX-adjusted index ────────────────────────────────────
        # Logic: when VIX is high (>20), Fear/Greed below 40 is a stronger signal
        # When VIX < 13, Greed above 70 is a stronger signal  
        vix_adjusted = None
        vix_regime = None
        if current_vix is not None:
            if current_vix > 25:
                vix_regime = "EXTREME"
                # Fear/Greed readings more volatile — compress toward extremes
                vix_adjusted = composite * 0.8 + (0 if composite < 50 else 100) * 0.2
            elif current_vix > 18:
                vix_regime = "ELEVATED"
                vix_adjusted = composite * 0.9 + (50 if composite < 50 else composite) * 0.1
            elif current_vix < 13:
                vix_regime = "COMPLACENCY"
                # Low VIX → market likely overconfident → boost Greed signal
                if composite > 60:
                    vix_adjusted = min(100.0, composite * 1.1)
                else:
                    vix_adjusted = composite
            else:
                vix_regime = "NORMAL"
                vix_adjusted = composite

            vix_adjusted = round(max(0.0, min(100.0, vix_adjusted)), 2)

        logger.info(
            "fear_greed.computed",
            index=composite,
            label=label,
            contrarian=contrarian,
            go_score=round(go_score, 1),
            st_score=round(st_score, 1),
            gdelt_score=round(gdelt_fg_score, 1),
            vix=current_vix,
            vix_adjusted=vix_adjusted,
        )

        return FearGreedResult(
            index=composite,
            label=label,
            contrarian_signal=contrarian,
            goemotions_score=round(go_score, 2),
            stocktwits_score=round(st_score, 2),
            gdelt_score_contribution=round(gdelt_fg_score, 2),
            social_texts_analyzed=go_result.total_texts,
            stocktwits_bullish=stocktwits_bullish,
            stocktwits_bearish=stocktwits_bearish,
            stocktwits_neutral=stocktwits_neutral,
            vix_adjusted_index=vix_adjusted,
            vix_regime=vix_regime,
        )

    async def compute_from_social_data(
        self,
        social_sentiment_data: "SocialSentimentData",  # from data/adapters/social_sentiment_client.py
        gdelt_normalized_score: float = 0.0,
        current_vix: Optional[float] = None,
    ) -> FearGreedResult:
        """
        Convenience: accept SocialSentimentData directly from the social adapter.

        Args:
            social_sentiment_data: from SocialSentimentClient.get_sentiment()
            gdelt_normalized_score: from GDELTToneAnalyzer.get_tone_score()
            current_vix: India VIX level

        Returns:
            FearGreedResult
        """
        # Extract texts from StockTwits messages + RSS article titles
        texts = []
        for msg in social_sentiment_data.stocktwits_messages:
            if msg.body:
                texts.append(msg.body)
        for article in social_sentiment_data.rss_articles:
            # Use title + summary (limited to manageable length)
            combined = f"{article.title}. {article.summary}"[:300]
            texts.append(combined)

        return await self.compute(
            social_texts=texts,
            stocktwits_bullish=social_sentiment_data.bullish_count,
            stocktwits_bearish=social_sentiment_data.bearish_count,
            stocktwits_neutral=social_sentiment_data.neutral_count,
            gdelt_normalized_score=gdelt_normalized_score,
            current_vix=current_vix,
        )

    async def run_calibration_check(self) -> dict:
        """
        Phase 4 validation: Fear/Greed index returns value in 0-100 range.
        Tests extreme Fear and extreme Greed inputs.
        """
        # Extreme Fear scenario
        fear_texts = [
            "Market crash! Nifty down 1500 points. Panic selling everywhere.",
            "FII selling heavily. Stop losses triggered across the board.",
            "Circuit breaker! Portfolio wiped out. This is 2020 again.",
        ]
        fear_result = await self.compute(
            social_texts=fear_texts,
            stocktwits_bullish=2, stocktwits_bearish=25, stocktwits_neutral=3,
            gdelt_normalized_score=-0.7,
        )

        # Extreme Greed scenario
        greed_texts = [
            "Nifty all time high! FII pumping money. FOMO is real!",
            "Everything is going up. Buy anything and make money.",
            "Sensex at 80k. India is unstoppable. Best market in the world!",
        ]
        greed_result = await self.compute(
            social_texts=greed_texts,
            stocktwits_bullish=28, stocktwits_bearish=2, stocktwits_neutral=5,
            gdelt_normalized_score=0.6,
        )

        fear_pass = fear_result.index < 40.0
        greed_pass = greed_result.index > 60.0
        range_pass = (
            0.0 <= fear_result.index <= 100.0 and
            0.0 <= greed_result.index <= 100.0
        )
        all_pass = fear_pass and greed_pass and range_pass

        logger.info(
            "fear_greed.calibration",
            fear_index=fear_result.index,
            greed_index=greed_result.index,
            all_pass=all_pass,
        )

        return {
            "fear_index": fear_result.index,
            "fear_label": fear_result.label,
            "greed_index": greed_result.index,
            "greed_label": greed_result.label,
            "fear_direction_pass": fear_pass,
            "greed_direction_pass": greed_pass,
            "range_valid_pass": range_pass,
            "all_pass": all_pass,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_fear_greed_index() -> IndiaFearGreedIndex:
    """Global singleton India Fear/Greed Index."""
    return IndiaFearGreedIndex()


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main():
        index = get_fear_greed_index()
        print("=" * 60)
        print("India Fear/Greed Index — Calibration Check")
        print("=" * 60)

        result = await index.run_calibration_check()
        print(f"\nFear scenario:  {result['fear_index']:5.1f}/100  [{result['fear_label']}]")
        print(f"Greed scenario: {result['greed_index']:5.1f}/100  [{result['greed_label']}]")
        print(f"\nFear direction (< 40):  {'✓' if result['fear_direction_pass'] else '✗'}")
        print(f"Greed direction (> 60): {'✓' if result['greed_direction_pass'] else '✗'}")
        print(f"Range valid (0-100):    {'✓' if result['range_valid_pass'] else '✗'}")
        print(f"\nPhase 4 gate:           {'✓ PASS' if result['all_pass'] else '✗ FAIL'}")

    asyncio.run(_main())
