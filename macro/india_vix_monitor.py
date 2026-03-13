"""
India VIX Monitor — Regime Classification & Mean Reversion Signals
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure analytics layer — no API calls. Receives pre-fetched VIX series.

Blueprint VIX thresholds (from config/constants.py):
  < 13     → COMPLACENCY  (sell premium strategies; market is too calm)
  13–18    → NORMAL       (all signals valid)
  18–25    → ELEVATED     (reduce position size by 30%)
  ≥ 25     → HIGH         (CIRCUIT BREAKER: override all verdicts to HOLD)
  ≥ 30     → CRISIS       (force CASH/GOLD only)

Mean Reversion:
  VIX spikes are temporary. When VIX z-score > +2, it typically reverts.
  This is a contrarian buy signal for Nifty (fear → opportunity).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass
from typing import Optional

from config.constants import (
    VIX_COMPLACENCY_MAX,
    VIX_NORMAL_MAX,
    VIX_ELEVATED_MAX,
    VIX_CIRCUIT_BREAKER,
    VIX_CRISIS_THRESHOLD,
)

logger = structlog.get_logger(__name__)

# VIX regime labels
VIX_COMPLACENCY = "COMPLACENCY"
VIX_NORMAL      = "NORMAL"
VIX_ELEVATED    = "ELEVATED"
VIX_HIGH        = "HIGH"
VIX_CRISIS      = "CRISIS"

# Position size multipliers by regime (blueprint)
_SIZE_MULTIPLIERS = {
    VIX_COMPLACENCY: 1.0,
    VIX_NORMAL:      1.0,
    VIX_ELEVATED:    0.7,
    VIX_HIGH:        0.0,
    VIX_CRISIS:      0.0,
}


@dataclass
class VIXSignal:
    """VIX regime + mean reversion signal."""
    current_vix: float
    regime: str
    z_score_20d: float
    is_circuit_breaker: bool
    is_crisis: bool
    is_extreme_fear: bool      # z-score > +2 = potential contrarian buy
    is_complacency: bool       # z-score < -1.5 = sell premium opportunity
    position_size_multiplier: float
    signal: str                # "CIRCUIT_BREAKER" / "CRISIS" / "SELL_PREMIUM" / "BUY_FEAR" / "NORMAL"
    description: str


def classify_vix_regime(vix: float) -> str:
    """
    Classify India VIX into regime using blueprint thresholds.

    Thresholds (from config/constants.py):
      < 13   = COMPLACENCY
      13-18  = NORMAL
      18-25  = ELEVATED
      25-30  = HIGH (circuit breaker)
      >= 30  = CRISIS

    NOTE: VIX_ELEVATED_MAX = 25 and VIX_CIRCUIT_BREAKER = 25 are the same
    constant but represent different boundaries: ELEVATED goes UP TO (not incl)
    circuit breaker, which is >= 25.

    Returns:
        "COMPLACENCY" / "NORMAL" / "ELEVATED" / "HIGH" / "CRISIS"
    """
    # Check from highest to lowest threshold
    if vix >= VIX_CRISIS_THRESHOLD:    # >= 30
        return VIX_CRISIS
    if vix >= VIX_CIRCUIT_BREAKER:     # >= 25
        return VIX_HIGH
    if vix >= VIX_NORMAL_MAX:          # >= 18 (ELEVATED = 18 to <25)
        return VIX_ELEVATED
    if vix >= VIX_COMPLACENCY_MAX:     # >= 13 (NORMAL = 13 to <18)
        return VIX_NORMAL
    return VIX_COMPLACENCY             # < 13


def compute_position_size_multiplier(vix: float) -> float:
    """
    Position size multiplier based on VIX regime (blueprint rule):
      COMPLACENCY / NORMAL → 1.0 (full size)
      ELEVATED             → 0.7 (reduce 30%)
      HIGH / CRISIS        → 0.0 (no new positions)
    """
    regime = classify_vix_regime(vix)
    return _SIZE_MULTIPLIERS.get(regime, 0.7)


def compute_vix_zscore(
    vix_series: pd.Series | list[float] | np.ndarray,
    window: int = 20,
) -> pd.Series:
    """
    Compute rolling z-score of VIX for mean reversion signal.

    z = (VIX - rolling_mean) / rolling_std

    Returns:
        pd.Series of z-scores (same index as input if pd.Series)
    """
    s = pd.Series(vix_series, dtype=float)
    rolling_mean = s.rolling(window=window, min_periods=max(2, window // 2)).mean()
    rolling_std  = s.rolling(window=window, min_periods=max(2, window // 2)).std()
    rolling_std  = rolling_std.replace(0, np.nan).fillna(1.0)
    return (s - rolling_mean) / rolling_std


def detect_vix_reversion_signal(
    vix_series: pd.Series | list[float] | np.ndarray,
    window: int = 20,
) -> VIXSignal:
    """
    Full VIX analysis: regime + z-score + mean reversion signal.

    Args:
        vix_series: Historical VIX values (most recent is LAST)
        window: Rolling window for z-score (default 20 trading days)

    Returns:
        VIXSignal dataclass with all derived values
    """
    s = pd.Series(vix_series, dtype=float)
    current_vix = float(s.iloc[-1])
    regime = classify_vix_regime(current_vix)

    zscore_series = compute_vix_zscore(s, window)
    current_z = float(zscore_series.iloc[-1]) if not np.isnan(zscore_series.iloc[-1]) else 0.0

    is_circuit = current_vix >= VIX_CIRCUIT_BREAKER
    is_crisis  = current_vix >= VIX_CRISIS_THRESHOLD
    is_extreme_fear   = current_z > 2.0   # high fear = contrarian buy signal
    is_complacency_z  = current_z < -1.5  # low fear = sell premium signal

    if is_crisis:
        signal = "CRISIS"
        desc = "CRISIS: Force CASH/GOLD only. All equity positions closed."
    elif is_circuit:
        signal = "CIRCUIT_BREAKER"
        desc = "CIRCUIT BREAKER (VIX ≥ 25): Override all verdicts to HOLD."
    elif is_extreme_fear:
        signal = "BUY_FEAR"
        desc = f"Extreme fear spike (z={current_z:.1f}). Contrarian BUY opportunity. VIX {regime}."
    elif is_complacency_z:
        signal = "SELL_PREMIUM"
        desc = f"Low VIX complacency (z={current_z:.1f}). Sell premium strategies active."
    else:
        signal = "NORMAL"
        desc = f"VIX regime: {regime}. z-score: {current_z:.2f}. Normal trading."

    multiplier = compute_position_size_multiplier(current_vix)

    logger.info(
        "vix.signal",
        vix=current_vix, regime=regime, z=round(current_z, 2), signal=signal,
    )

    return VIXSignal(
        current_vix=round(current_vix, 2),
        regime=regime,
        z_score_20d=round(current_z, 4),
        is_circuit_breaker=is_circuit,
        is_crisis=is_crisis,
        is_extreme_fear=is_extreme_fear,
        is_complacency=is_complacency_z,
        position_size_multiplier=multiplier,
        signal=signal,
        description=desc,
    )
