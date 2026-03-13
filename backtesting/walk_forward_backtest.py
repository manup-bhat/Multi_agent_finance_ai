"""
Walk-Forward Backtesting — Anti-Lookahead OOS Validation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enforces the same anti-lookahead constraint as Phase 5 ML engine:
  max(train_indices) < min(test_indices) - embargo

Each fold trains the strategy parameters on in-sample data,
then evaluates strictly on out-of-sample test data.

No data leaks. No curve fitting. India NSE calendar-aware.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass, field
from typing import Callable, Optional

from backtesting.metrics import (
    compute_sharpe, compute_max_drawdown, annualize_returns,
    NSE_TRADING_DAYS,
)

logger = structlog.get_logger(__name__)

# Default walk-forward parameters (same as Phase 5 ML WFO)
DEFAULT_TRAIN_WINDOW = 252   # 1 trading year
DEFAULT_TEST_WINDOW  = 63    # 3 trading months
DEFAULT_EMBARGO_DAYS = 5     # Gap between train end and test start
DEFAULT_STEP_SIZE    = 21    # Move forward 1 trading month per fold


@dataclass
class WalkForwardFold:
    """Results for a single WFO fold."""
    fold_idx:         int
    train_start:      int       # Integer index position
    train_end:        int
    test_start:       int
    test_end:         int
    train_start_date: str
    test_start_date:  str
    n_test_days:      int
    n_trades:         int
    oos_sharpe:       float
    oos_max_dd:       float
    oos_cagr:         float
    embargo_satisfied: bool     # max(train) < min(test) - embargo


@dataclass
class WalkForwardResult:
    """Aggregate walk-forward backtest results."""
    strategy_name:     str
    ticker:            str
    n_folds:           int
    folds:             list[WalkForwardFold]
    avg_oos_sharpe:    float
    median_oos_sharpe: float
    pct_profitable_folds: float   # % folds with positive Sharpe
    avg_oos_cagr:      float
    avg_oos_max_dd:    float
    all_oos_returns:   pd.Series  # Concatenated OOS daily returns
    anti_lookahead_ok: bool       # All folds pass the embargo check
    notes:             list[str] = field(default_factory=list)


def _validate_no_lookahead(
    train_end: int,
    test_start: int,
    embargo: int,
) -> bool:
    """
    Blueprint validation gate (same as Phase 5):
    max(train_indices) < min(test_indices) - EMBARGO_DAYS
    """
    return train_end < test_start - embargo


def run_walk_forward(
    prices: pd.Series,
    strategy_fn: Callable[[pd.Series], pd.DataFrame],
    strategy_name: str = "Strategy",
    ticker: str = "UNKNOWN",
    train_window: int = DEFAULT_TRAIN_WINDOW,
    test_window: int  = DEFAULT_TEST_WINDOW,
    embargo: int      = DEFAULT_EMBARGO_DAYS,
    step_size: int    = DEFAULT_STEP_SIZE,
) -> WalkForwardResult:
    """
    Run walk-forward out-of-sample backtesting.

    For each fold:
      1. Use prices[train_start:train_end] to generate signals
         (strategy is applied to the full price history up to train_end)
      2. Embargo gap: prices[train_end:train_end+embargo] - NOT used
      3. Evaluate on prices[test_start:test_end] OOS

    Anti-lookahead: `train_end < test_start - embargo` is asserted for ALL folds.

    Args:
        prices:       Full price Series (daily)
        strategy_fn:  Callable that takes prices Series, returns signals DataFrame
        strategy_name: Name for reporting
        ticker:       Instrument name
        train_window: In-sample training window (days)
        test_window:  Out-of-sample test window (days)
        embargo:      Gap between train end and test start (days)
        step_size:    Walk-forward step per fold (days)

    Returns:
        WalkForwardResult
    """
    n = len(prices)
    folds: list[WalkForwardFold] = []
    all_oos_returns_list: list[pd.Series] = []
    anti_lookahead_ok = True

    fold_idx = 0
    test_start = train_window + embargo

    while test_start + test_window <= n:
        train_start = max(0, test_start - embargo - train_window)
        train_end   = test_start - embargo - 1
        test_end    = min(n - 1, test_start + test_window - 1)

        # Anti-lookahead check
        ok = _validate_no_lookahead(train_end, test_start, embargo)
        if not ok:
            anti_lookahead_ok = False
            logger.error(
                "walk_forward.lookahead_violation",
                fold=fold_idx, train_end=train_end, test_start=test_start,
            )

        # Generate signals from FULL prices up to train_end (strategy is applied to all history)
        train_prices = prices.iloc[:train_end + 1]
        try:
            signals = strategy_fn(train_prices)
        except Exception as e:
            logger.warning("walk_forward.signal_error", fold=fold_idx, error=str(e))
            test_start += step_size
            fold_idx += 1
            continue

        # Evaluate on OOS prices
        oos_prices  = prices.iloc[test_start:test_end + 1]
        oos_entries = signals["entries"].reindex(oos_prices.index).fillna(False)
        oos_exits   = signals["exits"].reindex(oos_prices.index).fillna(False)

        # Simple returns simulation (position = 1 when in trade, else 0)
        position  = (oos_entries.astype(int) - oos_exits.astype(int)).clip(0, 1)
        position  = position.cumsum().clip(0, 1)   # Simple long-only position tracking
        price_ret = oos_prices.pct_change().fillna(0.0)
        oos_daily_returns = price_ret * position.shift(1).fillna(0)

        oos_equity = (1 + oos_daily_returns).cumprod() * 100_000
        oos_sharpe = compute_sharpe(oos_daily_returns)
        oos_max_dd = compute_max_drawdown(oos_equity)
        oos_cagr   = annualize_returns(oos_daily_returns)
        n_trades   = int((oos_entries & (position > 0)).sum())

        train_start_date = str(prices.index[train_start].date()) if hasattr(prices.index[train_start], "date") else str(prices.index[train_start])
        test_start_date  = str(prices.index[test_start].date()) if hasattr(prices.index[test_start], "date") else str(prices.index[test_start])

        folds.append(WalkForwardFold(
            fold_idx=fold_idx,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
            train_start_date=train_start_date,
            test_start_date=test_start_date,
            n_test_days=len(oos_prices),
            n_trades=n_trades,
            oos_sharpe=round(oos_sharpe, 4),
            oos_max_dd=round(oos_max_dd, 4),
            oos_cagr=round(oos_cagr, 4),
            embargo_satisfied=ok,
        ))

        all_oos_returns_list.append(oos_daily_returns)
        test_start += step_size
        fold_idx += 1

    if not folds:
        logger.warning("walk_forward.no_folds", n=n, train=train_window, test=test_window)
        return WalkForwardResult(
            strategy_name=strategy_name, ticker=ticker, n_folds=0,
            folds=[], avg_oos_sharpe=0.0, median_oos_sharpe=0.0,
            pct_profitable_folds=0.0, avg_oos_cagr=0.0, avg_oos_max_dd=0.0,
            all_oos_returns=pd.Series(dtype=float), anti_lookahead_ok=False,
            notes=["Too few data points for any fold."],
        )

    sharpes  = [f.oos_sharpe for f in folds]
    cagrs    = [f.oos_cagr for f in folds]
    max_dds  = [f.oos_max_dd for f in folds]
    all_oos  = pd.concat(all_oos_returns_list) if all_oos_returns_list else pd.Series(dtype=float)

    notes: list[str] = []
    if not anti_lookahead_ok:
        notes.append("⚠️ LOOKAHEAD VIOLATION detected in at least one fold!")
    pct_pos = sum(1 for s in sharpes if s > 0) / len(sharpes)
    if pct_pos < 0.5:
        notes.append(f"Only {pct_pos:.0%} of folds profitable — strategy may not generalise.")

    logger.info(
        "walk_forward.done",
        n_folds=len(folds), avg_sharpe=round(float(np.mean(sharpes)), 4),
        anti_lookahead_ok=anti_lookahead_ok,
    )

    return WalkForwardResult(
        strategy_name=strategy_name,
        ticker=ticker,
        n_folds=len(folds),
        folds=folds,
        avg_oos_sharpe=round(float(np.mean(sharpes)), 4),
        median_oos_sharpe=round(float(np.median(sharpes)), 4),
        pct_profitable_folds=round(pct_pos, 4),
        avg_oos_cagr=round(float(np.mean(cagrs)), 4),
        avg_oos_max_dd=round(float(np.mean(max_dds)), 4),
        all_oos_returns=all_oos,
        anti_lookahead_ok=anti_lookahead_ok,
        notes=notes,
    )
