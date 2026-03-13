"""
Backtesting Performance Metrics — India Calibrated
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure numpy/pandas. Zero external dependencies beyond scientific stack.

India-specific calibrations:
  - Risk-free rate = 6.5% p.a. (1-year India G-Sec, March 2026)
  - Trading days per year = 252 (NSE calendar)
  - Annualization factor = sqrt(252) for Sharpe/Sortino

All functions accept daily return Series (float, decimal form e.g. 0.01 = 1%).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional


# ── India constants ────────────────────────────────────────────────────────────
INDIA_RISK_FREE_ANNUAL = 0.065   # 6.5% pa — 1yr G-Sec March 2026
NSE_TRADING_DAYS       = 252     # NSE annual trading day count
ANNUALIZATION_FACTOR   = np.sqrt(NSE_TRADING_DAYS)


@dataclass
class PerformanceMetrics:
    """All performance metrics in one container."""
    sharpe_ratio:     float
    sortino_ratio:    float
    calmar_ratio:     float
    max_drawdown_pct: float          # e.g. -0.25 means 25% drawdown
    cagr_pct:         float          # annualized return in decimal
    total_return_pct: float          # raw total return
    win_rate:         float          # fraction of profitable trades (0-1)
    alpha:            float          # Jensen's alpha vs benchmark
    beta:             float          # market beta
    n_trades:         int
    n_days:           int
    notes:            list[str] = field(default_factory=list)


def compute_sharpe(
    daily_returns: pd.Series,
    risk_free_annual: float = INDIA_RISK_FREE_ANNUAL,
) -> float:
    """
    Annualized Sharpe ratio (India calibrated).

    Sharpe = (mean_daily_return - daily_risk_free) / std_daily_return * sqrt(252)
    """
    if daily_returns.empty or daily_returns.std() == 0:
        return 0.0
    daily_rf = risk_free_annual / NSE_TRADING_DAYS
    excess = daily_returns - daily_rf
    return float((excess.mean() / excess.std()) * ANNUALIZATION_FACTOR)


def compute_sortino(
    daily_returns: pd.Series,
    risk_free_annual: float = INDIA_RISK_FREE_ANNUAL,
) -> float:
    """
    Sortino ratio — like Sharpe but uses only downside deviation.
    Preferred for India F&O where downside risk is skewed.
    """
    if daily_returns.empty:
        return 0.0
    daily_rf = risk_free_annual / NSE_TRADING_DAYS
    excess = daily_returns - daily_rf
    downside = excess[excess < 0]
    if len(downside) == 0 or downside.std() == 0:
        return float(excess.mean() * ANNUALIZATION_FACTOR / 1e-9)  # effectively inf
    return float((excess.mean() / downside.std()) * ANNUALIZATION_FACTOR)


def compute_max_drawdown(equity_curve: pd.Series) -> float:
    """
    Maximum drawdown from equity curve (peak-to-trough).

    Returns:
        Float in decimal form (e.g. -0.25 for 25% drawdown). Always <= 0.
    """
    if equity_curve.empty:
        return 0.0
    rolling_max = equity_curve.cummax()
    drawdown = (equity_curve - rolling_max) / rolling_max
    return float(drawdown.min())


def compute_calmar(
    daily_returns: pd.Series,
    max_drawdown: float,
) -> float:
    """
    Calmar ratio = CAGR / abs(Max Drawdown).
    Measures return per unit of worst-case loss.
    """
    if max_drawdown == 0 or np.isnan(max_drawdown):
        return 0.0
    cagr = annualize_returns(daily_returns)
    return float(cagr / abs(max_drawdown))


def compute_alpha_beta(
    strategy_returns: pd.Series,
    benchmark_returns: pd.Series,
) -> tuple[float, float]:
    """
    Jensen's Alpha and Beta vs benchmark (e.g. Nifty 50).

    Uses OLS: strategy_return = alpha + beta * benchmark_return

    Returns:
        (alpha_annualized, beta)
    """
    # Align on common index
    aligned = pd.concat(
        [strategy_returns.rename("strat"), benchmark_returns.rename("bench")],
        axis=1,
    ).dropna()

    if len(aligned) < 10:
        return 0.0, 1.0

    x = aligned["bench"].values
    y = aligned["strat"].values
    coeffs = np.polyfit(x, y, deg=1)   # returns [slope, intercept]
    beta = float(coeffs[0])
    alpha_daily = float(coeffs[1])
    alpha_annual = float(alpha_daily * NSE_TRADING_DAYS)
    return alpha_annual, beta


def compute_win_rate(trade_returns: pd.Series) -> float:
    """
    Win rate = fraction of trades with positive return.

    Args:
        trade_returns: Series of per-trade P&L as decimal returns
    Returns:
        float in [0, 1]
    """
    if trade_returns.empty:
        return 0.0
    return float((trade_returns > 0).sum() / len(trade_returns))


def annualize_returns(
    daily_returns: pd.Series,
    trading_days: int = NSE_TRADING_DAYS,
) -> float:
    """
    Convert daily returns to annualized CAGR equivalent.

    CAGR = (1 + total_return) ^ (252/n_days) - 1
    """
    if daily_returns.empty:
        return 0.0
    total = float((1 + daily_returns).prod())
    n = len(daily_returns)
    return float(total ** (trading_days / n) - 1)


def compute_all_metrics(
    daily_returns: pd.Series,
    equity_curve: pd.Series,
    benchmark_returns: Optional[pd.Series] = None,
    trade_returns: Optional[pd.Series] = None,
    n_trades: int = 0,
) -> PerformanceMetrics:
    """
    Compute all performance metrics from daily returns + equity curve.

    Args:
        daily_returns:    Daily portfolio returns (decimal), pd.Series
        equity_curve:     Equity curve (₹ or index), pd.Series
        benchmark_returns: Benchmark daily returns (e.g. Nifty 50)
        trade_returns:    Per-trade P&L as decimal series
        n_trades:         Number of trades

    Returns:
        PerformanceMetrics dataclass
    """
    sharpe  = compute_sharpe(daily_returns)
    sortino = compute_sortino(daily_returns)
    max_dd  = compute_max_drawdown(equity_curve)
    calmar  = compute_calmar(daily_returns, max_dd)
    cagr    = annualize_returns(daily_returns)
    total_r = float((1 + daily_returns).prod() - 1)

    alpha, beta = (0.0, 1.0)
    if benchmark_returns is not None and not benchmark_returns.empty:
        alpha, beta = compute_alpha_beta(daily_returns, benchmark_returns)

    win_rate = compute_win_rate(trade_returns) if trade_returns is not None else 0.0

    notes: list[str] = []
    if sharpe < 0:
        notes.append("Negative Sharpe — strategy underperforms risk-free rate.")
    if max_dd < -0.20:
        notes.append(f"High drawdown {max_dd:.1%} — consider VIX gating or position sizing.")
    if beta > 1.5:
        notes.append(f"High beta ({beta:.2f}) — strategy amplifies market moves.")

    return PerformanceMetrics(
        sharpe_ratio=round(sharpe, 4),
        sortino_ratio=round(sortino, 4),
        calmar_ratio=round(calmar, 4),
        max_drawdown_pct=round(max_dd, 4),
        cagr_pct=round(cagr, 4),
        total_return_pct=round(total_r, 4),
        win_rate=round(win_rate, 4),
        alpha=round(alpha, 4),
        beta=round(beta, 4),
        n_trades=n_trades,
        n_days=len(daily_returns),
        notes=notes,
    )
