"""
FII/DII Flow Tracker — Analytics Layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure analytics on pre-fetched FII/DII DataFrames.
Data comes from NSELibClient.get_fii_dii() / get_fii_dii_zscore().

Blueprint thresholds (config/constants.py):
  FII sell streak alert: 7 consecutive days
  FII sell alert: ₹2000 crore net sell in a single day
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass
from typing import Optional

from config.constants import (
    FII_SELL_STREAK_ALERT_DAYS,
    FII_SELL_ALERT_AMOUNT_CR,
)

logger = structlog.get_logger(__name__)

# Consensus signal constants
CONSENSUS_STRONG_BULL       = "STRONG_BULL"
CONSENSUS_STRONG_BEAR       = "STRONG_BEAR"
CONSENSUS_FII_BULL_DII_BEAR = "FII_BULL_DII_BEAR"
CONSENSUS_DII_BULL_FII_BEAR = "DII_BULL_FII_BEAR"


@dataclass
class FIIDIIReport:
    """Aggregated FII/DII analysis result."""
    latest_fii_net: float       # INR crore
    latest_dii_net: float       # INR crore
    fii_zscore_5d: float        # 5-day rolling z-score
    dii_zscore_5d: float
    consensus: str              # STRONG_BULL / STRONG_BEAR / ...
    sell_streak_days: int       # consecutive FII sell days
    sell_streak_alert: bool     # True if streak >= 7 days
    large_sell_alert: bool      # True if day sell > ₹2000cr
    cumulative_fii_20d: float   # 20-day running FII net
    cumulative_dii_20d: float
    trend: str                  # "ACCUMULATING" / "DISTRIBUTING" / "NEUTRAL"


def compute_flow_zscore(
    series: pd.Series | list[float] | np.ndarray,
    window: int = 5,
) -> pd.Series:
    """
    Rolling Z-score for FII/DII net flows.
    z = (today_flow - rolling_mean) / rolling_std

    Blueprint: 5-day window matches NSE settlement cycle.
    """
    s = pd.Series(series, dtype=float)
    mu  = s.rolling(window=window, min_periods=2).mean()
    std = s.rolling(window=window, min_periods=2).std().replace(0, 1.0)
    return (s - mu) / std


def classify_consensus(fii_net: float, dii_net: float) -> str:
    """
    Four-quadrant FII/DII consensus classification.

    FII+, DII+ → STRONG_BULL  (institutional unanimity — most bullish)
    FII-, DII- → STRONG_BEAR  (institutional unanimity — most bearish)
    FII+, DII- → FII_BULL_DII_BEAR (FIIs buying, DIIs selling — watch closely)
    FII-, DII+ → DII_BULL_FII_BEAR (FIIs selling, DIIs supporting — DII floor)
    """
    if fii_net > 0 and dii_net > 0:
        return CONSENSUS_STRONG_BULL
    elif fii_net < 0 and dii_net < 0:
        return CONSENSUS_STRONG_BEAR
    elif fii_net > 0:
        return CONSENSUS_FII_BULL_DII_BEAR
    else:
        return CONSENSUS_DII_BULL_FII_BEAR


def detect_sell_streak(
    fii_net_series: pd.Series | list[float] | np.ndarray,
) -> int:
    """
    Count consecutive days of FII net selling (< 0) from the most recent date.

    Blueprint alert: 7+ consecutive sell days = warning signal (controlled panic).

    Returns:
        Number of consecutive sell days (0 if most recent day is positive).
    """
    arr = np.asarray(fii_net_series, dtype=float)
    streak = 0
    for val in reversed(arr):
        if val < 0:
            streak += 1
        else:
            break
    return streak


def compute_cumulative_flow(
    net_series: pd.Series | list[float] | np.ndarray,
    lookback: int = 20,
) -> float:
    """
    Sum of net flows over the last `lookback` trading days.
    Positive = net accumulation, Negative = net distribution.
    """
    arr = np.asarray(net_series, dtype=float)
    recent = arr[-lookback:] if len(arr) >= lookback else arr
    return float(np.sum(recent))


def classify_trend(cumulative_flow: float, threshold_cr: float = 5_000.0) -> str:
    """
    Classify directional trend based on cumulative flow.
    > +5000 cr net → ACCUMULATING
    < -5000 cr net → DISTRIBUTING
    Otherwise → NEUTRAL
    """
    if cumulative_flow > threshold_cr:
        return "ACCUMULATING"
    elif cumulative_flow < -threshold_cr:
        return "DISTRIBUTING"
    return "NEUTRAL"


def build_flow_report(
    df: pd.DataFrame,
    fii_net_col: str = "fii_net_value",
    dii_net_col: str = "dii_net_value",
) -> FIIDIIReport:
    """
    Build a complete FII/DII analysis report from a raw DataFrame.

    Expected columns in df: fii_net_value, dii_net_value

    Returns:
        FIIDIIReport dataclass
    """
    if fii_net_col not in df.columns or dii_net_col not in df.columns:
        raise ValueError(
            f"DataFrame must have columns '{fii_net_col}' and '{dii_net_col}'. "
            f"Got: {list(df.columns)}"
        )

    fii_net = df[fii_net_col].dropna()
    dii_net = df[dii_net_col].dropna()

    latest_fii = float(fii_net.iloc[-1]) if len(fii_net) > 0 else 0.0
    latest_dii = float(dii_net.iloc[-1]) if len(dii_net) > 0 else 0.0

    fii_z_series = compute_flow_zscore(fii_net, window=5)
    dii_z_series = compute_flow_zscore(dii_net, window=5)
    fii_z = float(fii_z_series.iloc[-1]) if not np.isnan(fii_z_series.iloc[-1]) else 0.0
    dii_z = float(dii_z_series.iloc[-1]) if not np.isnan(dii_z_series.iloc[-1]) else 0.0

    streak = detect_sell_streak(fii_net.values)
    cum_fii = compute_cumulative_flow(fii_net.values, lookback=20)
    cum_dii = compute_cumulative_flow(dii_net.values, lookback=20)
    consensus = classify_consensus(latest_fii, latest_dii)
    trend = classify_trend(cum_fii)

    report = FIIDIIReport(
        latest_fii_net=round(latest_fii, 2),
        latest_dii_net=round(latest_dii, 2),
        fii_zscore_5d=round(fii_z, 4),
        dii_zscore_5d=round(dii_z, 4),
        consensus=consensus,
        sell_streak_days=streak,
        sell_streak_alert=streak >= FII_SELL_STREAK_ALERT_DAYS,
        large_sell_alert=latest_fii < -FII_SELL_ALERT_AMOUNT_CR,
        cumulative_fii_20d=round(cum_fii, 2),
        cumulative_dii_20d=round(cum_dii, 2),
        trend=trend,
    )
    logger.info(
        "fii_dii.report",
        fii_net=latest_fii, dii_net=latest_dii,
        consensus=consensus, streak=streak, trend=trend,
    )
    return report
