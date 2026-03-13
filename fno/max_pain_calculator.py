"""
Max Pain Calculator
━━━━━━━━━━━━━━━━━━
Finds the strike at which total option writer losses are minimized (Max Pain).
Includes gravity zone detection (±1% from max pain = pin risk near expiry).

Theory: price gravitates toward max pain as expiry approaches because option
writers (mostly institutional) hedge in real-time, creating a self-fulfilling effect.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

# Default gravity zone: ±1% from max pain (India weekly expiry convention)
DEFAULT_GRAVITY_PCT = 0.01


@dataclass
class MaxPainResult:
    """Max Pain calculation result."""
    max_pain_strike: float
    total_pain_at_max: float      # INR total writer profit at max pain
    gravity_zone_low: float
    gravity_zone_high: float
    spot_in_gravity_zone: bool
    pin_risk: str                 # "HIGH" / "MODERATE" / "LOW"


def _compute_pain_at_strike(
    chain_df: pd.DataFrame,
    test_strike: float,
    strike_col: str = "strike_price",
    option_type_col: str = "option_type",
    oi_col: str = "open_interest",
) -> float:
    """
    Compute total option-buyer loss (= option-writer profit) if the
    underlying expires at `test_strike`.

    For each CE: buyer loss = max(0, spot - strike) * OI  (ITM calls hurt buyers)
    For each PE: buyer loss = max(0, strike - spot) * OI  (ITM puts hurt buyers)

    Max Pain = strike that MAXIMISES total buyer loss (= minimises writer loss).
    """
    total_pain = 0.0

    for _, row in chain_df.iterrows():
        K = float(row[strike_col])
        oi = float(row[oi_col])
        ot = str(row[option_type_col]).upper()

        if ot in ("CE", "C", "CALL"):
            # Call buyer loss if spot = test_strike
            intrinsic = max(0.0, test_strike - K)
            total_pain += intrinsic * oi
        elif ot in ("PE", "P", "PUT"):
            # Put buyer loss if spot = test_strike
            intrinsic = max(0.0, K - test_strike)
            total_pain += intrinsic * oi

    return total_pain


def calculate_max_pain(
    chain_df: pd.DataFrame,
    strike_col: str = "strike_price",
    option_type_col: str = "option_type",
    oi_col: str = "open_interest",
) -> tuple[float, float]:
    """
    Find the Max Pain strike.

    Returns:
        (max_pain_strike, total_pain_at_max)
    """
    strikes = sorted(chain_df[strike_col].unique())
    if not strikes:
        return 0.0, 0.0

    pain_by_strike = {}
    for strike in strikes:
        pain_by_strike[strike] = _compute_pain_at_strike(
            chain_df, strike, strike_col, option_type_col, oi_col
        )

    # Max pain = strike where total pain is MAXIMUM (counterintuitive naming:
    # "max pain" means max pain for BUYERS = max profit for writers)
    max_strike = max(pain_by_strike, key=pain_by_strike.get)  # type: ignore[arg-type]
    return float(max_strike), float(pain_by_strike[max_strike])


def compute_gravity_zone(
    max_pain: float,
    spot: float,
    gravity_pct: float = DEFAULT_GRAVITY_PCT,
) -> MaxPainResult:
    """
    Compute gravity zone around max pain and assess pin risk.

    Args:
        max_pain: Max pain strike price
        spot: Current spot/underlying price
        gravity_pct: Zone width as fraction of max pain (default 1%)

    Returns:
        MaxPainResult with zone boundaries and pin risk assessment
    """
    zone_low = max_pain * (1 - gravity_pct)
    zone_high = max_pain * (1 + gravity_pct)
    in_zone = zone_low <= spot <= zone_high

    # Distance from max pain as % of spot
    distance_pct = abs(spot - max_pain) / spot if spot > 0 else 1.0

    if in_zone:
        pin_risk = "HIGH"
    elif distance_pct < 0.02:
        pin_risk = "MODERATE"
    else:
        pin_risk = "LOW"

    return MaxPainResult(
        max_pain_strike=max_pain,
        total_pain_at_max=0.0,  # caller can fill this in
        gravity_zone_low=round(zone_low, 2),
        gravity_zone_high=round(zone_high, 2),
        spot_in_gravity_zone=in_zone,
        pin_risk=pin_risk,
    )


def is_in_gravity_zone(
    spot: float,
    max_pain: float,
    gravity_pct: float = DEFAULT_GRAVITY_PCT,
) -> bool:
    """Quick check: is spot within ±gravity_pct of max pain?"""
    return max_pain * (1 - gravity_pct) <= spot <= max_pain * (1 + gravity_pct)
