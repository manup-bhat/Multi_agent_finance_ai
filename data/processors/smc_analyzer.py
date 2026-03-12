"""
Smart Money Concepts (SMC) Analyzer
Wrapper around data/processors/smc_engine.py (pure Python, zero external deps).

Original: smartmoneyconcepts==0.0.26 — REMOVED (numba==0.58.1 conflicts with numpy>=2.4).
Replaced by: data/processors/smc_engine.py (pure Python).

Detects:
  - BOS (Break of Structure)
  - CHoCH (Change of Character)
  - Order Blocks (OB)
  - Fair Value Gaps (FVG)
  - Swing Highs / Lows
"""
import pandas as pd
import structlog

from data.processors.smc_engine import SMCEngine

logger = structlog.get_logger(__name__)


def detect_smc_zones(
    df: pd.DataFrame,
    swing_length: int = 5,
    close_idx: int = 1,
) -> dict:
    """
    Detect all SMC zones for a given OHLCV DataFrame.
    Delegates to SMCEngine (pure Python replacement for smartmoneyconcepts).

    Args:
        df: OHLCV DataFrame with columns: open, high, low, close, volume
            Index must be DatetimeIndex
        swing_length: Period for swing high/low detection (default 5)
        close_idx: Close type for BOS/CHoCH detection (kept for API compat)

    Returns:
        dict with keys:
          'current_bias': 'BULLISH' | 'BEARISH' | 'NEUTRAL'
          'order_blocks': list of OrderBlock dataclasses
          'fair_value_gaps': list of FairValueGap dataclasses
          'swing_highs': list of SwingPoint dataclasses
          'swing_lows': list of SwingPoint dataclasses
          'structure_events': list of StructureEvent dataclasses
          'nearest_ob_above': nearest bearish OB above price (resistance) or None
          'nearest_ob_below': nearest bullish OB below price (support) or None
          'summary': dict with counts
    """
    result = {
        "current_bias": "NEUTRAL",
        "order_blocks": None,
        "fair_value_gaps": None,
        "swing_highs": None,
        "swing_lows": None,
        "structure_events": None,
        "nearest_ob_above": None,
        "nearest_ob_below": None,
        "summary": {},
    }

    try:
        engine = SMCEngine(swing_length=swing_length)
        smc_result = engine.analyze(df)

        result["current_bias"] = smc_result.current_bias
        result["order_blocks"] = smc_result.order_blocks
        result["fair_value_gaps"] = smc_result.fair_value_gaps
        result["swing_highs"] = smc_result.swing_highs
        result["swing_lows"] = smc_result.swing_lows
        result["structure_events"] = smc_result.structure_events

        if smc_result.nearest_ob_above:
            ob = smc_result.nearest_ob_above
            result["nearest_ob_above"] = {
                "top": ob.top, "bottom": ob.bottom, "type": "BEARISH_OB",
            }
        if smc_result.nearest_ob_below:
            ob = smc_result.nearest_ob_below
            result["nearest_ob_below"] = {
                "top": ob.top, "bottom": ob.bottom, "type": "BULLISH_OB",
            }

        bos_count = sum(1 for e in smc_result.structure_events if e.event_type == "BOS")
        choch_count = sum(1 for e in smc_result.structure_events if e.event_type == "CHoCH")
        result["summary"] = {
            "bias": smc_result.current_bias,
            "bos_count": bos_count,
            "choch_count": choch_count,
            "ob_count": len(smc_result.order_blocks),
            "fvg_count": len(smc_result.fair_value_gaps),
        }

    except Exception as e:
        logger.warning("smc_analyzer.error", error=str(e))

    return result