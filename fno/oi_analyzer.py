"""
Open Interest Analyzer
━━━━━━━━━━━━━━━━━━━━━
OI buildup classification, max OI strike detection, and OI change analysis.

Four-quadrant OI interpretation (standard NSE derivatives theory):
  Price ↑ + OI ↑ = LONG_BUILDUP     (fresh longs, bullish)
  Price ↓ + OI ↑ = SHORT_BUILDUP    (fresh shorts, bearish)
  Price ↑ + OI ↓ = SHORT_COVERING   (shorts exit, mildly bullish)
  Price ↓ + OI ↓ = LONG_UNWINDING   (longs exit, mildly bearish)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass
from typing import Optional

from config.constants import PCR_BULLISH_THRESHOLD

logger = structlog.get_logger(__name__)


# OI buildup quadrants
LONG_BUILDUP = "LONG_BUILDUP"
SHORT_BUILDUP = "SHORT_BUILDUP"
SHORT_COVERING = "SHORT_COVERING"
LONG_UNWINDING = "LONG_UNWINDING"


@dataclass
class OIBuildup:
    """OI buildup classification result."""
    classification: str   # LONG_BUILDUP / SHORT_BUILDUP / SHORT_COVERING / LONG_UNWINDING
    price_change: float
    oi_change: float
    is_bullish: bool
    description: str


@dataclass
class MaxOIStrikeResult:
    """Max OI strikes (support/resistance levels)."""
    max_ce_oi_strike: float   # highest call OI = resistance
    max_pe_oi_strike: float   # highest put OI = support
    max_ce_oi: float
    max_pe_oi: float
    ce_oi_at_strike: dict     # top 5 CE OI strikes
    pe_oi_at_strike: dict     # top 5 PE OI strikes


def classify_oi_buildup(
    price_change: float,
    oi_change: float,
) -> OIBuildup:
    """
    Classify OI buildup using the four-quadrant model.

    Args:
        price_change: Price change (positive = up, negative = down)
        oi_change: OI change (positive = increase, negative = decrease)

    Returns:
        OIBuildup with classification and description
    """
    if price_change > 0 and oi_change > 0:
        return OIBuildup(
            classification=LONG_BUILDUP,
            price_change=price_change,
            oi_change=oi_change,
            is_bullish=True,
            description="Fresh longs entering — bullish continuation expected",
        )
    elif price_change < 0 and oi_change > 0:
        return OIBuildup(
            classification=SHORT_BUILDUP,
            price_change=price_change,
            oi_change=oi_change,
            is_bullish=False,
            description="Fresh shorts entering — bearish continuation expected",
        )
    elif price_change > 0 and oi_change < 0:
        return OIBuildup(
            classification=SHORT_COVERING,
            price_change=price_change,
            oi_change=oi_change,
            is_bullish=True,
            description="Short positions exiting — mildly bullish, may lack conviction",
        )
    else:  # price_change <= 0 and oi_change <= 0
        return OIBuildup(
            classification=LONG_UNWINDING,
            price_change=price_change,
            oi_change=oi_change,
            is_bullish=False,
            description="Long positions exiting — mildly bearish, exhaustion",
        )


def find_max_oi_strikes(
    chain_df: pd.DataFrame,
    option_type_col: str = "option_type",
    strike_col: str = "strike_price",
    oi_col: str = "open_interest",
    top_n: int = 5,
) -> MaxOIStrikeResult:
    """
    Find strikes with highest Call OI (resistance) and Put OI (support).

    Returns:
        MaxOIStrikeResult with support/resistance levels
    """
    calls = chain_df[chain_df[option_type_col].isin(["CE", "C", "c"])].copy()
    puts = chain_df[chain_df[option_type_col].isin(["PE", "P", "p"])].copy()

    # Call OI = resistance levels
    ce_by_strike = calls.groupby(strike_col)[oi_col].sum().sort_values(ascending=False)
    pe_by_strike = puts.groupby(strike_col)[oi_col].sum().sort_values(ascending=False)

    max_ce_strike = float(ce_by_strike.index[0]) if len(ce_by_strike) > 0 else 0.0
    max_pe_strike = float(pe_by_strike.index[0]) if len(pe_by_strike) > 0 else 0.0
    max_ce_oi = float(ce_by_strike.iloc[0]) if len(ce_by_strike) > 0 else 0.0
    max_pe_oi = float(pe_by_strike.iloc[0]) if len(pe_by_strike) > 0 else 0.0

    return MaxOIStrikeResult(
        max_ce_oi_strike=max_ce_strike,
        max_pe_oi_strike=max_pe_strike,
        max_ce_oi=max_ce_oi,
        max_pe_oi=max_pe_oi,
        ce_oi_at_strike=ce_by_strike.head(top_n).to_dict(),
        pe_oi_at_strike=pe_by_strike.head(top_n).to_dict(),
    )


def compute_oi_change_pct(
    chain_df: pd.DataFrame,
    option_type_col: str = "option_type",
    strike_col: str = "strike_price",
    oi_col: str = "open_interest",
    change_col: str = "change_in_open_interest",
) -> pd.DataFrame:
    """
    Compute OI change percentage per strike.

    Returns:
        DataFrame with strike, option_type, oi, change, change_pct
    """
    if change_col not in chain_df.columns:
        logger.warning("oi_analyzer.no_change_col", col=change_col)
        return chain_df[[strike_col, option_type_col, oi_col]].copy()

    df = chain_df[[strike_col, option_type_col, oi_col, change_col]].copy()
    prev_oi = df[oi_col] - df[change_col]
    df["oi_change_pct"] = np.where(
        prev_oi > 0,
        (df[change_col] / prev_oi * 100).round(2),
        0.0,
    )
    return df
