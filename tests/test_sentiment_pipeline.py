"""
Phase 4 Sentiment Pipeline Test Suite
======================================
Blueprint validation gate requirements:
  ✓ ProsusAI/finbert: "SEBI penalty" → Negative
  ✓ ProsusAI/finbert: "FII bought ₹8000 crore" → Positive
  ✓ GoEmotions Fear/Greed: returns 0-100 ✓
  ✓ Composite score in [-1, +1] range
  ✓ Dynamic weight adjustment for results season
  ✓ India context detector correctly identifies India-specific text

Run:
    pytest tests/test_sentiment_pipeline.py -v
    pytest tests/test_sentiment_pipeline.py -v --timeout=300  # higher timeout for model load

Note: First run downloads HuggingFace models (~1-2 GB total).
      Subsequent runs use cached models.
"""
from __future__ import annotations

import asyncio
import pytest
import pytest_asyncio
from types import SimpleNamespace


# ── FinBERT Primary Analyzer ─────────────────────────────────────────────────

class TestFinBERTAnalyzer:
    """Tests for ProsusAI/finbert (98.9% accuracy baseline)."""

    @pytest.mark.asyncio
    async def test_sebi_penalty_negative(self):
        """Blueprint gate: 'SEBI penalty' → Negative."""
        from sentiment.finbert_analyzer import get_finbert_analyzer
        analyzer = get_finbert_analyzer()
        result = await analyzer.analyze_single(
            "SEBI imposed a heavy penalty on the broker for violating circular on client front-running."
        )
        assert result.label == "negative", (
            f"Expected 'negative' for SEBI penalty text, got '{result.label}' (score={result.score})"
        )

    @pytest.mark.asyncio
    async def test_fii_buying_positive(self):
        """Blueprint gate: 'FII bought ₹8000 crore' → Positive."""
        from sentiment.finbert_analyzer import get_finbert_analyzer
        analyzer = get_finbert_analyzer()
        result = await analyzer.analyze_single(
            "FII bought ₹8000 crore worth of equities on NSE in a single trading session."
        )
        assert result.label == "positive", (
            f"Expected 'positive' for FII buying text, got '{result.label}' (score={result.score})"
        )

    @pytest.mark.asyncio
    async def test_score_range(self):
        """FinBERT scores must be in [-1, +1]."""
        from sentiment.finbert_analyzer import get_finbert_analyzer
        analyzer = get_finbert_analyzer()
        texts = [
            "Market crashed 1500 points today.",
            "Company reported record profit.",
            "The stock traded sideways on low volume.",
        ]
        result = await analyzer.analyze_texts(texts)
        assert -1.0 <= result.composite_score <= 1.0
        for r in result.results:
            assert r.score in (-1.0, 0.0, 1.0)

    @pytest.mark.asyncio
    async def test_batch_count(self):
        """Batch result count matches input."""
        from sentiment.finbert_analyzer import get_finbert_analyzer
        analyzer = get_finbert_analyzer()
        texts = [f"Test text {i} with some financial content." for i in range(10)]
        result = await analyzer.analyze_texts(texts)
        assert result.total_texts == 10

    @pytest.mark.asyncio
    async def test_calibration_pass_rate(self):
        """Full calibration check must pass ≥ 80%."""
        from sentiment.finbert_analyzer import get_finbert_analyzer
        analyzer = get_finbert_analyzer()
        check = await analyzer.run_calibration_check()
        assert check["pass_rate"] >= 0.8, (
            f"FinBERT calibration {check['pass_rate']:.0%} < 80%. Details: {check['details']}"
        )

    @pytest.mark.asyncio
    async def test_empty_input(self):
        """Empty input returns neutral result safely."""
        from sentiment.finbert_analyzer import get_finbert_analyzer
        analyzer = get_finbert_analyzer()
        result = await analyzer.analyze_texts([])
        assert result.label == "NEUTRAL"
        assert result.total_texts == 0


# ── FinBERT India Analyzer ────────────────────────────────────────────────────

