"""
Put-Call Ratio Analyzer
━━━━━━━━━━━━━━━━━━━━━━
OI-based and volume-based PCR, expiry-weighted PCR, and signal classification.

Blueprint thresholds (from config/constants.py):
  PCR > 1.2 → Bullish (heavy put writing = support)
  PCR < 0.8 → Bearish (heavy call writing = resistance)
  PCR 0.8–1.2 → Neutral
  PCR > 1.5 → Extreme (likely market bottom)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass

from config.constants import (
    PCR_BULLISH_THRESHOLD,
    PCR_BEARISH_THRESHOLD,
    PCR_EXTREME_HIGH,
)

logger = structlog.get_logger(__name__)


@dataclass
class PCRResult:
    """Put-Call Ratio analysis result."""
    oi_pcr: float          # OI-based PCR
    volume_pcr: float      # Volume-based PCR
    signal: str            # "BULLISH" / "BEARISH" / "NEUTRAL" / "EXTREME_BULLISH"
    put_oi: float          # Total put OI
    call_oi: float         # Total call OI
    put_volume: float      # Total put volume
    call_volume: float     # Total call volume


def compute_pcr(
    chain_df: pd.DataFrame,
    option_type_col: str = "option_type",
    oi_col: str = "open_interest",
) -> float:
    """
    Compute OI-based Put-Call Ratio.
    PCR = Total Put OI / Total Call OI.
    Returns 1.0 if call OI is zero.
    """
    puts = chain_df[chain_df[option_type_col].isin(["PE", "P", "p"])]
    calls = chain_df[chain_df[option_type_col].isin(["CE", "C", "c"])]

    put_oi = puts[oi_col].sum()
    call_oi = calls[oi_col].sum()

    if call_oi == 0:
        return 1.0
    return round(float(put_oi / call_oi), 4)


def compute_volume_pcr(
    chain_df: pd.DataFrame,
    option_type_col: str = "option_type",
    volume_col: str = "total_traded_volume",
) -> float:
    """
    Compute volume-based Put-Call Ratio.
    Volume PCR = Total Put Volume / Total Call Volume.
    """
    puts = chain_df[chain_df[option_type_col].isin(["PE", "P", "p"])]
    calls = chain_df[chain_df[option_type_col].isin(["CE", "C", "c"])]

    put_vol = puts[volume_col].sum() if volume_col in puts.columns else 0
    call_vol = calls[volume_col].sum() if volume_col in calls.columns else 0

    if call_vol == 0:
        return 1.0
    return round(float(put_vol / call_vol), 4)


def classify_pcr(pcr_value: float) -> str:
    """
    Classify PCR signal using blueprint thresholds.

    Returns: "EXTREME_BULLISH" / "BULLISH" / "BEARISH" / "NEUTRAL"
    """
    if pcr_value >= PCR_EXTREME_HIGH:
        return "EXTREME_BULLISH"
    elif pcr_value >= PCR_BULLISH_THRESHOLD:
        return "BULLISH"
    elif pcr_value <= PCR_BEARISH_THRESHOLD:
        return "BEARISH"
    return "NEUTRAL"


def analyze_pcr(
    chain_df: pd.DataFrame,
    option_type_col: str = "option_type",
    oi_col: str = "open_interest",
    volume_col: str = "total_traded_volume",
) -> PCRResult:
    """
    Full PCR analysis: OI-based + volume-based + signal classification.
    """
    puts = chain_df[chain_df[option_type_col].isin(["PE", "P", "p"])]
    calls = chain_df[chain_df[option_type_col].isin(["CE", "C", "c"])]

    put_oi = float(puts[oi_col].sum()) if oi_col in puts.columns else 0.0
    call_oi = float(calls[oi_col].sum()) if oi_col in calls.columns else 0.0
    put_vol = float(puts[volume_col].sum()) if volume_col in puts.columns else 0.0
    call_vol = float(calls[volume_col].sum()) if volume_col in calls.columns else 0.0

    oi_pcr = round(put_oi / call_oi, 4) if call_oi > 0 else 1.0
    vol_pcr = round(put_vol / call_vol, 4) if call_vol > 0 else 1.0
    signal = classify_pcr(oi_pcr)

    return PCRResult(
        oi_pcr=oi_pcr,
        volume_pcr=vol_pcr,
        signal=signal,
        put_oi=put_oi,
        call_oi=call_oi,
        put_volume=put_vol,
        call_volume=call_vol,
    )


def compute_expiry_weighted_pcr(
    chains_by_expiry: dict[str, pd.DataFrame],
    days_to_expiry: dict[str, int],
    option_type_col: str = "option_type",
    oi_col: str = "open_interest",
) -> float:
    """
    Compute PCR weighted by inverse days to expiry.
    Nearer expiries have more weight (more gamma, more relevance).

    Args:
        chains_by_expiry: {expiry_str: chain_df}
        days_to_expiry: {expiry_str: days_remaining}

    Returns:
        Weighted PCR (float)
    """
    total_weight = 0.0
    weighted_pcr = 0.0

    for expiry, chain in chains_by_expiry.items():
        dte = days_to_expiry.get(expiry, 30)
        if dte <= 0:
            dte = 1
        weight = 1.0 / dte  # nearer expiry = higher weight
        pcr = compute_pcr(chain, option_type_col, oi_col)
        weighted_pcr += pcr * weight
        total_weight += weight

    if total_weight == 0:
        return 1.0
    return round(weighted_pcr / total_weight, 4)
