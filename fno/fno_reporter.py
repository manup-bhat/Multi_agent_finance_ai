"""
F&O Reporter — Structured Summary for Agent Consumption
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Combines all F&O analysis into a single report dict and plain-text summary
for the Orchestrator agent to consume.

Aggregates:
  - PCR signal
  - Max Pain + gravity zone
  - OI buildup classification
  - IV Rank / Percentile
  - Top support/resistance (max OI) strikes
  - Strategy suggestions based on IV/PCR/Regime
"""
from __future__ import annotations

import structlog
import numpy as np
import pandas as pd
from typing import Optional

from fno.pcr_analyzer import analyze_pcr, PCRResult
from fno.oi_analyzer import find_max_oi_strikes, classify_oi_buildup, MaxOIStrikeResult
from fno.max_pain_calculator import calculate_max_pain, compute_gravity_zone, MaxPainResult
from fno.iv_analyzer import compute_iv_metrics, IVMetrics

logger = structlog.get_logger(__name__)


def build_fno_report(
    chain_df: pd.DataFrame,
    spot: float,
    price_change: float = 0.0,
    oi_change: float = 0.0,
    current_iv: float = 0.0,
    iv_history: Optional[list[float]] = None,
    expiry_label: str = "",
) -> dict:
    """
    Build a comprehensive F&O analysis report.

    Args:
        chain_df:      Option chain DataFrame with strike_price, option_type, open_interest
        spot:          Current spot/underlying price
        price_change:  Recent price change (for OI buildup classification)
        oi_change:     Recent aggregate OI change
        current_iv:    Current ATM IV (annualised)
        iv_history:    Historical IV values for rank/percentile
        expiry_label:  Expiry date label (e.g. "27-Mar-2026")

    Returns:
        dict with all F&O metrics
    """
    # ── PCR Analysis ───────────────────────────────────────────
    pcr_result = analyze_pcr(chain_df)

    # ── Max Pain ───────────────────────────────────────────────
    max_pain_strike, total_pain = calculate_max_pain(chain_df)
    gravity = compute_gravity_zone(max_pain_strike, spot)
    gravity.total_pain_at_max = total_pain

    # ── OI Analysis ────────────────────────────────────────────
    max_oi = find_max_oi_strikes(chain_df)
    oi_buildup = classify_oi_buildup(price_change, oi_change)

    # ── IV Analysis ────────────────────────────────────────────
    iv_metrics: Optional[IVMetrics] = None
    if current_iv > 0 and iv_history:
        iv_metrics = compute_iv_metrics(current_iv, iv_history)

    report = {
        "symbol_spot": spot,
        "expiry": expiry_label,

        # PCR
        "pcr_oi": pcr_result.oi_pcr,
        "pcr_volume": pcr_result.volume_pcr,
        "pcr_signal": pcr_result.signal,
        "total_put_oi": pcr_result.put_oi,
        "total_call_oi": pcr_result.call_oi,

        # Max Pain
        "max_pain_strike": max_pain_strike,
        "gravity_zone": {
            "low": gravity.gravity_zone_low,
            "high": gravity.gravity_zone_high,
        },
        "spot_in_gravity_zone": gravity.spot_in_gravity_zone,
        "pin_risk": gravity.pin_risk,

        # OI Support/Resistance
        "resistance_strike": max_oi.max_ce_oi_strike,
        "support_strike": max_oi.max_pe_oi_strike,
        "resistance_oi": max_oi.max_ce_oi,
        "support_oi": max_oi.max_pe_oi,
        "top_ce_oi_strikes": max_oi.ce_oi_at_strike,
        "top_pe_oi_strikes": max_oi.pe_oi_at_strike,

        # OI Buildup
        "oi_buildup": oi_buildup.classification,
        "oi_buildup_description": oi_buildup.description,
        "oi_is_bullish": oi_buildup.is_bullish,

        # IV (if available)
        "iv_rank": iv_metrics.iv_rank if iv_metrics else None,
        "iv_percentile": iv_metrics.iv_percentile if iv_metrics else None,
        "iv_signal": iv_metrics.signal if iv_metrics else None,
        "iv_52w_high": iv_metrics.iv_high_52w if iv_metrics else None,
        "iv_52w_low": iv_metrics.iv_low_52w if iv_metrics else None,
    }

    logger.info(
        "fno.report_built",
        pcr=pcr_result.oi_pcr,
        max_pain=max_pain_strike,
        pin_risk=gravity.pin_risk,
        resistance=max_oi.max_ce_oi_strike,
        support=max_oi.max_pe_oi_strike,
    )
    return report


def build_fno_summary_text(report: dict) -> str:
    """
    Convert F&O report dict into a plain-text summary for LLM agent consumption.
    """
    lines = [
        f"F&O ANALYSIS — Spot: ₹{report['symbol_spot']:,.2f}",
        f"Expiry: {report.get('expiry', 'N/A')}",
        "",
        f"PCR (OI): {report['pcr_oi']:.2f}  Signal: {report['pcr_signal']}",
        f"  Put OI: {report['total_put_oi']:,.0f}  |  Call OI: {report['total_call_oi']:,.0f}",
        "",
        f"Max Pain: ₹{report['max_pain_strike']:,.0f}  "
        f"(Gravity: ₹{report['gravity_zone']['low']:,.0f} – ₹{report['gravity_zone']['high']:,.0f})",
        f"  Pin Risk: {report['pin_risk']}  |  In Gravity Zone: {report['spot_in_gravity_zone']}",
        "",
        f"Support (Max PE OI): ₹{report['support_strike']:,.0f}  "
        f"(OI: {report['support_oi']:,.0f})",
        f"Resistance (Max CE OI): ₹{report['resistance_strike']:,.0f}  "
        f"(OI: {report['resistance_oi']:,.0f})",
        "",
        f"OI Buildup: {report['oi_buildup']}",
        f"  {report['oi_buildup_description']}",
    ]

    if report.get("iv_rank") is not None:
        lines.extend([
            "",
            f"IV Rank: {report['iv_rank']:.1f}%  |  IV Percentile: {report['iv_percentile']:.1f}%",
            f"IV Signal: {report['iv_signal']}  "
            f"(52W: {report['iv_52w_low']:.2f} – {report['iv_52w_high']:.2f})",
        ])

    return "\n".join(lines)
