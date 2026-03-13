"""
Macro Analysis Package — Phase 7
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Public API for all macro analysis modules.
"""
from macro.india_vix_monitor import (
    classify_vix_regime,
    compute_vix_zscore,
    compute_position_size_multiplier,
    detect_vix_reversion_signal,
    VIXSignal,
    VIX_COMPLACENCY, VIX_NORMAL, VIX_ELEVATED, VIX_HIGH, VIX_CRISIS,
)
from macro.fii_dii_tracker import (
    compute_flow_zscore,
    classify_consensus,
    detect_sell_streak,
    compute_cumulative_flow,
    classify_trend,
    build_flow_report,
    FIIDIIReport,
    CONSENSUS_STRONG_BULL, CONSENSUS_STRONG_BEAR,
    CONSENSUS_FII_BULL_DII_BEAR, CONSENSUS_DII_BULL_FII_BEAR,
)
from macro.rupee_tracker import (
    classify_rupee_trend,
    compute_rupee_fii_correlation,
    rupee_impact_on_nifty_signal,
    analyze_rupee,
    RupeeAnalysis,
    RUPEE_APPRECIATING, RUPEE_DEPRECIATING, RUPEE_STABLE,
)
from macro.crude_tracker import (
    classify_crude_regime,
    classify_crude_from_price,
    crude_cad_impact_signal,
    compute_crude_nifty_correlation,
    analyze_crude,
    CrudeAnalysis,
    CRUDE_SUPPORTIVE, CRUDE_NEUTRAL, CRUDE_INFLATIONARY,
)
from macro.global_cues_aggregator import (
    compute_sgx_gap,
    classify_global_sentiment,
    expected_nifty_open,
    build_global_cues_report,
    GlobalCuesReport,
    RISK_ON, RISK_OFF, MIXED,
)
from macro.event_impact_analyzer import (
    compute_event_volatility_multiplier,
    get_event_trading_rules,
    build_event_impact_report,
    EventImpactReport,
)

__all__ = [
    # VIX
    "classify_vix_regime", "compute_vix_zscore", "compute_position_size_multiplier",
    "detect_vix_reversion_signal", "VIXSignal",
    "VIX_COMPLACENCY", "VIX_NORMAL", "VIX_ELEVATED", "VIX_HIGH", "VIX_CRISIS",
    # FII/DII
    "compute_flow_zscore", "classify_consensus", "detect_sell_streak",
    "compute_cumulative_flow", "classify_trend", "build_flow_report", "FIIDIIReport",
    "CONSENSUS_STRONG_BULL", "CONSENSUS_STRONG_BEAR",
    "CONSENSUS_FII_BULL_DII_BEAR", "CONSENSUS_DII_BULL_FII_BEAR",
    # Rupee
    "classify_rupee_trend", "compute_rupee_fii_correlation",
    "rupee_impact_on_nifty_signal", "analyze_rupee", "RupeeAnalysis",
    "RUPEE_APPRECIATING", "RUPEE_DEPRECIATING", "RUPEE_STABLE",
    # Crude
    "classify_crude_regime", "classify_crude_from_price", "crude_cad_impact_signal",
    "compute_crude_nifty_correlation", "analyze_crude", "CrudeAnalysis",
    "CRUDE_SUPPORTIVE", "CRUDE_NEUTRAL", "CRUDE_INFLATIONARY",
    # Global cues
    "compute_sgx_gap", "classify_global_sentiment", "expected_nifty_open",
    "build_global_cues_report", "GlobalCuesReport", "RISK_ON", "RISK_OFF", "MIXED",
    # Event impact
    "compute_event_volatility_multiplier", "get_event_trading_rules",
    "build_event_impact_report", "EventImpactReport",
]