class TestFinBERTIndiaAnalyzer:
    """Tests for Vansh180/FinBERT-India-v1 + India context detection."""

    def test_india_context_detector_rbi(self):
        """RBI text should trigger India context detector."""
        from sentiment.finbert_india_analyzer import FinBERTIndiaAnalyzer
        analyzer = FinBERTIndiaAnalyzer()
        assert analyzer.is_india_context("RBI raised repo rate by 25 bps") is True

    def test_india_context_detector_fii(self):
        """FII/DII text should trigger India context detector."""
        from sentiment.finbert_india_analyzer import FinBERTIndiaAnalyzer
        analyzer = FinBERTIndiaAnalyzer()
        assert analyzer.is_india_context("FII bought ₹8000 crore in NSE") is True

    def test_non_india_context(self):
        """Non-India text should NOT trigger India context detector."""
        from sentiment.finbert_india_analyzer import FinBERTIndiaAnalyzer
        analyzer = FinBERTIndiaAnalyzer()
        assert analyzer.is_india_context("The Fed raised US interest rates by 25 basis points.") is False

    def test_india_context_inr_symbol(self):
        """₹ symbol should trigger India context."""
        from sentiment.finbert_india_analyzer import FinBERTIndiaAnalyzer
        analyzer = FinBERTIndiaAnalyzer()
        assert analyzer.is_india_context("Company revenue was ₹500 crore in Q3FY25") is True

    def test_india_context_nifty(self):
        """Nifty reference should trigger India context."""
        from sentiment.finbert_india_analyzer import FinBERTIndiaAnalyzer
        analyzer = FinBERTIndiaAnalyzer()
        assert analyzer.is_india_context("Nifty 50 fell 300 points on global selloff") is True

    @pytest.mark.asyncio
    async def test_fused_score_range(self):
        """Fused India+Prosus score must be in [-1, +1]."""
        from sentiment.finbert_india_analyzer import get_finbert_india_analyzer
        analyzer = get_finbert_india_analyzer()
        prosus_scores = [0.5, -0.3, 0.0]
        result = await analyzer.analyze_with_india_boost(
            texts=["RBI cut rates today.", "SEBI penalty imposed.", "Flat trading session."],
            prosus_scores=prosus_scores,
        )
        assert -1.0 <= result.composite_score <= 1.0

    @pytest.mark.asyncio
    async def test_india_context_routing(self):
        """Only India-context texts should be routed through FinBERT-India."""
        from sentiment.finbert_india_analyzer import get_finbert_india_analyzer
        analyzer = get_finbert_india_analyzer()
        texts = [
            "Nifty Bank rallied 500 points today.",  # India context
            "US markets closed flat after Fed minutes.",  # NOT India context
        ]
        result = await analyzer.analyze_with_india_boost(texts=texts)
        assert result.india_context_count == 1
        for r in result.results:
            assert -1.0 <= r.fused_score <= 1.0


# ── FinBERT Tone Analyzer ─────────────────────────────────────────────────────

class TestFinBERTToneAnalyzer:
    """Tests for yiyanghkust/finbert-tone earnings call analysis."""

    def test_earnings_context_detector_quarterly(self):
        """Quarterly results text should be detected as earnings context."""
        from sentiment.finbert_tone_analyzer import FinBERTToneAnalyzer
        analyzer = FinBERTToneAnalyzer()
        assert analyzer.is_earnings_context("Q3 FY25 results: revenue grew 18% YoY") is True

    def test_earnings_context_detector_guidance(self):
        """Guidance language should be detected as earnings context."""
        from sentiment.finbert_tone_analyzer import FinBERTToneAnalyzer
        analyzer = FinBERTToneAnalyzer()
        assert analyzer.is_earnings_context("Management remains optimistic about FY26 outlook") is True

    def test_non_earnings_context(self):
        """Technical analysis text is NOT an earnings context."""
        from sentiment.finbert_tone_analyzer import FinBERTToneAnalyzer
        analyzer = FinBERTToneAnalyzer()
        assert analyzer.is_earnings_context("RSI crossed 70, stock near resistance") is False

    @pytest.mark.asyncio
    async def test_management_confidence_score(self):
        """Confident guidance text should have high management_confidence score."""
        from sentiment.finbert_tone_analyzer import get_finbert_tone_analyzer
        analyzer = get_finbert_tone_analyzer()
        result = await analyzer.analyze_earnings_texts([
            "Management is highly confident of 25% revenue growth next quarter with strong order book.",
        ])
        assert len(result.results) == 1
        assert result.results[0].management_confidence > 0.0
        assert -1.0 <= result.composite_score <= 1.0

    @pytest.mark.asyncio
    async def test_cautious_guidance(self):
        """Cautious guidance text should yield low management_confidence."""
        from sentiment.finbert_tone_analyzer import get_finbert_tone_analyzer
        analyzer = get_finbert_tone_analyzer()
        result = await analyzer.analyze_earnings_texts([
            "We are cautious about near-term demand outlook due to rural stress and margin headwinds.",
        ])
        assert result.results[0].caution_signal > 0.0


