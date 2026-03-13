"""
Implied Volatility Analyzer
━━━━━━━━━━━━━━━━━━━━━━━━━━
IV Rank, IV Percentile, IV Surface, and IV Skew analysis.

IV Rank:       (current - 52w_low) / (52w_high - 52w_low) × 100
IV Percentile: % of days in lookback where IV was BELOW current IV

Blueprint: IV Rank + IV Percentile + IV surface + skew
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass
from typing import Optional

logger = structlog.get_logger(__name__)


@dataclass
class IVMetrics:
    """IV analysis results for a symbol."""
    current_iv: float
    iv_rank: float          # 0–100
    iv_percentile: float    # 0–100
    iv_high_52w: float
    iv_low_52w: float
    signal: str             # "HIGH" / "NORMAL" / "LOW"


def compute_iv_rank(
    current_iv: float,
    iv_history: pd.Series | np.ndarray | list[float],
) -> float:
    """
    IV Rank = (current - low) / (high - low) × 100.
    Returns 0–100.  Returns 50.0 if high == low (no range).
    """
    arr = np.asarray(iv_history, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return 50.0
    lo, hi = float(np.min(arr)), float(np.max(arr))
    if hi == lo:
        return 50.0
    rank = (current_iv - lo) / (hi - lo) * 100.0
    return round(np.clip(rank, 0.0, 100.0), 2)


def compute_iv_percentile(
    current_iv: float,
    iv_history: pd.Series | np.ndarray | list[float],
) -> float:
    """
    IV Percentile = % of historical observations BELOW current IV.
    Returns 0–100.
    """
    arr = np.asarray(iv_history, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return 50.0
    pct = float(np.sum(arr < current_iv)) / len(arr) * 100.0
    return round(pct, 2)


def compute_iv_metrics(
    current_iv: float,
    iv_history: pd.Series | np.ndarray | list[float],
) -> IVMetrics:
    """Compute full IV metrics suite."""
    arr = np.asarray(iv_history, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    lo = float(np.min(arr)) if len(arr) > 0 else current_iv
    hi = float(np.max(arr)) if len(arr) > 0 else current_iv

    rank = compute_iv_rank(current_iv, arr)
    pctl = compute_iv_percentile(current_iv, arr)

    if rank > 70:
        signal = "HIGH"
    elif rank < 30:
        signal = "LOW"
    else:
        signal = "NORMAL"

    return IVMetrics(
        current_iv=round(current_iv, 4),
        iv_rank=rank,
        iv_percentile=pctl,
        iv_high_52w=round(hi, 4),
        iv_low_52w=round(lo, 4),
        signal=signal,
    )


def build_iv_surface(
    chain_df: pd.DataFrame,
    iv_col: str = "iv",
    strike_col: str = "strike_price",
    expiry_col: str = "expiry_date",
    option_type_col: str = "option_type",
) -> pd.DataFrame:
    """
    Build 2D IV surface: strikes × expiries.

    Returns:
        DataFrame with strike_price as index, expiry dates as columns,
        values = average IV of CE and PE at that strike/expiry.
    """
    df = chain_df.copy()
    if iv_col not in df.columns:
        logger.warning("iv_analyzer.no_iv_column", available=list(df.columns))
        return pd.DataFrame()

    # Average CE and PE IVs at each (strike, expiry)
    pivot = df.groupby([strike_col, expiry_col])[iv_col].mean().unstack(fill_value=0)
    return pivot


def compute_iv_skew(
    chain_df: pd.DataFrame,
    spot: float,
    iv_col: str = "iv",
    strike_col: str = "strike_price",
    option_type_col: str = "option_type",
) -> dict:
    """
    Compute put-call IV skew for a given expiry.

    Returns:
        {
            "atm_iv": float,
            "otm_put_iv": float (10% OTM put IV),
            "otm_call_iv": float (10% OTM call IV),
            "skew": float (put_iv - call_iv; >0 = negative skew),
            "skew_ratio": float (put_iv / call_iv),
        }
    """
    puts = chain_df[chain_df[option_type_col].isin(["PE", "P", "p"])].copy()
    calls = chain_df[chain_df[option_type_col].isin(["CE", "C", "c"])].copy()

    if puts.empty or calls.empty:
        return {"atm_iv": 0.0, "otm_put_iv": 0.0, "otm_call_iv": 0.0,
                "skew": 0.0, "skew_ratio": 1.0}

    # Find ATM strike (closest to spot)
    all_strikes = chain_df[strike_col].unique()
    atm_strike = float(all_strikes[np.argmin(np.abs(all_strikes - spot))])

    # 10% OTM strikes
    otm_put_strike = atm_strike * 0.90
    otm_call_strike = atm_strike * 1.10

    # Find closest strikes
    put_strike = float(puts[strike_col].iloc[
        np.argmin(np.abs(puts[strike_col].values - otm_put_strike))
    ])
    call_strike = float(calls[strike_col].iloc[
        np.argmin(np.abs(calls[strike_col].values - otm_call_strike))
    ])

    atm_iv_vals = chain_df[
        chain_df[strike_col] == atm_strike
    ][iv_col].values
    atm_iv = float(np.mean(atm_iv_vals)) if len(atm_iv_vals) > 0 else 0.0

    otm_put_iv = float(puts[puts[strike_col] == put_strike][iv_col].mean())
    otm_call_iv = float(calls[calls[strike_col] == call_strike][iv_col].mean())

    skew_ratio = otm_put_iv / otm_call_iv if otm_call_iv > 0 else 1.0

    return {
        "atm_iv": round(atm_iv, 4),
        "otm_put_iv": round(otm_put_iv, 4),
        "otm_call_iv": round(otm_call_iv, 4),
        "skew": round(otm_put_iv - otm_call_iv, 4),
        "skew_ratio": round(skew_ratio, 4),
    }
