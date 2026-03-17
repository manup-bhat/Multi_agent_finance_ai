"""
google/goemotions — India Retail Fear/Greed Index (0-100)
=========================================================
Model: google/goemotions-bert-base (56M params, 27 emotion classes)
Trained on: 58,000 Reddit comments — perfect for social media financial text

WHY GoEmotions for Fear/Greed:
  - Standard FinBERT only gives positive/neutral/negative
  - Fear/Greed requires emotion-level granularity:
      Fear emotions  → Joy(↓), Excitement(↓), Approval(↓), Nervousness(↑), Fear(↑)
      Greed emotions → Desire(↑), Optimism(↑), Admiration(↑), Excitement(↑)
  - GoEmotions was trained on Reddit text — same domain as financial social media

India Data Sources for Fear/Greed:
  1. StockTwits messages (via social_sentiment_client.py — already built)
  2. India RSS feed snippets (Moneycontrol comments, ET Markets headlines)
  3. GDELT article tones (via gdelt_client.py — already built)
  NOTE: Reddit API now requires developer account (see social_sentiment_client.py note)
        Use StockTwits as the primary social signal for this index.

27 GoEmotions → India Fear/Greed Mapping:
  FEAR indicators (push index DOWN toward 0):
    fear, nervousness, grief, sadness, disappointment, anger, disgust,
    annoyance, remorse, embarrassment, confusion
  GREED indicators (push index UP toward 100):
    excitement, joy, optimism, approval, admiration, amusement, desire,
    gratitude, love, pride, relief, curiosity, realization
  NEUTRAL (minimal impact):
    neutral, surprise, caring

Output:
  Fear/Greed Index 0-100:
    0-20  = Extreme Fear    (contrarian BUY signal)
    20-40 = Fear
    40-60 = Neutral
    60-80 = Greed
    80-100 = Extreme Greed  (contrarian SELL signal)

Usage:
    analyzer = get_goemotions_analyzer()
    index = await analyzer.compute_fear_greed_index(texts)
    # → IndiaFearGreedResult(index=72.3, label="GREED", ...)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import structlog

from sentiment.hf_loader import get_transformers_pipeline

logger = structlog.get_logger(__name__)

MODEL_ID = "SamLowe/roberta-base-go_emotions"  # Most widely-used GoEmotions on HuggingFace
# Fallback: google/goemotions-bert-base (requires additional auth in some regions)
MODEL_ID_FALLBACK = "google/goemotions-bert-base"

# ── Emotion → Fear/Greed Classification ────────────────────────────────────────
# Each emotion has a signed weight:
#   Positive weight → contributes to GREED side (higher index)
#   Negative weight → contributes to FEAR side (lower index)
#   0 → neutral, minimal contribution

EMOTION_TO_FEARGREED: dict[str, float] = {
    # GREED-contributing emotions (positive weight)
    "excitement":    +1.0,
    "joy":           +0.9,
    "optimism":      +1.0,
    "approval":      +0.8,
    "admiration":    +0.7,
    "amusement":     +0.4,
    "desire":        +0.9,
    "gratitude":     +0.6,
    "love":          +0.5,
    "pride":         +0.8,
    "relief":        +0.7,
    "curiosity":     +0.3,
    "realization":   +0.2,
    "caring":        +0.2,

    # FEAR-contributing emotions (negative weight)
    "fear":          -1.0,
    "nervousness":   -0.9,
    "grief":         -0.9,
    "sadness":       -0.8,
    "disappointment": -0.8,
    "anger":         -0.7,
    "disgust":       -0.7,
    "annoyance":     -0.5,
    "remorse":       -0.6,
    "embarrassment": -0.5,
    "confusion":     -0.3,

    # Near-neutral
    "neutral":       0.0,
    "surprise":      +0.1,  # slight positive bias (euphoric surprises more common in bull markets)
}

# Fear/Greed index labels
def _index_to_label(index: float) -> str:
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


# Contrarian interpretation
def _contrarian_signal(index: float) -> str:
    if index <= 20:
        return "CONTRARIAN_BUY"     # extreme fear = smart money buy
    elif index >= 80:
        return "CONTRARIAN_SELL"    # extreme greed = distribution top
    return "NO_SIGNAL"


@dataclass
class GoEmotionsResult:
    """Per-text emotion analysis result."""
    text: str
    top_emotion: str
    top_emotion_prob: float
    all_emotions: dict[str, float]   # emotion → probability
    fear_greed_contribution: float   # [-1.0, +1.0] contribution to index


@dataclass
class IndiaFearGreedResult:
    """Aggregated India Fear/Greed Index result."""
    index: float                      # 0.0 to 100.0
    label: str                        # "EXTREME_FEAR" | "FEAR" | "NEUTRAL" | "GREED" | "EXTREME_GREED"
    contrarian_signal: str            # "CONTRARIAN_BUY" | "CONTRARIAN_SELL" | "NO_SIGNAL"
    results: list[GoEmotionsResult] = field(default_factory=list)
    total_texts: int = 0
    dominant_emotions: list[tuple[str, float]] = field(default_factory=list)  # top 5 emotions
    model_id: str = MODEL_ID
    raw_score: float = 0.0           # pre-normalization weighted sum [-1, +1]


class GoEmotionsAnalyzer:
    """
    India Fear/Greed Index computed from GoEmotions emotion classification.

    Singleton via get_goemotions_analyzer().

    The index is computed as:
      1. For each text, classify 27 emotions (probabilities)
      2. Compute emotion_score = Σ (emotion_weight × emotion_prob)
      3. raw_score = mean(emotion_scores across all texts)
      4. Normalize: index = (raw_score + 1) / 2 × 100 → [0, 100]

    Contrarian signals:
      index < 20 → CONTRARIAN_BUY  (as per VIX mean reversion logic)
      index > 80 → CONTRARIAN_SELL (excessive greed = near top)
    """

    def __init__(
        self,
        batch_size: int = 16,
        device: str = "auto",
        max_length: int = 256,     # social media posts are short
        threshold: float = 0.1,    # minimum probability to include emotion
    ):
        self.batch_size = batch_size
        self.max_length = max_length
        self.threshold = threshold
        self._device = device
        self._pipeline = None
        self._load_lock = asyncio.Lock()
        self._loaded = False
        self._model_used = MODEL_ID

    def _resolve_device(self) -> int:
        if self._device == "cpu":
            return -1
        if self._device == "cuda":
            return 0
        try:
            import torch
            return 0 if torch.cuda.is_available() else -1
        except ImportError:
            return -1

    def _load_model_sync(self) -> None:
        device_id = self._resolve_device()
        hf_pipeline = get_transformers_pipeline()
        self._pipeline = None

        for model_id in [MODEL_ID, MODEL_ID_FALLBACK]:
            try:
                logger.info("goemotions.loading", model=model_id, device_id=device_id)
                t0 = time.perf_counter()
                self._pipeline = hf_pipeline(
                    task="text-classification",
                    model=model_id,
                    tokenizer=model_id,
                    device=device_id,
                    top_k=None,       # return all 27/28 emotion probabilities
                    truncation=True,
                    max_length=self.max_length,
                    batch_size=self.batch_size,
                )
                elapsed = time.perf_counter() - t0
                logger.info(
                    "goemotions.loaded",
                    model=model_id,
                    elapsed_s=round(elapsed, 2),
                )
                self._model_used = model_id
                self._loaded = True
                return
            except Exception as e:
                logger.warning("goemotions.load_failed", model=model_id, error=str(e))
                continue

        logger.error("goemotions.all_models_failed")
        self._loaded = True  # Mark loaded to avoid retry loop

    def _reset_and_force_cpu(self) -> None:
        """Clear a bad pipeline state and force a CPU reload for the next attempt."""
        self._pipeline = None
        self._loaded = False
        self._device = "cpu"

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if not self._loaded:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._load_model_sync)

    def _run_batch_sync(self, texts: list[str]) -> list[list[dict]]:
        if not texts or self._pipeline is None:
            return [[] for _ in texts]
        return self._pipeline(texts)

    def _compute_fear_greed_contribution(
        self, emotions: dict[str, float]
    ) -> float:
        """
        Weighted sum of emotion probabilities → [-1.0 FEAR, +1.0 GREED].
        Each emotion contributes: its weight × its probability.
        """
        score = 0.0
        total_weight = 0.0
        for emotion, prob in emotions.items():
            if prob < self.threshold:
                continue
            weight = EMOTION_TO_FEARGREED.get(emotion, 0.0)
            score += weight * prob
            total_weight += abs(weight) * prob

        if total_weight > 0:
            return score / total_weight  # normalized to [-1, +1]
        return 0.0

    async def compute_fear_greed_index(
        self,
        texts: list[str],
        min_length: int = 5,
    ) -> IndiaFearGreedResult:
        """
        Compute India Fear/Greed Index from social/news texts.

        Designed for:
          - StockTwits messages (short, colloquial)
          - India financial RSS headlines
          - GDELT snippet titles
          - Any short financial opinion text

        Args:
            texts: list of social media / news snippets
            min_length: minimum text length to process

        Returns:
            IndiaFearGreedResult with index (0-100), label, contrarian_signal
        """
        await self._ensure_loaded()

        filtered = [
            t.strip()[:500] for t in texts
            if len(t.strip()) >= min_length
        ]
        if not filtered:
            logger.warning("goemotions.empty_input")
            return IndiaFearGreedResult(
                index=50.0,
                label="NEUTRAL",
                contrarian_signal="NO_SIGNAL",
                total_texts=0,
            )

        loop = asyncio.get_event_loop()
        all_raws: list[list[dict]] = []
        for attempt in range(2):
            try:
                all_raws = []
                for i in range(0, len(filtered), self.batch_size):
                    batch = filtered[i : i + self.batch_size]
                    raw = await loop.run_in_executor(None, self._run_batch_sync, batch)
                    all_raws.extend(raw)
                break
            except Exception as exc:
                is_meta_error = "device meta" in str(exc).lower()
                if attempt == 0 and is_meta_error:
                    logger.warning("goemotions.retry_cpu_after_meta_error", error=str(exc))
                    self._reset_and_force_cpu()
                    await self._ensure_loaded()
                    continue

                logger.error("goemotions.inference_failed", error=str(exc))
                return IndiaFearGreedResult(
                    index=50.0,
                    label="NEUTRAL",
                    contrarian_signal="NO_SIGNAL",
                    total_texts=0,
                    model_id=self._model_used,
                )

        # Build per-text results
        results: list[GoEmotionsResult] = []
        emotion_accumulator: dict[str, float] = {}

        for text, raw_item in zip(filtered, all_raws):
            if not raw_item:
                continue

            # Build emotion probability map
            emotions = {
                item["label"].lower(): item["score"]
                for item in raw_item
                if item["score"] >= self.threshold
            }

            # Accumulate for dominant emotion detection
            for emotion, prob in emotions.items():
                emotion_accumulator[emotion] = (
                    emotion_accumulator.get(emotion, 0.0) + prob
                )

            # Top emotion
            top_emotion = max(emotions, key=emotions.get) if emotions else "neutral"
            top_prob = emotions.get(top_emotion, 0.0)

            fg_contribution = self._compute_fear_greed_contribution(emotions)

            results.append(
                GoEmotionsResult(
                    text=text[:80] + "..." if len(text) > 80 else text,
                    top_emotion=top_emotion,
                    top_emotion_prob=top_prob,
                    all_emotions=emotions,
                    fear_greed_contribution=fg_contribution,
                )
            )

        # Aggregate Fear/Greed
        total = len(results)
        if total == 0:
            return IndiaFearGreedResult(
                index=50.0,
                label="NEUTRAL",
                contrarian_signal="NO_SIGNAL",
                total_texts=0,
            )

        raw_score = sum(r.fear_greed_contribution for r in results) / total
        # Normalize from [-1, +1] to [0, 100]
        index = (raw_score + 1.0) / 2.0 * 100.0
        index = max(0.0, min(100.0, index))  # clip to [0, 100]

        label = _index_to_label(index)
        contrarian = _contrarian_signal(index)

        # Top 5 dominant emotions
        dominant_5 = sorted(
            emotion_accumulator.items(), key=lambda x: x[1], reverse=True
        )[:5]
        dominant_normalized = [
            (em, round(prob / total, 4)) for em, prob in dominant_5
        ]

        logger.info(
            "goemotions.index_computed",
            index=round(index, 1),
            label=label,
            contrarian=contrarian,
            total_texts=total,
            top_emotion=dominant_5[0][0] if dominant_5 else "none",
        )

        return IndiaFearGreedResult(
            index=round(index, 2),
            label=label,
            contrarian_signal=contrarian,
            results=results,
            total_texts=total,
            dominant_emotions=dominant_normalized,
            model_id=self._model_used,
            raw_score=raw_score,
        )

    async def run_calibration_check(self) -> dict:
        """
        Phase 4 gate: GoEmotions index returns value in 0-100 range.
        Also validates Fear/Greed direction for known extreme texts.
        """
        fear_texts = [
            "Market crash! Circuit breaker triggered. Sell everything now.",
            "Nifty down 1500 points. Panic selling everywhere.",
            "FII massive selling. Rupee collapsing. This is disaster.",
            "Portfolio completely wiped. I am scared to check my demat.",
            "This market is going to zero. Total bloodbath.",
        ]
        greed_texts = [
            "Nifty at all time high! Amazing rally. Buy everything!",
            "FII pumping money into India. 10x multibagger opportunity.",
            "Sensex crossed 80k! Best time to invest in India ever.",
            "FOMO kicking in. Not investing now is biggest mistake.",
            "Every dip gets bought. Bulls completely in control.",
        ]

        fear_result = await self.compute_fear_greed_index(fear_texts)
        greed_result = await self.compute_fear_greed_index(greed_texts)

        fear_pass = fear_result.index < 40.0
        greed_pass = greed_result.index > 60.0
        range_pass = 0.0 <= fear_result.index <= 100.0 and 0.0 <= greed_result.index <= 100.0

        return {
            "model": self._model_used,
            "fear_index": round(fear_result.index, 1),
            "greed_index": round(greed_result.index, 1),
            "fear_label": fear_result.label,
            "greed_label": greed_result.label,
            "fear_direction_pass": fear_pass,
            "greed_direction_pass": greed_pass,
            "range_valid_pass": range_pass,
            "all_pass": fear_pass and greed_pass and range_pass,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_goemotions_analyzer() -> GoEmotionsAnalyzer:
    from config.settings import get_settings
    s = get_settings()
    return GoEmotionsAnalyzer(
        batch_size=max(8, s.sentiment_batch_size // 2),
        device="auto",
        max_length=256,
        threshold=0.05,   # include lower-probability emotions for better coverage
    )


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main():
        analyzer = get_goemotions_analyzer()
        print("=" * 60)
        print("GoEmotions — India Fear/Greed Index Calibration")
        print("=" * 60)

        result = await analyzer.run_calibration_check()
        print(f"\nFear texts  → Index: {result['fear_index']:5.1f}  Label: {result['fear_label']}")
        print(f"Greed texts → Index: {result['greed_index']:5.1f}  Label: {result['greed_label']}")
        print(f"\nFear direction pass:  {'✓' if result['fear_direction_pass'] else '✗'}")
        print(f"Greed direction pass: {'✓' if result['greed_direction_pass'] else '✗'}")
        print(f"Range valid (0-100):  {'✓' if result['range_valid_pass'] else '✗'}")
        print(f"\nOverall:              {'✓ PASS' if result['all_pass'] else '✗ FAIL'}")
        print(f"Model used:           {result['model']}")

    asyncio.run(_main())