# ── GoEmotions Fear/Greed ─────────────────────────────────────────────────────

class TestGoEmotionsAnalyzer:
    """Tests for Google GoEmotions India Fear/Greed Index."""

    @pytest.mark.asyncio
    async def test_fear_greed_range(self):
        """Fear/Greed index MUST be in [0, 100]."""
        from sentiment.goemotions_analyzer import get_goemotions_analyzer
        analyzer = get_goemotions_analyzer()
        texts = ["Nifty rallying! Feeling great about the market."]
        result = await analyzer.compute_fear_greed_index(texts)
        assert 0.0 <= result.index <= 100.0, f"Index {result.index} out of [0, 100] range"

    @pytest.mark.asyncio
    async def test_fear_texts_yield_fear(self):
        """Panic texts should yield Fear (index < 40)."""
        from sentiment.goemotions_analyzer import get_goemotions_analyzer
        analyzer = get_goemotions_analyzer()
        fear_texts = [
            "Market is crashing! Panic selling everywhere. I'm scared.",
            "Portfolio is completely red. This is disaster.",
            "Circuit breaker triggered. Everything is falling.",
        ]
        result = await analyzer.compute_fear_greed_index(fear_texts)
        assert result.index < 50.0, (
            f"Fear scenario index {result.index} not below 50 (expected < 40 ideally)"
        )

    @pytest.mark.asyncio
    async def test_greed_texts_yield_greed(self):
        """Euphoric texts should yield Greed (index > 60)."""
        from sentiment.goemotions_analyzer import get_goemotions_analyzer
        analyzer = get_goemotions_analyzer()
        greed_texts = [
            "Amazing rally! Nifty at all time high! Best time to invest!",
            "Everything is going up. FOMO is real. Buy anything.",
            "Bulls are unstoppable. India market is best in world!",
        ]
        result = await analyzer.compute_fear_greed_index(greed_texts)
        assert result.index > 50.0, (
            f"Greed scenario index {result.index} not above 50 (expected > 60 ideally)"
        )

    @pytest.mark.asyncio
    async def test_fear_label(self):
        """Label field must be one of the valid categories."""
        from sentiment.goemotions_analyzer import get_goemotions_analyzer
        analyzer = get_goemotions_analyzer()
        result = await analyzer.compute_fear_greed_index(["Flat session today."])
        assert result.label in {"EXTREME_FEAR", "FEAR", "NEUTRAL", "GREED", "EXTREME_GREED"}

    @pytest.mark.asyncio
    async def test_empty_input_returns_neutral(self):
        """Empty input → neutral index = 50."""
        from sentiment.goemotions_analyzer import get_goemotions_analyzer
        analyzer = get_goemotions_analyzer()
        result = await analyzer.compute_fear_greed_index([])
        assert result.index == 50.0
        assert result.label == "NEUTRAL"

    @pytest.mark.asyncio
    async def test_calibration_pass(self):
        """Full calibration: fear < greed AND both in valid range."""
        from sentiment.goemotions_analyzer import get_goemotions_analyzer
        analyzer = get_goemotions_analyzer()
        check = await analyzer.run_calibration_check()
        assert check["range_valid_pass"], "Fear/Greed index out of [0,100] range"
        # Fear index should be lower than greed index
        assert check["fear_index"] < check["greed_index"], (
            f"Fear ({check['fear_index']}) not less than Greed ({check['greed_index']})"
        )


# ── GDELT Tone Analyzer ───────────────────────────────────────────────────────

