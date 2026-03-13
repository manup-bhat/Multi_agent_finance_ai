"""
Phase 9: Backtesting Module — Public API
"""
from backtesting.metrics import (
    PerformanceMetrics, compute_sharpe, compute_sortino, compute_max_drawdown,
    compute_calmar, compute_alpha_beta, compute_win_rate, annualize_returns,
    compute_all_metrics, INDIA_RISK_FREE_ANNUAL, NSE_TRADING_DAYS,
)
from backtesting.strategies import (
    mean_reversion_rsi_bb, ema_momentum, vix_gated_momentum, fii_flow_momentum,
)
from backtesting.engine import BacktestEngine, BacktestResult
from backtesting.report_generator import build_backtest_report, format_backtest_summary
from backtesting.walk_forward_backtest import (
    run_walk_forward, WalkForwardResult, WalkForwardFold,
)

__all__ = [
    # Metrics
    "PerformanceMetrics", "compute_sharpe", "compute_sortino",
    "compute_max_drawdown", "compute_calmar", "compute_alpha_beta",
    "compute_win_rate", "annualize_returns", "compute_all_metrics",
    "INDIA_RISK_FREE_ANNUAL", "NSE_TRADING_DAYS",
    # Strategies
    "mean_reversion_rsi_bb", "ema_momentum", "vix_gated_momentum",
    "fii_flow_momentum",
    # Engine
    "BacktestEngine", "BacktestResult",
    # Reports
    "build_backtest_report", "format_backtest_summary",
    # Walk-forward
    "run_walk_forward", "WalkForwardResult", "WalkForwardFold",
]
