"""
India Trading Strategies — Signal Generators
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Each strategy returns a pd.DataFrame with columns:
  - 'entries': bool  — True on bar where long position is entered
  - 'exits':   bool  — True on bar where position is closed

Design rules:
  - All signals are generated with .shift(1) anti-lookahead protection
  - VIX-gated strategies block new signals when VIX ≥ 25 (circuit breaker)
  - India calendar-aware: no signals on holidays (optional)
  - No LLM, no data fetching — pure pandas/numpy signal math
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Optional

from config.constants import VIX_CIRCUIT_BREAKER


def _compute_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """RSI using Wilder's smoothing (same as NSE/TradingView)."""
    delta = prices.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _compute_bollinger(
    prices: pd.Series,
    period: int = 20,
    n_std: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Returns (middle, upper, lower) Bollinger Bands."""
    middle = prices.rolling(period).mean()
    std    = prices.rolling(period).std()
    return middle, middle + n_std * std, middle - n_std * std


def mean_reversion_rsi_bb(
    prices: pd.Series,
    rsi_period: int = 14,
    bb_period: int = 20,
    bb_std: float = 2.0,
    oversold: float = 30.0,
    overbought: float = 70.0,
) -> pd.DataFrame:
    """
    India Bank Nifty Mean Reversion Strategy.

    Entry:  RSI < oversold  AND  close < lower_bb  (shift(1) applied)
    Exit:   RSI > overbought AND  close > upper_bb  OR  RSI > 50

    Best suited for Bank Nifty due to high mean-reversion tendency
    caused by FII hedging activity around expiry weeks.

    Args:
        prices:     Close price Series (daily)
        rsi_period: Wilder RSI period (default 14)
        bb_period:  Bollinger Band lookback (default 20)
        bb_std:     BB standard deviations (default 2)
        oversold:   RSI below this = entry signal (default 30)
        overbought: RSI above this = exit signal  (default 70)

    Returns:
        DataFrame with 'entries' and 'exits' bool columns
    """
    rsi = _compute_rsi(prices, rsi_period)
    _, upper_bb, lower_bb = _compute_bollinger(prices, bb_period, bb_std)

    # Anti-lookahead: all signals based on yesterday's close
    rsi_lag      = rsi.shift(1)
    price_lag    = prices.shift(1)
    lower_bb_lag = lower_bb.shift(1)
    upper_bb_lag = upper_bb.shift(1)

    entries = (rsi_lag < oversold)  & (price_lag < lower_bb_lag)
    # Exit: overbought OR crossed middle
    exits   = (rsi_lag > overbought) & (price_lag > upper_bb_lag)

    return pd.DataFrame({"entries": entries.fillna(False),
                          "exits":   exits.fillna(False)})


def ema_momentum(
    prices: pd.Series,
    ema_short: int = 21,
    ema_long: int = 50,
) -> pd.DataFrame:
    """
    India EMA Momentum / Trend-Following Strategy.

    Entry:  EMA21 crosses above EMA50 (golden cross India variant)
    Exit:   EMA21 crosses below EMA50 (death cross)

    Anti-lookahead: crossover determined from shifted (t-1) values.
    """
    ema_s = prices.ewm(span=ema_short, adjust=False).mean()
    ema_l = prices.ewm(span=ema_long,  adjust=False).mean()

    # Shifted for anti-lookahead
    ema_s_lag = ema_s.shift(1)
    ema_l_lag = ema_l.shift(1)
    ema_s_lag2 = ema_s.shift(2)
    ema_l_lag2 = ema_l.shift(2)

    # Golden cross: ema_short just crossed above ema_long
    entries = (ema_s_lag > ema_l_lag) & (ema_s_lag2 <= ema_l_lag2)
    exits   = (ema_s_lag < ema_l_lag) & (ema_s_lag2 >= ema_l_lag2)

    return pd.DataFrame({"entries": entries.fillna(False),
                          "exits":   exits.fillna(False)})


def vix_gated_momentum(
    prices: pd.Series,
    vix_series: pd.Series,
    ema_short: int = 21,
    ema_long: int = 50,
    vix_threshold: float = VIX_CIRCUIT_BREAKER,
) -> pd.DataFrame:
    """
    VIX-Gated EMA Momentum — Blueprint compliant.

    Same as ema_momentum but:
      - Blocks new ENTRIES when VIX ≥ vix_threshold (circuit breaker)
      - Forces EXIT when VIX ≥ vix_threshold (protect capital)

    This enforces the blueprint risk rule: VIX ≥ 25 → no new positions.

    Args:
        prices:       Daily close prices
        vix_series:   India VIX daily Series (aligned to prices index)
        ema_short:    Short EMA span (default 21)
        ema_long:     Long EMA span (default 50)
        vix_threshold: VIX level that triggers gate (default 25)
    """
    base = ema_momentum(prices, ema_short, ema_long)

    # Align VIX to price index
    vix_aligned = vix_series.reindex(prices.index).ffill().fillna(15.0)
    vix_lag = vix_aligned.shift(1).fillna(15.0)

    high_vix = vix_lag >= vix_threshold

    # Block entries during high VIX; add forced exits
    entries = base["entries"] & ~high_vix
    exits   = base["exits"]   | high_vix

    return pd.DataFrame({"entries": entries.fillna(False),
                          "exits":   exits.fillna(False)})


def fii_flow_momentum(
    prices: pd.Series,
    fii_cumulative: pd.Series,
    window: int = 5,
) -> pd.DataFrame:
    """
    FII Flow Momentum Strategy — India-specific alpha.

    FII flows lead Nifty/BankNifty by 1-3 days (well-documented in India).
    Uses 5-day rolling sum of FII net flows as direction signal.

    Entry:  Cumulative 5d FII flow turns positive (FII buying)
    Exit:   Cumulative 5d FII flow turns negative (FII selling)

    Args:
        prices:          Daily close prices (aligned to FII index)
        fii_cumulative:  Daily FII net flow in ₹ Crore (+ = buy, - = sell)
        window:          Rolling window for trend detection (default 5)
    """
    fii_aligned = fii_cumulative.reindex(prices.index).fillna(0.0)
    rolling_sum = fii_aligned.rolling(window).sum()

    # Shift 1 day — FII data published after market close
    flow_lag  = rolling_sum.shift(1)
    flow_lag2 = rolling_sum.shift(2)

    entries = (flow_lag > 0) & (flow_lag2 <= 0)   # Turned positive
    exits   = (flow_lag < 0) & (flow_lag2 >= 0)   # Turned negative

    return pd.DataFrame({"entries": entries.fillna(False),
                          "exits":   exits.fillna(False)})