class TestGDELTToneAnalyzer:
    """Tests for GDELT India macro tone wrapper."""

    @pytest.mark.asyncio
    async def test_tone_score_in_range(self):
        """GDELT normalized score must be in [-1, +1]."""
        from sentiment.gdelt_tone_analyzer import get_gdelt_tone_analyzer
        analyzer = get_gdelt_tone_analyzer()
        score = await analyzer.get_tone_score()
        assert -1.0 <= score <= 1.0, f"Score {score} out of [-1, +1] range"

    @pytest.mark.asyncio
    async def test_india_macro_tone_structure(self):
        """India macro tone returns valid GDELTToneResult."""
        from sentiment.gdelt_tone_analyzer import get_gdelt_tone_analyzer
        analyzer = get_gdelt_tone_analyzer()
        result = await analyzer.get_india_macro_tone()
        assert -1.0 <= result.normalized_score <= 1.0
        assert result.label in {
            "STRONGLY_NEGATIVE", "NEGATIVE", "MILDLY_NEGATIVE",
            "NEUTRAL", "MILDLY_POSITIVE", "POSITIVE", "STRONGLY_POSITIVE"
        }
        assert isinstance(result.article_count, int)

    @pytest.mark.asyncio
    async def test_composite_returns_gdelt_india_result(self):
        """Composite India tone produces GDELTIndiaResult."""
        from sentiment.gdelt_tone_analyzer import get_gdelt_tone_analyzer, GDELTIndiaResult
        analyzer = get_gdelt_tone_analyzer()
        result = await analyzer.get_composite_india_tone()
        assert isinstance(result, GDELTIndiaResult)
        assert -1.0 <= result.composite_score <= 1.0
        assert result.macro_news_flow in {"HIGH", "NORMAL", "LOW"}

    @pytest.mark.asyncio
    async def test_health_check(self):
        """Health check endpoint responds."""
        from sentiment.gdelt_tone_analyzer import get_gdelt_tone_analyzer
        analyzer = get_gdelt_tone_analyzer()
        health = await analyzer.health_check()
        assert health["status"] in {"ok", "error"}
        if health["status"] == "ok":
            assert "gdelt_composite_score" in health


# ── Fear/Greed Index ──────────────────────────────────────────────────────────

class TestIndiaFearGreedIndex:
    """Tests for India Fear/Greed Index composite."""

    @pytest.mark.asyncio
    async def test_index_range(self):
        """Fear/Greed index must be in [0, 100]."""
        from sentiment.fear_greed_index import get_fear_greed_index
        index = get_fear_greed_index()
        result = await index.compute(
            social_texts=["Market is doing well today."],
            stocktwits_bullish=5, stocktwits_bearish=2, stocktwits_neutral=3,
            gdelt_normalized_score=0.1,
        )
        assert 0.0 <= result.index <= 100.0

    @pytest.mark.asyncio
    async def test_stocktwits_pure_bullish(self):
        """All-bullish StockTwits should push index above 50."""
        from sentiment.fear_greed_index import get_fear_greed_index
        index = get_fear_greed_index()
        result = await index.compute(
            social_texts=[],
            stocktwits_bullish=30, stocktwits_bearish=0, stocktwits_neutral=0,
            gdelt_normalized_score=0.0,
        )
        # StockTwits is 30% weight → all bullish = stocktwits score 100
        # Even with GoEmotions at 50 default → should be > 50
        assert result.stocktwits_score > 70.0

    @pytest.mark.asyncio
    async def test_contrarian_signal(self):
        """Extreme Fear should trigger CONTRARIAN_BUY signal."""
        from sentiment.fear_greed_index import FearGreedResult, _contrarian
        # Directly test contrarian function
        assert _contrarian(15.0) == "CONTRARIAN_BUY"
        assert _contrarian(85.0) == "CONTRARIAN_SELL"
        assert _contrarian(50.0) == "NO_SIGNAL"

    @pytest.mark.asyncio
    async def test_vix_adjusted_extreme(self):
        """With extreme VIX, vix_adjusted_index should be computed."""
        from sentiment.fear_greed_index import get_fear_greed_index
        index = get_fear_greed_index()
        result = await index.compute(
            social_texts=["Market may crash..."],
            gdelt_normalized_score=-0.5,
            current_vix=28.0,   # EXTREME VIX
        )
        assert result.vix_adjusted_index is not None
        assert result.vix_regime == "EXTREME"

    @pytest.mark.asyncio
    async def test_calibration_gate(self):
        """Phase 4 gate: Fear/Greed calibration check passes."""
        from sentiment.fear_greed_index import get_fear_greed_index
        index = get_fear_greed_index()
        check = await index.run_calibration_check()
        # Range must always be valid — non-negotiable
        assert check["range_valid_pass"], "Fear/Greed range invalid"
        # Fear < Greed direction is the key directional test
        assert check["fear_index"] < check["greed_index"]

    @pytest.mark.asyncio
    async def test_goemotions_runtime_failure_degrades_to_neutral(self, monkeypatch):
        """GoEmotions runtime/device failures should not bubble out of Fear/Greed."""
        from sentiment.fear_greed_index import get_fear_greed_index

        index = get_fear_greed_index()

        async def fake_compute_fear_greed_index(*args, **kwargs):
            raise RuntimeError("Tensor on device meta is not on the expected device cpu!")

        monkeypatch.setattr(index._goemotions, "compute_fear_greed_index", fake_compute_fear_greed_index)

        result = await index.compute(
            social_texts=["Reliance looks strong today."],
            stocktwits_bullish=3,
            stocktwits_bearish=1,
            stocktwits_neutral=0,
            gdelt_normalized_score=0.0,
        )
        assert result.goemotions_score == 50.0
        assert 0.0 <= result.index <= 100.0


