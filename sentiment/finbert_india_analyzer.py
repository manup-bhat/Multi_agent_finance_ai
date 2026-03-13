"""
Vansh180/FinBERT-India-v1 — India-Specific Supplementary Sentiment
===================================================================
Validated accuracy: 76.8% on Indian news dataset.

WHY THIS SUPPLEMENTS ProsusAI/finbert (98.9%):
  - ProsusAI/finbert is trained on Western financial data; may misclassify
    India-specific references (SEBI orders, RBI policy tone, FII/DII context,
    Indian corporate governance language, Hinglish mixing).
  - FinBERT-India-v1 is fine-tuned on Moneycontrol, ET Markets, BSE filings.

USAGE PATTERN (from blueprint):
  1. Always run ProsusAI/finbert first (higher accuracy baseline)
  2. Run FinBERT-India-v1 when: India-specific context detected OR
     ProsusAI confidence < 0.65 (uncertainty → need India-localized check)
  3. Fuse: India_score = 0.6 × ProsusAI + 0.4 × FinBERT_India

India-specific text detectors:
  - Moneycontrol / ET Markets / Business India articles
  - RBI MPC minutes, repo rate, CRR changes
  - SEBI circulars, F&O expiry news
  - NSE/BSE corporate actions (rights issue, bonus, demerger in Indian context)
  - FII/DII data announcements
  - Nifty/Sensex/BankNifty specific references

Usage:
    analyzer = get_finbert_india_analyzer()
    result = await analyzer.analyze_with_india_boost(
        texts=["RBI hikes repo rate", ...],
        prosus_scores=[-0.3, ...],  # from finbert_analyzer.py
    )
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)

MODEL_ID = "Vansh180/FinBERT-India-v1"
FALLBACK_MODEL_ID = "ProsusAI/finbert"  # used if FinBERT-India fails to load

# Regex patterns triggering India-specific booster
INDIA_TRIGGER_PATTERNS = [
    r"\bRBI\b", r"\bSEBI\b", r"\bNSE\b", r"\bBSE\b",
    r"\bNifty\b", r"\bSensex\b", r"\bBank\s*Nifty\b", r"\bFinnifty\b",
    r"\bFII\b", r"\bDII\b", r"\bFPI\b",
    r"\brepo\s+rate\b", r"\bCRR\b", r"\bSLR\b",
    r"\brupee\b", r"\bINR\b", r"₹",
    r"\bNIFTY\b", r"\bBhavcopy\b",
    r"\bMPC\b", r"\bmonetary\s+policy\b",
    r"\bcircuit\s+breaker\b", r"\bupper\s+circuit\b", r"\blower\s+circuit\b",
    r"\bF&O\b", r"\bfutures\s+options\b", r"\bexpiry\b",
    r"\bBudget\b", r"\bUnion\s+Budget\b",
    r"\bMoneycontrol\b", r"\bET\s+Markets\b",
    r"\blakh\b", r"\bcrore\b",
]
_INDIA_PATTERN = re.compile(
    "|".join(INDIA_TRIGGER_PATTERNS), re.IGNORECASE
)

LABEL_TO_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral":  0.0,
    "negative": -1.0,
    # FinBERT-India may also return different label names
    "POSITIVE": 1.0,
    "NEUTRAL":  0.0,
    "NEGATIVE": -1.0,
    "LABEL_0": -1.0,   # some HuggingFace fine-tunes use LABEL_N
    "LABEL_1":  0.0,
    "LABEL_2":  1.0,
}

# Fusion weights (from blueprint formulas)
PROSUS_WEIGHT      = 0.60   # ProsusAI is more accurate overall
INDIA_WEIGHT       = 0.40   # FinBERT-India captures Indian context


@dataclass
class IndiaFinBERTResult:
    """Per-text result from FinBERT-India-v1."""
    text: str
    label: str             # "positive" | "neutral" | "negative"
    india_score: float     # [-1.0, +1.0] from this model
    is_india_context: bool # True if India trigger patterns detected
    fused_score: float     # 0.6 × prosus + 0.4 × india (or pure prosus if not India context)
    confidence: float = 0.0


@dataclass
class IndiaFinBERTBatchResult:
    """Aggregated batch result."""
    results: list[IndiaFinBERTResult] = field(default_factory=list)
    composite_score: float = 0.0   # mean fused score
    india_context_count: int = 0   # texts with India-specific language
    model_id: str = MODEL_ID
    fallback_used: bool = False


class FinBERTIndiaAnalyzer:
    """
    Vansh180/FinBERT-India-v1 — supplementary India-specific sentiment.

    Load strategy:
      - Try to load FinBERT-India-v1 first
      - If model not available (e.g. HuggingFace download fails or
        model weights removed), fall back to ProsusAI/finbert itself
        (still better than nothing for Indian text)

    Call analyze_with_india_boost() to get the fused score that combines
    ProsusAI results with India-specific enrichment.
    """

    def __init__(
        self,
        batch_size: int = 16,   # smaller; FinBERT-India is less stable on large batches
        device: str = "auto",
        max_length: int = 512,
    ):
        self.batch_size = batch_size
        self.max_length = max_length
        self._device = device
        self._pipeline = None
        self._load_lock = asyncio.Lock()
        self._loaded = False
        self._fallback_used = False

    # ── India context detection ───────────────────────────────────────────────

    @staticmethod
    def is_india_context(text: str) -> bool:
        """
        Detect if text contains India-specific financial language.
        Returns True if any trigger pattern is found.
        """
        return bool(_INDIA_PATTERN.search(text))

    # ── Model loading ─────────────────────────────────────────────────────────

    def _resolve_device(self) -> int:
        """Return device_id for HuggingFace pipeline (-1 = CPU, 0 = cuda:0)."""
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
        """Attempt to load FinBERT-India-v1; fall back to ProsusAI if needed."""
        import transformers

        device_id = self._resolve_device()

        for model_id in [MODEL_ID, FALLBACK_MODEL_ID]:
            try:
                logger.info("finbert_india.loading", model=model_id, device_id=device_id)
                t0 = time.perf_counter()
                self._pipeline = transformers.pipeline(
                    task="text-classification",
                    model=model_id,
                    tokenizer=model_id,
                    device=device_id,
                    top_k=None,
                    truncation=True,
                    max_length=self.max_length,
                    batch_size=self.batch_size,
                )
                elapsed = time.perf_counter() - t0
                if model_id == FALLBACK_MODEL_ID:
                    self._fallback_used = True
                    logger.warning(
                        "finbert_india.fallback_active",
                        reason="FinBERT-India-v1 not available",
                        using=FALLBACK_MODEL_ID,
                    )
                else:
                    logger.info(
                        "finbert_india.loaded",
                        model=model_id,
                        elapsed_s=round(elapsed, 2),
                    )
                self._loaded = True
                return
            except Exception as e:
                logger.warning(
                    "finbert_india.load_failed",
                    model=model_id,
                    error=str(e),
                )
                continue

        # Both failed — create a trivial dummy that returns neutral
        logger.error("finbert_india.both_models_failed_using_dummy")
        self._pipeline = None
        self._loaded = True

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._load_lock:
            if not self._loaded:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._load_model_sync)

    # ── Inference ─────────────────────────────────────────────────────────────

    def _run_batch_sync(self, texts: list[str]) -> list[list[dict]]:
        if not texts or self._pipeline is None:
            return [[] for _ in texts]
        return self._pipeline(texts)

    def _parse_label_score(self, raw: list[dict]) -> tuple[str, float, float]:
        """
        Return (label, numeric_score, confidence) from top_k=None output.
        Handles both standard labels and LABEL_N format.
        """
        if not raw:
            return "neutral", 0.0, 0.0

        best = max(raw, key=lambda x: x["score"])
        label_raw = best["label"].lower()
        confidence = best["score"]

        # Normalize label
        if "positive" in label_raw or label_raw == "label_2":
            label = "positive"
        elif "negative" in label_raw or label_raw == "label_0":
            label = "negative"
        else:
            label = "neutral"

        numeric = LABEL_TO_SCORE.get(label, 0.0)
        return label, numeric, confidence

    async def analyze_india_texts(
        self,
        texts: list[str],
        min_length: int = 10,
    ) -> list[tuple[str, float, float]]:
        """
        Analyze texts through FinBERT-India-v1.

        Returns:
            list of (label, numeric_score, confidence) tuples
        """
        await self._ensure_loaded()

        filtered = [t.strip()[:900] for t in texts if len(t.strip()) >= min_length]
        if not filtered:
            return [("neutral", 0.0, 0.0)] * len(texts)

        loop = asyncio.get_event_loop()
        all_raws: list[list[dict]] = []
        for i in range(0, len(filtered), self.batch_size):
            batch = filtered[i : i + self.batch_size]
            raw = await loop.run_in_executor(None, self._run_batch_sync, batch)
            all_raws.extend(raw)

        results = []
        for raw_item in all_raws:
            label, score, conf = self._parse_label_score(raw_item)
            results.append((label, score, conf))

        return results

    async def analyze_with_india_boost(
        self,
        texts: list[str],
        prosus_scores: Optional[list[float]] = None,
        min_length: int = 10,
    ) -> IndiaFinBERTBatchResult:
        """
        Main entry point: analyze texts and fuse with ProsusAI scores.

        For texts WITHOUT India context → return prosus_score unchanged.
        For texts WITH India context → fuse: 0.6 × prosus + 0.4 × india.
        If prosus_scores is None → use india score only.

        Args:
            texts: financial news strings
            prosus_scores: pre-computed scores from finbert_analyzer.py [-1, +1]
            min_length: skip texts shorter than this

        Returns:
            IndiaFinBERTBatchResult with fused scores
        """
        await self._ensure_loaded()

        valid_texts = [t.strip() for t in texts if len(t.strip()) >= min_length]
        if not valid_texts:
            return IndiaFinBERTBatchResult()

        # Detect India context per text
        india_flags = [self.is_india_context(t) for t in valid_texts]

        # Only run model on texts with India-specific content (optimization)
        india_texts = [t for t, flag in zip(valid_texts, india_flags) if flag]
        india_raw_results: list[tuple[str, float, float]] = []
        if india_texts:
            india_raw_results = await self.analyze_india_texts(india_texts)

        # Build fused results
        india_idx = 0
        results: list[IndiaFinBERTResult] = []
        india_context_count = 0

        for i, (text, is_india) in enumerate(zip(valid_texts, india_flags)):
            prosus_s = prosus_scores[i] if prosus_scores and i < len(prosus_scores) else 0.0

            if is_india and india_raw_results:
                label, india_s, conf = india_raw_results[india_idx]
                india_idx += 1
                india_context_count += 1

                if prosus_scores is not None:
                    fused = PROSUS_WEIGHT * prosus_s + INDIA_WEIGHT * india_s
                else:
                    fused = india_s
            else:
                label = "neutral"
                india_s = 0.0
                conf = 0.0
                fused = prosus_s

            results.append(
                IndiaFinBERTResult(
                    text=text[:100] + "..." if len(text) > 100 else text,
                    label=label,
                    india_score=india_s,
                    is_india_context=is_india,
                    fused_score=fused,
                    confidence=conf,
                )
            )

        composite = (
            sum(r.fused_score for r in results) / len(results)
            if results else 0.0
        )

        logger.info(
            "finbert_india.analyzed",
            total=len(results),
            india_context=india_context_count,
            composite_fused=round(composite, 4),
            fallback=self._fallback_used,
        )

        return IndiaFinBERTBatchResult(
            results=results,
            composite_score=composite,
            india_context_count=india_context_count,
            model_id=FALLBACK_MODEL_ID if self._fallback_used else MODEL_ID,
            fallback_used=self._fallback_used,
        )

    async def run_calibration_check(self) -> dict:
        """
        Test FinBERT-India-v1 on India-specific phrases.
        Blueprint gate: all phrases should be correctly classified.
        """
        test_cases = [
            ("RBI raised repo rate by 25 bps in the MPC meeting.", "negative"),
            ("NSE circuit breaker triggered as Sensex fell 2000 points.", "negative"),
            ("FII bought ₹8000 crore in Indian equities this week.", "positive"),
            ("SEBI imposed fine on broker for F&O manipulation.", "negative"),
            ("Nifty 50 hit an all-time high of 26,000 today.", "positive"),
        ]
        texts = [t for t, _ in test_cases]
        india_results = await self.analyze_india_texts(texts)

        passed = 0
        details = []
        for (text, expected), (got_label, score, conf) in zip(test_cases, india_results):
            ok = got_label == expected
            if ok:
                passed += 1
            details.append({
                "text": text[:60] + "...",
                "expected": expected,
                "got": got_label,
                "score": round(score, 3),
                "pass": ok,
            })

        return {
            "model": MODEL_ID,
            "fallback_used": self._fallback_used,
            "passed": passed,
            "total": len(test_cases),
            "pass_rate": passed / len(test_cases),
            "details": details,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_finbert_india_analyzer() -> FinBERTIndiaAnalyzer:
    """Global singleton. Not loaded until first inference call."""
    from config.settings import get_settings
    s = get_settings()
    return FinBERTIndiaAnalyzer(
        batch_size=max(8, s.sentiment_batch_size // 2),
        device="auto",
        max_length=512,
    )


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main():
        analyzer = get_finbert_india_analyzer()
        print("=" * 60)
        print("FinBERT-India-v1 — Calibration Check")
        print("=" * 60)

        # Test India context detection
        test_india = "RBI raised repo rate 25 bps, FII bought ₹8000 crore"
        test_global = "The Fed raised interest rates by 25 basis points"
        print(f"\nIndia context: '{test_india[:40]}...' → {analyzer.is_india_context(test_india)}")
        print(f"Global context: '{test_global[:40]}...' → {analyzer.is_india_context(test_global)}")

        result = await analyzer.run_calibration_check()
        print(f"\nPass rate: {result['pass_rate']:.0%} ({result['passed']}/{result['total']})")
        print(f"Fallback used: {result['fallback_used']}")
        for d in result["details"]:
            status = "✓" if d["pass"] else "✗"
            print(f"  {status} [{d['expected']:8s}→{d['got']:8s}] score={d['score']:+.3f}  {d['text']}")

    asyncio.run(_main())
