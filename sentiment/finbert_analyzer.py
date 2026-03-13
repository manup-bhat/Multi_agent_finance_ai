"""
ProsusAI/finbert — Primary Institutional Sentiment Analyzer
===========================================================
Validated accuracy: 98.9% on Financial PhraseBank dataset.
Best for: English financial news, analyst reports, institutional filings,
          Finlight news items, SEBI/RBI press releases.

Architecture:
  - Lazy-loads model on first call (avoids startup delay)
  - Batch inference with configurable batch_size
  - Thread-safe via @lru_cache singleton
  - Returns score in [-1.0, +1.0] with per-text breakdown

Output labels → numeric mapping:
  positive → +1.0
  neutral  →  0.0
  negative → -1.0

Usage:
    analyzer = get_finbert_analyzer()
    score, breakdown = await analyzer.analyze_texts(["FII bought ₹8000 crore"])
    # score ≈ +0.9 (Positive)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

# Lazy import — only pulled in when model is first used
_torch = None
_transformers = None

LABEL_TO_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral":  0.0,
    "negative": -1.0,
}

MODEL_ID = "ProsusAI/finbert"


@dataclass
class FinBERTResult:
    """Per-text result from ProsusAI/finbert."""
    text: str
    label: str             # "positive" | "neutral" | "negative"
    score: float           # [-1.0, +1.0]
    confidence: float      # raw softmax probability of the predicted class
    positive_prob: float = 0.0
    neutral_prob: float  = 0.0
    negative_prob: float = 0.0


@dataclass
class FinBERTBatchResult:
    """Aggregated result for a batch of texts."""
    results: list[FinBERTResult] = field(default_factory=list)
    composite_score: float = 0.0   # weighted average by confidence
    mean_score: float = 0.0        # simple average
    positive_count: int = 0
    neutral_count: int  = 0
    negative_count: int = 0
    total_texts: int    = 0
    label: str = "NEUTRAL"         # "BULLISH" | "BEARISH" | "NEUTRAL"
    model_id: str = MODEL_ID


class FinBERTAnalyzer:
    """
    ProsusAI/finbert analyzer for institutional English financial text.

    Singleton via get_finbert_analyzer() — model loaded once, reused.
    Batch size 32 keeps GPU memory under control.

    Args:
        batch_size: number of texts per inference batch (default 32)
        device: "cuda" | "cpu" | "auto" (default "auto")
        max_length: tokenizer max length (default 512)
    """

    def __init__(
        self,
        batch_size: int = 32,
        device: str = "auto",
        max_length: int = 512,
    ):
        self.batch_size = batch_size
        self.max_length = max_length
        self._pipeline = None
        self._device = device
        self._load_lock = asyncio.Lock()
        self._loaded = False

    # ── Model Loading ─────────────────────────────────────────────────────────

    def _resolve_device(self) -> str:
        """Auto-detect CUDA availability."""
        if self._device != "auto":
            return self._device
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _load_model_sync(self) -> None:
        """Synchronous model load — called in executor to avoid blocking event loop."""
        global _torch, _transformers
        if _torch is None:
            import torch as _torch_mod
            _torch = _torch_mod
        if _transformers is None:
            import transformers as _transformers_mod
            _transformers = _transformers_mod

        device = self._resolve_device()
        device_id = 0 if device == "cuda" else -1

        logger.info("finbert.loading", model=MODEL_ID, device=device)
        t0 = time.perf_counter()

        self._pipeline = _transformers.pipeline(
            task="text-classification",
            model=MODEL_ID,
            tokenizer=MODEL_ID,
            device=device_id,
            top_k=None,          # return all 3 class probabilities
            truncation=True,
            max_length=self.max_length,
            batch_size=self.batch_size,
        )

        elapsed = time.perf_counter() - t0
        logger.info("finbert.loaded", model=MODEL_ID, elapsed_s=round(elapsed, 2))
        self._loaded = True

    async def _ensure_loaded(self) -> None:
        """Ensure model is loaded — thread-safe lazy initialization."""
        if self._loaded:
            return
        async with self._load_lock:
            if not self._loaded:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._load_model_sync)

    # ── Inference ─────────────────────────────────────────────────────────────

    def _run_batch_sync(self, texts: list[str]) -> list[list[dict]]:
        """Run pipeline synchronously — called in executor."""
        if not texts:
            return []
        return self._pipeline(texts)  # returns list[list[dict]] with top_k=None

    def _parse_class_probs(
        self, raw: list[dict]
    ) -> tuple[float, float, float, str, float]:
        """
        Parse the top_k=None output into (positive_p, neutral_p, negative_p, label, confidence).
        """
        prob_map: dict[str, float] = {}
        for item in raw:
            key = item["label"].lower()
            prob_map[key] = item["score"]

        pos_p = prob_map.get("positive", 0.0)
        neu_p = prob_map.get("neutral",  0.0)
        neg_p = prob_map.get("negative", 0.0)

        # Label = class with highest probability
        if pos_p >= neu_p and pos_p >= neg_p:
            label, confidence = "positive", pos_p
        elif neg_p >= pos_p and neg_p >= neu_p:
            label, confidence = "negative", neg_p
        else:
            label, confidence = "neutral", neu_p

        return pos_p, neu_p, neg_p, label, confidence

    async def analyze_texts(
        self,
        texts: list[str],
        min_length: int = 10,
    ) -> FinBERTBatchResult:
        """
        Analyze a batch of financial texts.

        Args:
            texts: list of financial news/article strings
            min_length: skip texts shorter than this (avoids noise from tickers)

        Returns:
            FinBERTBatchResult with per-text results + composite_score [-1, +1]
        """
        await self._ensure_loaded()

        # Filter and truncate
        filtered = [t.strip()[:1000] for t in texts if len(t.strip()) >= min_length]
        if not filtered:
            logger.warning("finbert.empty_batch")
            return FinBERTBatchResult(label="NEUTRAL")

        # Run in batches in executor (blocking transformer inference)
        loop = asyncio.get_event_loop()

        all_raws: list[list[dict]] = []
        for i in range(0, len(filtered), self.batch_size):
            batch = filtered[i : i + self.batch_size]
            raw = await loop.run_in_executor(None, self._run_batch_sync, batch)
            all_raws.extend(raw)

        results: list[FinBERTResult] = []
        for text, raw_item in zip(filtered, all_raws):
            pos_p, neu_p, neg_p, label, confidence = self._parse_class_probs(raw_item)
            numeric_score = LABEL_TO_SCORE[label]
            results.append(
                FinBERTResult(
                    text=text[:120] + "..." if len(text) > 120 else text,
                    label=label,
                    score=numeric_score,
                    confidence=confidence,
                    positive_prob=pos_p,
                    neutral_prob=neu_p,
                    negative_prob=neg_p,
                )
            )

        # Aggregate
        total = len(results)
        pos_count = sum(1 for r in results if r.label == "positive")
        neg_count = sum(1 for r in results if r.label == "negative")
        neu_count = total - pos_count - neg_count

        # Confidence-weighted composite score
        total_conf = sum(r.confidence for r in results)
        if total_conf > 0:
            composite = sum(r.score * r.confidence for r in results) / total_conf
        else:
            composite = sum(r.score for r in results) / total if results else 0.0

        mean_score = sum(r.score for r in results) / total if results else 0.0

        # Directional label (more nuanced than individual)
        if composite > 0.15:
            agg_label = "BULLISH"
        elif composite < -0.15:
            agg_label = "BEARISH"
        else:
            agg_label = "NEUTRAL"

        logger.info(
            "finbert.analyzed",
            total=total,
            positive=pos_count,
            negative=neg_count,
            neutral=neu_count,
            composite_score=round(composite, 4),
            label=agg_label,
        )

        return FinBERTBatchResult(
            results=results,
            composite_score=composite,
            mean_score=mean_score,
            positive_count=pos_count,
            neutral_count=neu_count,
            negative_count=neg_count,
            total_texts=total,
            label=agg_label,
            model_id=MODEL_ID,
        )

    async def analyze_single(self, text: str) -> FinBERTResult:
        """Convenience: analyze a single text string."""
        batch_result = await self.analyze_texts([text])
        if batch_result.results:
            return batch_result.results[0]
        return FinBERTResult(
            text=text,
            label="neutral",
            score=0.0,
            confidence=0.0,
        )

    # ── Calibration Tests ─────────────────────────────────────────────────────

    async def run_calibration_check(self) -> dict:
        """
        Run the 5 validation phrases from the blueprint Phase 4 gate.
        Pass criteria: all phrases correctly classified.
        """
        test_cases = [
            ("SEBI imposed a penalty on the broker for front-running client orders.", "negative"),
            ("FII bought ₹8000 crore worth of equities in a single session.", "positive"),
            ("RBI raised repo rate by 25 bps to control inflation.", "negative"),
            ("The company reported record quarterly profits beating all estimates.", "positive"),
            ("The stock traded flat amid mixed global cues.", "neutral"),
        ]

        texts = [t for t, _ in test_cases]
        result = await self.analyze_texts(texts)

        passed = 0
        details = []
        for res, (text, expected_label) in zip(result.results, test_cases):
            ok = res.label == expected_label
            if ok:
                passed += 1
            details.append({
                "text":     text[:60] + "...",
                "expected": expected_label,
                "got":      res.label,
                "score":    round(res.score, 3),
                "pass":     ok,
            })

        logger.info(
            "finbert.calibration",
            passed=passed,
            total=len(test_cases),
            pass_rate=f"{passed/len(test_cases):.0%}",
        )
        return {
            "model": MODEL_ID,
            "passed": passed,
            "total": len(test_cases),
            "pass_rate": passed / len(test_cases),
            "details": details,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_finbert_analyzer() -> FinBERTAnalyzer:
    """
    Global singleton. Import and call this everywhere.
    Model is NOT loaded until first analyze_texts() call.
    """
    from config.settings import get_settings
    s = get_settings()
    return FinBERTAnalyzer(
        batch_size=s.sentiment_batch_size,
        device="auto",
        max_length=512,
    )


# ── Standalone test ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main():
        analyzer = get_finbert_analyzer()
        print("=" * 60)
        print("ProsusAI/finbert — Calibration Check")
        print("=" * 60)
        result = await analyzer.run_calibration_check()
        print(f"\nPass rate: {result['pass_rate']:.0%} ({result['passed']}/{result['total']})")
        for d in result["details"]:
            status = "✓" if d["pass"] else "✗"
            print(f"  {status} [{d['expected']:8s}→{d['got']:8s}] score={d['score']:+.3f}  {d['text']}")

    asyncio.run(_main())