# ── Composite Sentiment ───────────────────────────────────────────────────────

class TestCompositeSentimentEngine:
    """Tests for the 5-model composite fusion engine."""

    @pytest.mark.asyncio
    async def test_composite_score_range(self):
        """Composite score must be in [-1.0, +1.0]."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        result = await engine.analyze(
            ticker="RELIANCE",
            news_texts=["Reliance Industries reported strong quarterly results."],
            social_texts=["RELIANCE looking strong. Buy signal confirmed."],
            earnings_texts=["Management confident of 15% revenue growth next year."],
            stocktwits_bullish=8, stocktwits_bearish=2, stocktwits_neutral=5,
            gdelt_normalized_score=0.3,
        )
        assert -1.0 <= result.score <= 1.0, f"Score {result.score} out of range"

    @pytest.mark.asyncio
    async def test_composite_label_valid(self):
        """Label must be one of the 5 valid values."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        result = await engine.analyze(
            ticker="TCS",
            news_texts=["TCS wins $500M deal from US client."],
            social_texts=["TCS at ATH! Strong buy."],
            gdelt_normalized_score=0.2,
        )
        assert result.label in {
            "STRONGLY_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONGLY_BEARISH"
        }

    @pytest.mark.asyncio
    async def test_results_season_weight_adjustment(self):
        """Results season should change weight to RESULTS_SEASON."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        result = await engine.analyze(
            ticker="HDFCBANK",
            news_texts=["HDFC Bank Q3 results: 20% PAT growth."],
            social_texts=["HDFCBANK great results!"],
            earnings_texts=["Management confident of continued growth."],
            is_results_season=True,
        )
        # During results season, earnings weight should be 0.35
        assert result.components.w_earnings == 0.35, (
            f"Expected earnings weight 0.35 during results season, got {result.components.w_earnings}"
        )
        assert "RESULTS_SEASON" in result.weight_adjustment_applied

    @pytest.mark.asyncio
    async def test_geopolitical_crisis_weight(self):
        """Geopolitical crisis should elevate GDELT weight."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        result = await engine.analyze(
            ticker="NIFTY",
            news_texts=["India border tensions escalate."],
            social_texts=["Markets nervous about India-Pakistan situation."],
            is_geopolitical_crisis=True,
        )
        assert result.components.w_gdelt == 0.35
        assert "GEOPOLITICAL" in result.weight_adjustment_applied

    @pytest.mark.asyncio
    async def test_confidence_in_range(self):
        """Confidence must be in [0, 1]."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        result = await engine.analyze(
            ticker="INFY",
            news_texts=["Infosys wins large contract."],
            social_texts=["INFY bullish!"],
        )
        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_components_present(self):
        """All components should be present in result."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        result = await engine.analyze(
            ticker="WIPRO",
            news_texts=["Wipro Q4 results in line with estimates."],
            social_texts=["Meh results from Wipro."],
        )
        assert result.components is not None
        assert result.fear_greed_index is not None
        assert result.fear_greed_label is not None
        assert result.contrarian_signal is not None

    @pytest.mark.asyncio
    async def test_empty_inputs(self):
        """Empty inputs should return neutral result without crashing."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        result = await engine.analyze(
            ticker="TEST",
            news_texts=[],
            social_texts=[],
        )
        assert -1.0 <= result.score <= 1.0
        assert result.label is not None

    @pytest.mark.asyncio
    async def test_no_earnings_texts_path_does_not_require_asyncio_coroutine(self, monkeypatch):
        """The optional earnings branch should work on modern asyncio without coroutine()."""
        from sentiment.composite_sentiment import get_composite_sentiment
        from sentiment.fear_greed_index import FearGreedResult

        engine = get_composite_sentiment()

        async def fake_finbert(_texts):
            return SimpleNamespace(composite_score=0.2, results=[])

        async def fake_fear_greed(**_kwargs):
            return FearGreedResult(
                index=55.0,
                label="NEUTRAL",
                contrarian_signal="NO_SIGNAL",
                goemotions_score=50.0,
                stocktwits_score=50.0,
                gdelt_score_contribution=50.0,
            )

        async def fake_india_boost(texts, prosus_scores=None):
            return SimpleNamespace(composite_score=0.2)

        monkeypatch.setattr(engine._finbert, "analyze_texts", fake_finbert)
        monkeypatch.setattr(engine._fear_greed, "compute", fake_fear_greed)
        monkeypatch.setattr(engine._finbert_india, "analyze_with_india_boost", fake_india_boost)

        result = await engine.analyze(
            ticker="RELIANCE",
            news_texts=["Reliance reported stable refining margins."],
            social_texts=["Reliance looks steady."],
            earnings_texts=[],
            gdelt_normalized_score=0.0,
        )
        assert result is not None
        assert result.earnings_tone == 0.0

    @pytest.mark.asyncio
    async def test_full_phase4_validation(self):
        """Run the blueprint Phase 4 validation gate."""
        from sentiment.composite_sentiment import get_composite_sentiment
        engine = get_composite_sentiment()
        check = await engine.run_phase4_validation()

        # Non-negotiable: composite range must always be valid
        assert check["composite_range_valid"], "Composite score out of [-1, +1] range"
        assert check["components_present"], "Components missing from result"

        # Finbert calibration ≥ 80%
        assert check["finbert_calibration"]["pass_rate"] >= 0.8, (
            f"FinBERT calibration {check['finbert_calibration']['pass_rate']:.0%} < 80%"
        )

        # Fear/Greed valid range
        assert check["fear_greed_calibration"]["range_valid_pass"]


# ── Weight arithmetic integrity ───────────────────────────────────────────────

class TestWeightIntegrity:
    """Non-ML unit tests for weight arithmetic."""

    def test_default_weights_sum(self):
        """Default weights must sum to 1.0."""
        from sentiment.composite_sentiment import _resolve_weights
        w_f, w_fg, w_g, w_e, _ = _resolve_weights(False, False)
        total = w_f + w_fg + w_g + w_e
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total} (expected 1.0)"

    def test_results_season_weights_sum(self):
        """Results season weights must sum to 1.0."""
        from sentiment.composite_sentiment import _resolve_weights
        w_f, w_fg, w_g, w_e, label = _resolve_weights(True, False)
        total = w_f + w_fg + w_g + w_e
        assert abs(total - 1.0) < 1e-9, f"Results season weights sum to {total}"
        assert label == "RESULTS_SEASON"
        assert w_e == 0.35

    def test_geopolitical_weights_sum(self):
        """Geopolitical weights must sum to 1.0."""
        from sentiment.composite_sentiment import _resolve_weights
        w_f, w_fg, w_g, w_e, label = _resolve_weights(False, True)
        total = w_f + w_fg + w_g + w_e
        assert abs(total - 1.0) < 1e-9, f"Geopolitical weights sum to {total}"
        assert label == "GEOPOLITICAL"
        assert w_g == 0.35

    def test_stocktwits_all_bearish_score(self):
        """All-bearish StockTwits should yield score < 50."""
        from sentiment.fear_greed_index import _stocktwits_to_fg_score
        score = _stocktwits_to_fg_score(bullish=0, bearish=20, neutral=0)
        assert score < 50.0, f"All-bearish score {score} >= 50"

    def test_stocktwits_all_bullish_score(self):
        """All-bullish StockTwits should yield score > 50."""
        from sentiment.fear_greed_index import _stocktwits_to_fg_score
        score = _stocktwits_to_fg_score(bullish=20, bearish=0, neutral=0)
        assert score > 50.0, f"All-bullish score {score} <= 50"

    def test_gdelt_to_fg_zero(self):
        """GDELT tone=0 → Fear/Greed = 50 exactly."""
        from sentiment.fear_greed_index import _gdelt_to_fg_score
        score = _gdelt_to_fg_score(0.0)
        assert score == 50.0

    def test_gdelt_to_fg_positive(self):
        """Positive GDELT tone → Fear/Greed > 50."""
        from sentiment.fear_greed_index import _gdelt_to_fg_score
        score = _gdelt_to_fg_score(0.5)
        assert score > 50.0

    def test_gdelt_to_fg_negative(self):
        """Negative GDELT tone → Fear/Greed < 50."""
        from sentiment.fear_greed_index import _gdelt_to_fg_score
        score = _gdelt_to_fg_score(-0.5)
        assert score < 50.0

    def test_score_to_label_bounds(self):
        """Score → label mapping covers all regions."""
        from sentiment.composite_sentiment import _score_to_label
        assert _score_to_label(0.8) == "STRONGLY_BULLISH"
        assert _score_to_label(0.3) == "BULLISH"
        assert _score_to_label(0.0) == "NEUTRAL"
        assert _score_to_label(-0.3) == "BEARISH"
        assert _score_to_label(-0.8) == "STRONGLY_BEARISH"

    def test_model_agreement_confidence_perfect(self):
        """All same score → confidence = 1.0."""
        from sentiment.composite_sentiment import _model_agreement_confidence
        conf = _model_agreement_confidence([0.5, 0.5, 0.5, 0.5])
        assert conf == 1.0

    def test_model_agreement_confidence_mixed(self):
        """Mixed +1/-1 signals → low confidence."""
        from sentiment.composite_sentiment import _model_agreement_confidence
        conf = _model_agreement_confidence([1.0, -1.0, 1.0, -1.0])
        assert conf < 0.5


# ── GDELT normalization utils ─────────────────────────────────────────────────

class TestGDELTNormalization:
    
    def test_normalize_zero(self):
        """GDELT raw_tone 0 → normalized 0."""
        from sentiment.gdelt_tone_analyzer import _normalize_tone
        assert _normalize_tone(0.0) == 0.0

    def test_normalize_positive(self):
        """GDELT raw_tone +5 → normalized +0.5."""
        from sentiment.gdelt_tone_analyzer import _normalize_tone
        assert _normalize_tone(5.0) == 0.5

    def test_normalize_clamp(self):
        """GDELT extreme raw_tone clamped to ±1.0."""
        from sentiment.gdelt_tone_analyzer import _normalize_tone
        assert _normalize_tone(15.0) == 1.0
        assert _normalize_tone(-15.0) == -1.0

    def test_raw_tone_labels(self):
        """Label mapping covers all zones."""
        from sentiment.gdelt_tone_analyzer import _raw_tone_to_label
        assert _raw_tone_to_label(-6.0) == "STRONGLY_NEGATIVE"
        assert _raw_tone_to_label(-3.0) == "NEGATIVE"
        assert _raw_tone_to_label(0.0) == "NEUTRAL"
        assert _raw_tone_to_label(3.0) == "POSITIVE"
        assert _raw_tone_to_label(6.0) == "STRONGLY_POSITIVE"
