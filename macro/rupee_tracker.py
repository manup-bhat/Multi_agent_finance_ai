"""
USD/INR Rupee Tracker
━━━━━━━━━━━━━━━━━━━━
USD/INR trend analysis and correlation with FII flows for India market impact.

India-specific context:
  - Rupee depreciation = bad for FIIs (reduces USD-denominated returns)
  - FII selling → rupee falls further (self-reinforcing loop)
  - RBI interventions: sell USD reserves to arrest sharp depreciation
  - Key level: INR 87–88 range is critical (Feb-Mar 2026 data)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

# USD/INR trends
RUPEE_APPRECIATING  = "APPRECIATING"
RUPEE_DEPRECIATING  = "DEPRECIATING"
RUPEE_STABLE        = "STABLE"

# Nifty impact signals
RUPEE_NIFTY_POSITIVE  = "POSITIVE"    # appreciation → FII inflow supportive
RUPEE_NIFTY_NEGATIVE  = "NEGATIVE"    # depreciation → FII outflow risk
RUPEE_NIFTY_NEUTRAL   = "NEUTRAL"

# Stable band: ±0.5% over the window = STABLE
STABLE_THRESHOLD_PCT = 0.005


@dataclass
class RupeeAnalysis:
    """USD/INR analysis result."""
    current_usdinr: float
    trend: str              # APPRECIATING / DEPRECIATING / STABLE
    change_pct_10d: float   # % change over 10 trading days
    fii_correlation_20d: float  # Pearson corr with FII net (if available)
    nifty_signal: str       # signal for Nifty impact
    rbi_intervention_risk: bool  # True if depreciation > 2% in 10 days
    description: str


def classify_rupee_trend(
    usdinr_series: pd.Series | list[float] | np.ndarray,
    window: int = 10,
) -> str:
    """
    Classify USD/INR trend over `window` trading days.

    Note on direction: USD/INR rising = weaker rupee = DEPRECIATING
                       USD/INR falling = stronger rupee = APPRECIATING

    STABLE: |change| < 0.5% over window.

    Returns:
        "APPRECIATING" / "DEPRECIATING" / "STABLE"
    """
    s = np.asarray(usdinr_series, dtype=float)
    if len(s) < 2:
        return RUPEE_STABLE

    lookback = s[-window:] if len(s) >= window else s
    if len(lookback) < 2:
        return RUPEE_STABLE

    pct_change = (lookback[-1] - lookback[0]) / lookback[0]

    if pct_change < -STABLE_THRESHOLD_PCT:
        return RUPEE_APPRECIATING   # USD/INR down = rupee stronger
    elif pct_change > STABLE_THRESHOLD_PCT:
        return RUPEE_DEPRECIATING   # USD/INR up = rupee weaker
    return RUPEE_STABLE


def compute_rupee_fii_correlation(
    usdinr_series: pd.Series | list[float] | np.ndarray,
    fii_net_series: pd.Series | list[float] | np.ndarray,
    window: int = 20,
) -> float:
    """
    Rolling Pearson correlation between USD/INR and FII net flows.

    Expected: negative correlation — when FIIs sell (neg FII), rupee falls (USD/INR rises).
    This means corr(USDINR, FII_net) should be negative.

    Returns:
        Pearson correlation coefficient (-1 to +1) over the last `window` days.
        Returns 0.0 if not enough data.
    """
    s1 = np.asarray(usdinr_series, dtype=float)
    s2 = np.asarray(fii_net_series, dtype=float)

    min_len = min(len(s1), len(s2))
    if min_len < 5:
        return 0.0

    s1_recent = s1[-min(window, min_len):]
    s2_recent = s2[-min(window, min_len):]

    if np.std(s1_recent) == 0 or np.std(s2_recent) == 0:
        return 0.0

    return float(np.corrcoef(s1_recent, s2_recent)[0, 1])


def rupee_impact_on_nifty_signal(trend: str) -> str:
    """
    Map USD/INR trend to Nifty impact signal.

    APPRECIATING rupee → FIIs retain value → positive for Nifty
    DEPRECIATING rupee → FIIs lose USD returns → negative for Nifty
    STABLE → neutral
    """
    return {
        RUPEE_APPRECIATING: RUPEE_NIFTY_POSITIVE,
        RUPEE_DEPRECIATING: RUPEE_NIFTY_NEGATIVE,
        RUPEE_STABLE:       RUPEE_NIFTY_NEUTRAL,
    }.get(trend, RUPEE_NIFTY_NEUTRAL)


def analyze_rupee(
    usdinr_series: pd.Series | list[float] | np.ndarray,
    fii_net_series: pd.Series | list[float] | np.ndarray | None = None,
    window: int = 10,
) -> RupeeAnalysis:
    """
    Full USD/INR analysis: trend + FII correlation + Nifty signal.
    """
    s = np.asarray(usdinr_series, dtype=float)
    current = float(s[-1]) if len(s) > 0 else 0.0
    trend = classify_rupee_trend(s, window)

    lookback = s[-window:] if len(s) >= window else s
    pct_change = round(
        (lookback[-1] - lookback[0]) / lookback[0] * 100, 4
    ) if len(lookback) >= 2 else 0.0

    fii_corr = 0.0
    if fii_net_series is not None:
        fii_corr = compute_rupee_fii_correlation(s, fii_net_series)

    nifty_signal = rupee_impact_on_nifty_signal(trend)
    rbi_risk = pct_change > 2.0  # >2% depreciation in 10 days → RBI likely to intervene

    if trend == RUPEE_DEPRECIATING:
        desc = (
            f"Rupee DEPRECIATING {abs(pct_change):.2f}% over {window}d "
            f"({current:.2f} USD/INR). FII outflow risk elevated."
        )
    elif trend == RUPEE_APPRECIATING:
        desc = (
            f"Rupee APPRECIATING {abs(pct_change):.2f}% over {window}d "
            f"({current:.2f} USD/INR). FII return supportive."
        )
    else:
        desc = f"Rupee STABLE ({current:.2f} USD/INR, {pct_change:+.2f}% over {window}d)."

    logger.info("rupee.analysis", trend=trend, pct_10d=pct_change, nifty_signal=nifty_signal)
    return RupeeAnalysis(
        current_usdinr=round(current, 2),
        trend=trend,
        change_pct_10d=pct_change,
        fii_correlation_20d=round(fii_corr, 4),
        nifty_signal=nifty_signal,
        rbi_intervention_risk=rbi_risk,
        description=desc,
    )
