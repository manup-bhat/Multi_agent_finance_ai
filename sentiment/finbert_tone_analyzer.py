"""
yiyanghkust/finbert-tone — Earnings Call & Management Tone Analyzer
====================================================================
Purpose: Analyze management confidence from earnings call transcripts,
         quarterly results announcements, and guidance statements.

Why a separate model from ProsusAI/finbert:
  - finbert-tone is fine-tuned specifically for forward-looking management
    language: guidance, outlook, expectations  
  - Better at detecting management hedging, over-optimism, caution
  - The 3 output labels map to distinct management signals:
      positive → management confidence / bullish guidance
      neutral  → measured/hedged language
      negative → management caution / profit warning / weak guidance

India-specific earnings context:
  - NSE/BSE quarterly results season (Q1: Jul-Aug, Q2: Oct-Nov,
    Q3: Jan-Feb, Q4: Apr-May)
  - Analyst concall transcripts (uploaded to NSE within 24 hours of results)
  - Management commentary on RBI policy impact, INR exposure, crude cost
  - Promoter pledge disclosures, related-party transaction notes

Usage:
    analyzer = get_finbert_tone_analyzer()
    result = await analyzer.analyze_earnings_texts(
        ["Management remains confident of 20% revenue growth in FY27."]
    )
    # → EarningsToneResult(label="positive", management_confidence=0.85, ...)
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional

import structlog

from sentiment.hf_loader import get_transformers_pipeline

logger = structlog.get_logger(__name__)

MODEL_ID = "yiyanghkust/finbert-tone"

LABEL_TO_SCORE: dict[str, float] = {
    "positive": 1.0,
    "neutral":  0.0,
    "negative": -1.0,
}

# India results season detection patterns
EARNINGS_PATTERNS = [
    r"\bquarterly\s+results?\b", r"\bQ[1-4]\s*(FY)?\d{2,4}\b",
    r"\bearnings?\b", r"\brevenue\b", r"\bPAT\b", r"\bEBITDA\b",
    r"\bguidance\b", r"\boutlook\b", r"\bmanagement\b",
    r"\bconcall\b", r"\banalyst\s+call\b",
    r"\bnet\s+profit\b", r"\boperating\s+profit\b",
    r"\bmargin\s+expansion\b", r"\bmargin\s+compression\b",
    r"\bFY2[0-9]\b", r"\bH[12]\s*FY\b",
    r"\bgrowth\s+guidance\b", r"\bprofit\s+(warning|upgrade|downgrade)\b",
]
_EARNINGS_PATTERN = re.compile(
    "|".join(EARNINGS_PATTERNS), re.IGNORECASE
)


@dataclass
class EarningsToneResult:
    """Per-text result from finbert-tone."""
    text: str
    label: str                      # "positive" | "neutral" | "negative"
    score: float                    # [-1.0, +1.0]
    management_confidence: float    # 0.0 to 1.0 (positive probability)
    caution_signal: float           # 0.0 to 1.0 (negative probability)
    is_earnings_context: bool
    positive_prob: float = 0.0
    neutral_prob: float  = 0.0
    negative_prob: float = 0.0


@dataclass
class EarningsToneBatchResult:
    """Aggregated result for a batch of earnings texts."""
    results: list[EarningsToneResult] = field(default_factory=list)
    composite_score: float = 0.0        # confidence-weighted average
    mean_management_confidence: float = 0.0
    earnings_context_count: int = 0
    bullish_guidance_count: int = 0
    cautious_guidance_count: int = 0
    results_season_signal: str = "NEUTRAL"   # "BULLISH_GUIDANCE" | "CAUTIOUS" | "NEUTRAL"
    model_id: str = MODEL_ID


class FinBERTToneAnalyzer:
    """
    yiyanghkust/finbert-tone for earnings call transcript analysis.

    Singleton via get_finbert_tone_analyzer().
    Optimized for:
      - Management guidance text from Q results concalls
      - Annual report language
      - Earnings call transcripts
      - Investor day presentations
    """

    def __init__(
        self,
        batch_size: int = 16,
        device: str = "auto",
        max_length: int = 512,
    ):
        self.batch_size = batch_size
        self.max_length = max_length
        self._device = device
        self._pipeline = None
        self._load_lock = asyncio.Lock()
        self._loaded = False

    # ── Earnings context detection ────────────────────────────────────────────

    @staticmethod
    def is_earnings_context(text: str) -> bool:
        """Detect if text is from an earnings-related source."""
        return bool(_EARNINGS_PATTERN.search(text))

    # ── Model loading ─────────────────────────────────────────────────────────

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
        logger.info("finbert_tone.loading", model=MODEL_ID, device_id=device_id)
        t0 = time.perf_counter()

        self._pipeline = hf_pipeline(
            task="text-classification",
            model=MODEL_ID,
            tokenizer=MODEL_ID,
            device=device_id,
            top_k=None,
            truncation=True,
            max_length=self.max_length,
            batch_size=self.batch_size,
        )
        elapsed = time.perf_counter() - t0
        logger.info("finbert_tone.loaded", elapsed_s=round(elapsed, 2))
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

    def _parse_class_probs(
        self, raw: list[dict]
    ) -> tuple[float, float, float, str, float]:
        """Parse top_k=None output into (pos_p, neu_p, neg_p, label, confidence)."""
        prob_map = {
            item["label"].lower(): item["score"] for item in raw
        }
        pos_p = prob_map.get("positive", 0.0)
        neu_p = prob_map.get("neutral",  0.0)
        neg_p = prob_map.get("negative", 0.0)

        if pos_p >= neu_p and pos_p >= neg_p:
            label, confidence = "positive", pos_p
        elif neg_p >= pos_p and neg_p >= neu_p:
            label, confidence = "negative", neg_p
        else:
            label, confidence = "neutral", neu_p

        return pos_p, neu_p, neg_p, label, confidence

    async def analyze_earnings_texts(
        self,
        texts: list[str],
        min_length: int = 15,
    ) -> EarningsToneBatchResult:
        """
        Analyze earnings/management tone from a batch of texts.

        Best results with:
          - Full sentences from management: "We remain confident of achieving..."
          - Guidance language: "We expect revenue to grow by 18-20% in FY27"
          - Risk disclosures: "We are cautious about the near-term demand environment"

        Args:
            texts: management/earnings text strings
            min_length: minimum text length to analyze

        Returns:
            EarningsToneBatchResult with per-text results + aggregate signal
        """
        await self._ensure_loaded()

        filtered = [t.strip()[:900] for t in texts if len(t.strip()) >= min_length]
        if not filtered:
            return EarningsToneBatchResult()

        loop = asyncio.get_event_loop()
        all_raws: list[list[dict]] = []
        for i in range(0, len(filtered), self.batch_size):
            batch = filtered[i : i + self.batch_size]
            raw = await loop.run_in_executor(None, self._run_batch_sync, batch)
            all_raws.extend(raw)

        results: list[EarningsToneResult] = []
        earnings_ctx_count = 0
        bullish_count = 0
        cautious_count = 0

        for text, raw_item in zip(filtered, all_raws):
            pos_p, neu_p, neg_p, label, conf = self._parse_class_probs(raw_item)
            numeric = LABEL_TO_SCORE[label]
            is_earn = self.is_earnings_context(text)

            if is_earn:
                earnings_ctx_count += 1
            if label == "positive":
                bullish_count += 1
            elif label == "negative":
                cautious_count += 1

            results.append(
                EarningsToneResult(
                    text=text[:120] + "..." if len(text) > 120 else text,
                    label=label,
                    score=numeric,
                    management_confidence=pos_p,
                    caution_signal=neg_p,
                    is_earnings_context=is_earn,
                    positive_prob=pos_p,
                    neutral_prob=neu_p,
                    negative_prob=neg_p,
                )
            )

        total = len(results)
        total_conf = sum(abs(r.score) for r in results)
        if total_conf > 0:
            composite = sum(r.score * abs(r.score) for r in results) / total_conf
        else:
            composite = sum(r.score for r in results) / total if total else 0.0

        mean_mgmt_conf = (
            sum(r.management_confidence for r in results) / total if total else 0.0
        )

        # Derive results-season signal
        bull_ratio = bullish_count / total if total else 0.0
        caut_ratio = cautious_count / total if total else 0.0
        if bull_ratio > 0.5:
            season_signal = "BULLISH_GUIDANCE"
        elif caut_ratio > 0.4:
            season_signal = "CAUTIOUS"
        else:
            season_signal = "NEUTRAL"

        logger.info(
            "finbert_tone.analyzed",
            total=total,
            earnings_context=earnings_ctx_count,
            bullish_guidance=bullish_count,
            cautious=cautious_count,
            signal=season_signal,
            composite=round(composite, 4),
        )

        return EarningsToneBatchResult(
            results=results,
            composite_score=composite,
            mean_management_confidence=mean_mgmt_conf,
            earnings_context_count=earnings_ctx_count,
            bullish_guidance_count=bullish_count,
            cautious_guidance_count=cautious_count,
            results_season_signal=season_signal,
            model_id=MODEL_ID,
        )

    async def run_calibration_check(self) -> dict:
        """
        Validate finbert-tone on India results season language.
        Blueprint gate: management confidence signal correctly classified.
        """
        test_cases = [
            ("Management remains confident of achieving 20% revenue growth in FY27.", "positive"),
            ("We are cautious about demand outlook due to rural stress and high inflation.", "negative"),
            ("The board has declared an interim dividend of ₹5 per share.", "neutral"),
            ("Operating margins declined 200 bps YoY due to higher input costs.", "negative"),
            ("Our order book remains robust, providing strong visibility for next 2 years.", "positive"),
        ]

        texts = [t for t, _ in test_cases]
        result = await self.analyze_earnings_texts(texts)

        passed = 0
        details = []
        for res, (text, expected) in zip(result.results, test_cases):
            ok = res.label == expected
            if ok:
                passed += 1
            details.append({
                "text": text[:60] + "...",
                "expected": expected,
                "got": res.label,
                "mgmt_confidence": round(res.management_confidence, 3),
                "pass": ok,
            })

        return {
            "model": MODEL_ID,
            "passed": passed,
            "total": len(test_cases),
            "pass_rate": passed / len(test_cases),
            "details": details,
        }


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_finbert_tone_analyzer() -> FinBERTToneAnalyzer:
    from config.settings import get_settings
    s = get_settings()
    return FinBERTToneAnalyzer(
        batch_size=max(8, s.sentiment_batch_size // 2),
        device="auto",
    )


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main():
        analyzer = get_finbert_tone_analyzer()
        print("=" * 60)
        print("finbert-tone — Earnings Tone Calibration Check")
        print("=" * 60)
        result = await analyzer.run_calibration_check()
        print(f"\nPass rate: {result['pass_rate']:.0%} ({result['passed']}/{result['total']})")
        for d in result["details"]:
            status = "✓" if d["pass"] else "✗"
            print(f"  {status} [{d['expected']:8s}→{d['got']:8s}] mgmt_conf={d['mgmt_confidence']:.3f}  {d['text']}")

    asyncio.run(_main())
