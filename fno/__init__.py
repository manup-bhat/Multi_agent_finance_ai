"""
F&O (Futures & Options) Analysis Package — Phase 6
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Public API for all F&O analysis modules.
"""
from fno.greeks_calculator import (
    compute_greeks,
    compute_iv,
    compute_chain_greeks,
    GreeksResult,
    DEFAULT_RISK_FREE_RATE,
)
from fno.iv_analyzer import (
    compute_iv_rank,
    compute_iv_percentile,
    compute_iv_metrics,
    build_iv_surface,
    compute_iv_skew,
    IVMetrics,
)
from fno.pcr_analyzer import (
    compute_pcr,
    compute_volume_pcr,
    classify_pcr,
    analyze_pcr,
    compute_expiry_weighted_pcr,
    PCRResult,
)
from fno.oi_analyzer import (
    classify_oi_buildup,
    find_max_oi_strikes,
    compute_oi_change_pct,
    OIBuildup,
    MaxOIStrikeResult,
    LONG_BUILDUP,
    SHORT_BUILDUP,
    SHORT_COVERING,
    LONG_UNWINDING,
)
from fno.max_pain_calculator import (
    calculate_max_pain,
    compute_gravity_zone,
    is_in_gravity_zone,
    MaxPainResult,
)
from fno.strategy_simulator import (
    simulate_payoff,
    compute_breakevens,
    compute_max_profit_loss,
    analyze_strategy,
    build_straddle,
    build_strangle,
    build_iron_condor,
    build_bull_call_spread,
    build_bear_put_spread,
    StrategyPayoff,
)
from fno.fno_reporter import (
    build_fno_report,
    build_fno_summary_text,
)

__all__ = [
    "compute_greeks", "compute_iv", "compute_chain_greeks", "GreeksResult",
    "DEFAULT_RISK_FREE_RATE",
    "compute_iv_rank", "compute_iv_percentile", "compute_iv_metrics",
    "build_iv_surface", "compute_iv_skew", "IVMetrics",
    "compute_pcr", "compute_volume_pcr", "classify_pcr", "analyze_pcr",
    "compute_expiry_weighted_pcr", "PCRResult",
    "classify_oi_buildup", "find_max_oi_strikes", "compute_oi_change_pct",
    "OIBuildup", "MaxOIStrikeResult",
    "LONG_BUILDUP", "SHORT_BUILDUP", "SHORT_COVERING", "LONG_UNWINDING",
    "calculate_max_pain", "compute_gravity_zone", "is_in_gravity_zone",
    "MaxPainResult",
    "simulate_payoff", "compute_breakevens", "compute_max_profit_loss",
    "analyze_strategy", "build_straddle", "build_strangle",
    "build_iron_condor", "build_bull_call_spread", "build_bear_put_spread",
    "StrategyPayoff",
    "build_fno_report", "build_fno_summary_text",
]
