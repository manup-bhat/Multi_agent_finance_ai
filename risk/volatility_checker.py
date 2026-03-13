"""
Volatility Checker — VIX-based position sizing
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Re-exports from macro/india_vix_monitor with risk-module framing.
"""
from __future__ import annotations
from macro.india_vix_monitor import (
    classify_vix_regime,
    compute_position_size_multiplier,
    detect_vix_reversion_signal,
    VIXSignal,
    VIX_COMPLACENCY, VIX_NORMAL, VIX_ELEVATED, VIX_HIGH, VIX_CRISIS,
)

__all__ = [
    "classify_vix_regime",
    "compute_position_size_multiplier",
    "detect_vix_reversion_signal",
    "VIXSignal",
    "VIX_COMPLACENCY", "VIX_NORMAL", "VIX_ELEVATED", "VIX_HIGH", "VIX_CRISIS",
    "get_position_size_for_regime",
]


def get_position_size_for_regime(vix: float, base_size: float = 1.0) -> float:
    """
    Compute position size as a fraction of the base position.
    Applies VIX regime multiplier to base.
    """
    return base_size * compute_position_size_multiplier(vix)
