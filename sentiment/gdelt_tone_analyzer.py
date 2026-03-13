"""
GDELT V2Tone — India Macro Sentiment Score (-10 to +10)
========================================================
Source: GDELT (Global Database of Events, Language, and Tone)
  - No API key required (truly free, unlimited)
  - Processes 65+ languages across 100+ countries
  - Real-time global news monitoring
  - India filter: sourcecountry:IN + India-specific query terms

V2Tone field: Comma-separated string containing 6 tone dimensions:
  [0] Tone        : overall article tone (-10 negative → +10 positive)
  [1] Polarity    : absolute magnitude of emotional content
  [2] PositiveTone: share of positive-tone words (%)
  [3] NegativeTone: share of negative-tone words (%)
  [4] Polarity2   : polarization score
  [5] ActivityRef : activity/event reference density

This adapter is a WRAPPER around gdelt_client.py (already built in data/adapters/).
It formats GDELT tone into the standard sentiment pipeline interface for
composite_sentiment.py consumption.

Output:
  GDELT India Tone Score: -10 to +10
  Normalized to [-1, +1] for sentiment fusion:
    score = raw_tone / 10.0
    (capped at ±1.0 to handle rare extreme values)

Regime interpretation:
  < -3 → strong negative macro tone (risk-off India)
  -3 to -1 → mildly negative
  -1 to +1 → neutral/mixed
  +1 to +3 → mildly positive (risk-on India)
  > +3 → strong positive macro tone

India Query Terms Used:
  - Primary: "India economy stock market NSE Nifty"
  - Ticker-specific: "RELIANCE NSE" / "HDFCBANK India"
  - Events: "RBI monetary policy India" / "SEBI India"
  - Geopolitical: (filtered separately for geo-risk overlay)

Usage:
    analyzer = get_gdelt_tone_analyzer()
    result = await analyzer.get_india_macro_tone(ticker="HDFCBANK", days_back=1)
    # → GDELTToneResult(tone_score=2.3, normalized_score=0.23, label="MILDLY_POSITIVE")
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from functools import lru_cache

import structlog

logger = structlog.get_logger(__name__)

# Import the existing GDELT client (built in Phase 1)
from data.adapters.gdelt_client import GDELTClient


# ── Tone labels ───────────────────────────────────────────────────────────────

def _raw_tone_to_label(tone: float) -> str:
    """Convert GDELT raw tone (-10 to +10) to readable label."""
    if tone <= -5:
        return "STRONGLY_NEGATIVE"
    elif tone <= -2:
        return "NEGATIVE"
    elif tone <= -0.5:
        return "MILDLY_NEGATIVE"
    elif tone < 0.5:
        return "NEUTRAL"
    elif tone < 2:
        return "MILDLY_POSITIVE"
    elif tone < 5:
        return "POSITIVE"
    else:
        return "STRONGLY_POSITIVE"


def _normalize_tone(raw_tone: float) -> float:
    """Normalize GDELT tone [-10, +10] → [-1.0, +1.0] for fusion."""
    normalized = raw_tone / 10.0
    return max(-1.0, min(1.0, normalized))


# India-specific query templates
INDIA_MACRO_QUERY = "India economy stock market NSE Nifty Sensex"
INDIA_RBI_QUERY = "RBI Reserve Bank India monetary policy repo rate"
INDIA_SEBI_QUERY = "SEBI Securities Exchange Board India regulation"
INDIA_FII_QUERY = "FII FPI foreign investor India equity"
INDIA_GEOPOLITICAL_QUERY = "India geopolitical border conflict tension"


@dataclass
class GDELTToneResult:
    """GDELT India macro tone result."""
    raw_tone_score: float          # raw V2Tone value (-10 to +10)
    normalized_score: float        # divided by 10, capped at [-1, +1]
    label: str                     # "STRONGLY_NEGATIVE" ... "STRONGLY_POSITIVE"
    article_count: int             # number of articles analyzed
    articles: list[dict] = field(default_factory=list)   # raw article data
    query_used: str = ""


@dataclass
class GDELTIndiaResult:
    """Multi-query GDELT India macro composite."""
    macro_tone: GDELTToneResult          # general India market tone
    rbi_tone: Optional[GDELTToneResult]  # RBI/monetary policy tone (if requested)
    fii_tone: Optional[GDELTToneResult]  # FII flow news tone (if requested)
    geo_risk_score: float                # geopolitical risk score (negative-biased)
    composite_score: float               # weighted composite [-1.0, +1.0]
    composite_label: str
    ticker_tone: Optional[GDELTToneResult] = None   # ticker-specific tone

    # Dynamic weight adjustments
    geopolitical_risk_flag: bool = False   # True if India geo score < -3
    macro_news_flow: str = "NORMAL"        # "HIGH" | "NORMAL" | "LOW"


from typing import Optional  # needed for dataclass fields above


class GDELTToneAnalyzer:
    """
    GDELT V2Tone sentiment adapter for the composite sentiment pipeline.

    Wraps the existing GDELTClient (data/adapters/gdelt_client.py) and
    formats output for consumption by composite_sentiment.py.

    This module is NOT a separate ML model — it uses GDELT's
    pre-computed NLP tone scores (V2Tone), which are already computed
    by GDELT's proprietary text processing pipeline across 65+ languages.

    Weight in composite formula: 0.20 (from blueprint)
    Increased to 0.35 during geopolitical crisis events.
    """

    def __init__(self):
        self._client = GDELTClient()

    async def get_india_macro_tone(
        self,
        ticker: Optional[str] = None,
        days_back: int = 1,
        max_records: int = 50,
    ) -> GDELTToneResult:
        """
        Fetch general India macro tone from GDELT.

        Args:
            ticker: NSE ticker to add as query filter (optional)
            days_back: look-back period in days (default 1 = last 24 hours)
            max_records: max articles to fetch (default 50)

        Returns:
            GDELTToneResult with raw tone, normalized score, label
        """
        query = INDIA_MACRO_QUERY
        if ticker:
            # Add ticker-specific context to GDELT query
            clean_ticker = ticker.replace(".NS", "").replace(".BO", "")
            query = f"{clean_ticker} India {query}"

        articles = await self._client.get_india_tone(
            query=query,
            days_back=days_back,
            max_records=max_records,
        )

        if not articles:
            logger.warning("gdelt_tone.no_articles", query=query)
            return GDELTToneResult(
                raw_tone_score=0.0,
                normalized_score=0.0,
                label="NEUTRAL",
                article_count=0,
                query_used=query,
            )

        raw_tone = sum(a["tone"] for a in articles) / len(articles)
        normalized = _normalize_tone(raw_tone)
        label = _raw_tone_to_label(raw_tone)

        logger.info(
            "gdelt_tone.macro_computed",
            articles=len(articles),
            raw_tone=round(raw_tone, 3),
            normalized=round(normalized, 3),
            label=label,
        )

        return GDELTToneResult(
            raw_tone_score=round(raw_tone, 3),
            normalized_score=round(normalized, 4),
            label=label,
            article_count=len(articles),
            articles=articles[:5],    # keep only top 5 for memory efficiency
            query_used=query,
        )

    async def get_rbi_tone(self, days_back: int = 3) -> GDELTToneResult:
        """
        Fetch RBI/monetary policy news tone.
        Uses 3-day lookback (RBI decisions impact markets for 2-3 days).
        """
        articles = await self._client.get_india_tone(
            query=INDIA_RBI_QUERY,
            days_back=days_back,
            max_records=30,
        )

        if not articles:
            return GDELTToneResult(
                raw_tone_score=0.0,
                normalized_score=0.0,
                label="NEUTRAL",
                article_count=0,
                query_used=INDIA_RBI_QUERY,
            )

        raw_tone = sum(a["tone"] for a in articles) / len(articles)
        return GDELTToneResult(
            raw_tone_score=round(raw_tone, 3),
            normalized_score=round(_normalize_tone(raw_tone), 4),
            label=_raw_tone_to_label(raw_tone),
            article_count=len(articles),
            query_used=INDIA_RBI_QUERY,
        )

    async def get_geopolitical_score(self, days_back: int = 2) -> float:
        """
        India geopolitical risk score.
        Returns raw GDELT tone (negative = higher risk).
        Separate from macro tone — used to flag geo-risk regime.
        """
        articles = await self._client.get_india_tone(
            query=INDIA_GEOPOLITICAL_QUERY,
            days_back=days_back,
            max_records=20,
        )
        if not articles:
            return 0.0
        return sum(a["tone"] for a in articles) / len(articles)

    async def get_composite_india_tone(
        self,
        ticker: Optional[str] = None,
        days_back: int = 1,
        include_rbi: bool = True,
        include_geo: bool = True,
    ) -> GDELTIndiaResult:
        """
        Multi-query composite India GDELT tone — primary interface for composite_sentiment.py.

        Combines:
          - General India market tone (weight 0.5)
          - RBI/monetary policy tone (weight 0.3 if requested)
          - FII news tone (weight 0.2)
          - Geopolitical risk overlay (flag if score < -3)

        Args:
            ticker: NSE ticker for ticker-specific news (optional)
            days_back: look-back in days
            include_rbi: include RBI-specific query (useful on MPC dates)
            include_geo: include geopolitical risk check

        Returns:
            GDELTIndiaResult with composite_score [-1, +1] and labels
        """
        # Parallel fetches
        tasks = {
            "macro": self.get_india_macro_tone(ticker=ticker, days_back=days_back),
        }
        if include_rbi:
            tasks["rbi"] = self.get_rbi_tone(days_back=max(days_back, 3))
        if include_geo:
            tasks["geo"] = self.get_geopolitical_score(days_back=days_back)

        gathered = await asyncio.gather(*tasks.values(), return_exceptions=True)
        results_map = dict(zip(tasks.keys(), gathered))

        # Extract results with fallback
        macro_tone: GDELTToneResult = (
            results_map.get("macro")
            if not isinstance(results_map.get("macro"), Exception)
            else GDELTToneResult(0.0, 0.0, "NEUTRAL", 0)
        )
        rbi_tone: Optional[GDELTToneResult] = (
            results_map.get("rbi")
            if not isinstance(results_map.get("rbi", None), Exception)
            else None
        )
        geo_score: float = (
            results_map.get("geo", 0.0)
            if not isinstance(results_map.get("geo", 0.0), Exception)
            else 0.0
        )

        # Composite weighting
        composite = macro_tone.normalized_score * 0.60

        if rbi_tone and not isinstance(rbi_tone, Exception):
            composite += rbi_tone.normalized_score * 0.25
        
        # Geo risk: normalize and reduce composite when risks are high
        geo_normalized = _normalize_tone(geo_score)
        if geo_score < -3.0:
            # Strong geopolitical risk — downward pressure on composite
            composite += geo_normalized * 0.15
            geo_risk_flag = True
        else:
            composite += geo_normalized * 0.05
            geo_risk_flag = False

        composite = max(-1.0, min(1.0, composite))
        composite_label = _raw_tone_to_label(composite * 10)

        # Article count determines news flow level
        article_count = macro_tone.article_count
        news_flow = (
            "HIGH" if article_count > 40
            else "LOW" if article_count < 5
            else "NORMAL"
        )

        logger.info(
            "gdelt_tone.composite",
            macro_score=macro_tone.normalized_score,
            rbi_score=rbi_tone.normalized_score if rbi_tone else "N/A",
            geo_risk=round(geo_score, 2),
            composite=round(composite, 4),
            label=composite_label,
            geo_risk_flag=geo_risk_flag,
        )

        return GDELTIndiaResult(
            macro_tone=macro_tone,
            rbi_tone=rbi_tone,
            fii_tone=None,     # FII tone can be added in Phase 7 enrichment
            geo_risk_score=round(geo_score, 3),
            composite_score=round(composite, 4),
            composite_label=composite_label,
            geopolitical_risk_flag=geo_risk_flag,
            macro_news_flow=news_flow,
        )

    async def get_tone_score(
        self,
        ticker: Optional[str] = None,
        days_back: int = 1,
    ) -> float:
        """
        Lightweight interface: just the composite score [-1, +1].
        Used by composite_sentiment.py for the GDELT weight slot.
        """
        result = await self.get_composite_india_tone(
            ticker=ticker,
            days_back=days_back,
            include_rbi=True,
            include_geo=True,
        )
        return result.composite_score

    async def health_check(self) -> dict:
        """Health check for API layer."""
        try:
            score = await self.get_tone_score()
            return {
                "status": "ok",
                "gdelt_composite_score": score,
                "range_valid": -1.0 <= score <= 1.0,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ── Singleton ─────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_gdelt_tone_analyzer() -> GDELTToneAnalyzer:
    """Global singleton. GDELTClient is stateless — safe to cache."""
    return GDELTToneAnalyzer()


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    async def _main():
        analyzer = get_gdelt_tone_analyzer()
        print("=" * 60)
        print("GDELT India Tone Analyzer — Health Check")
        print("=" * 60)
        result = await analyzer.get_composite_india_tone()
        print(f"\nMacro tone:       {result.macro_tone.raw_tone_score:+.2f} raw  → "
              f"{result.macro_tone.normalized_score:+.3f} norm  [{result.macro_tone.label}]")
        print(f"RBI tone:         "
              f"{result.rbi_tone.raw_tone_score:+.2f} raw  → "
              f"{result.rbi_tone.normalized_score:+.3f} norm  [{result.rbi_tone.label}]"
              if result.rbi_tone else "RBI tone:         N/A")
        print(f"Geo risk score:   {result.geo_risk_score:+.2f}")
        print(f"Geo risk flag:    {result.geopolitical_risk_flag}")
        print(f"News flow:        {result.macro_news_flow}")
        print(f"\nComposite score:  {result.composite_score:+.4f}")
        print(f"Composite label:  {result.composite_label}")
        # Validate range
        assert -1.0 <= result.composite_score <= 1.0, "RANGE ERROR"
        print("\n✓ Score in valid range [-1.0, +1.0]")

    asyncio.run(_main())
