"""
Global Cues Aggregator — Morning Market Context for India
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
India Nifty 50 opening is heavily influenced by:
  1. SGX Nifty futures (Singapore) — the primary pre-market indicator
  2. S&P 500 + Nasdaq — US market direction
  3. Asian peers: Nikkei, Hang Seng, KOSPI, STI
  4. Gift Nifty (replaced SGX Nifty in July 2023 on GIFT City exchange)

Gap analysis:
  SGX/GIFT Nifty vs Nifty prev close → expected opening gap
  > +0.5% = Gap Up    (positive for opening sentiment)
  < -0.5% = Gap Down  (negative for opening sentiment)
  Otherwise = Flat

Risk sentiment:
  "RISK_ON"  — US + Asia both positive
  "RISK_OFF" — US + Asia both negative
  "MIXED"    — divergent signals
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass
from typing import Optional

logger = structlog.get_logger(__name__)

# Gap direction thresholds
GAP_THRESHOLD_PCT = 0.005    # ±0.5%

# Global sentiment categories
RISK_ON  = "RISK_ON"
RISK_OFF = "RISK_OFF"
MIXED    = "MIXED"


@dataclass
class GlobalCuesReport:
    """Structured global cues snapshot for agent consumption."""
    sgx_gap_pct: float          # SGX/GIFT Nifty vs Nifty prev close
    sgx_gap_direction: str      # "GAP_UP" / "GAP_DOWN" / "FLAT"
    us_sp500_ret: float         # S&P 500 overnight return
    us_nasdaq_ret: float        # Nasdaq overnight return
    asia_avg_ret: float         # Average of available Asian markets
    global_sentiment: str       # RISK_ON / RISK_OFF / MIXED
    expected_nifty_open: str    # "POSITIVE" / "NEGATIVE" / "NEUTRAL"
    description: str


def compute_sgx_gap(
    sgx_price: float,
    nifty_prev_close: float,
) -> tuple[float, str]:
    """
    Compute SGX Nifty / GIFT Nifty gap vs Nifty previous close.

    Args:
        sgx_price: GIFT/SGX Nifty futures price (pre-market)
        nifty_prev_close: Nifty 50 previous day's closing price

    Returns:
        (gap_pct, direction) where direction = "GAP_UP" / "GAP_DOWN" / "FLAT"
    """
    if nifty_prev_close <= 0:
        return 0.0, "FLAT"

    gap_pct = (sgx_price - nifty_prev_close) / nifty_prev_close
    if gap_pct > GAP_THRESHOLD_PCT:
        direction = "GAP_UP"
    elif gap_pct < -GAP_THRESHOLD_PCT:
        direction = "GAP_DOWN"
    else:
        direction = "FLAT"

    return round(gap_pct * 100, 4), direction  # return as percentage


def classify_global_sentiment(
    sp500_ret: float,
    nasdaq_ret: float,
    asia_ret: Optional[float] = None,
) -> str:
    """
    Classify global risk sentiment.

    Args:
        sp500_ret:  S&P 500 return (e.g. 0.01 = +1%)
        nasdaq_ret: Nasdaq return
        asia_ret:   Average Asian market return (optional)

    Returns:
        "RISK_ON" / "RISK_OFF" / "MIXED"
    """
    us_positive  = (sp500_ret + nasdaq_ret) > 0
    us_negative  = (sp500_ret + nasdaq_ret) < 0

    if asia_ret is not None:
        asia_positive = asia_ret > 0
        asia_negative = asia_ret < 0
        if us_positive and asia_positive:
            return RISK_ON
        if us_negative and asia_negative:
            return RISK_OFF
        return MIXED
    else:
        # No Asia data — use US alone
        if us_positive:
            return RISK_ON
        elif us_negative:
            return RISK_OFF
        return MIXED


def expected_nifty_open(
    sgx_gap_direction: str,
    global_sentiment: str,
) -> str:
    """
    Derive expected Nifty opening direction from gap + global sentiment.

    Returns:
        "POSITIVE" / "NEGATIVE" / "NEUTRAL"
    """
    if sgx_gap_direction == "GAP_UP" or global_sentiment == RISK_ON:
        if sgx_gap_direction == "GAP_DOWN" or global_sentiment == RISK_OFF:
            return "NEUTRAL"   # conflicting signals
        return "POSITIVE"
    elif sgx_gap_direction == "GAP_DOWN" or global_sentiment == RISK_OFF:
        return "NEGATIVE"
    return "NEUTRAL"


def build_global_cues_report(
    sgx_price: float,
    nifty_prev_close: float,
    sp500_ret: float = 0.0,
    nasdaq_ret: float = 0.0,
    asia_rets: Optional[dict[str, float]] = None,
) -> GlobalCuesReport:
    """
    Build a complete global cues report for the Macro agent.

    Args:
        sgx_price:       GIFT/SGX Nifty futures pre-market price
        nifty_prev_close: Nifty 50 previous session close
        sp500_ret:       S&P 500 return (yesterday's US close)
        nasdaq_ret:      Nasdaq return
        asia_rets:       dict of {market_name: return, ...}
                         e.g. {"nikkei": 0.01, "hangseng": -0.005}

    Returns:
        GlobalCuesReport dataclass
    """
    gap_pct, gap_dir = compute_sgx_gap(sgx_price, nifty_prev_close)

    asia_avg = None
    if asia_rets and len(asia_rets) > 0:
        asia_avg = float(np.mean(list(asia_rets.values())))

    sentiment = classify_global_sentiment(sp500_ret, nasdaq_ret, asia_avg)
    open_signal = expected_nifty_open(gap_dir, sentiment)

    asia_str = ""
    if asia_rets:
        asia_parts = [f"{k.title()}: {v*100:+.2f}%" for k, v in asia_rets.items()]
        asia_str = " | ".join(asia_parts)

    desc = (
        f"GIFT Nifty gap: {gap_pct:+.2f}% ({gap_dir}). "
        f"US: S&P {sp500_ret*100:+.2f}% | Nasdaq {nasdaq_ret*100:+.2f}%. "
        f"Global: {sentiment}. "
        f"Expected Nifty open: {open_signal}."
        + (f" Asia: {asia_str}" if asia_str else "")
    )

    logger.info(
        "global_cues.report",
        gap_pct=gap_pct, gap_dir=gap_dir,
        sentiment=sentiment, open_signal=open_signal,
    )
    return GlobalCuesReport(
        sgx_gap_pct=gap_pct,
        sgx_gap_direction=gap_dir,
        us_sp500_ret=round(sp500_ret * 100, 4),
        us_nasdaq_ret=round(nasdaq_ret * 100, 4),
        asia_avg_ret=round(asia_avg * 100, 4) if asia_avg is not None else 0.0,
        global_sentiment=sentiment,
        expected_nifty_open=open_signal,
        description=desc,
    )
