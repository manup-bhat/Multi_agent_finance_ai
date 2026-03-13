"""
BacktestEngine — vectorbt Wrapper (India Calibrated)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Wraps vectorbt's portfolio simulation with:
  - India-calibrated costs (0.03% brokerage + 0.01% slippage = 0.04% per trade)
  - Long-only mode (NSE equity positions)
  - Proper performance metrics via backtesting.metrics
  - Returns structured BacktestResult dataclass

vectorbt docs: https://vectorbt.dev/api/portfolio/base/
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass, field
from typing import Optional

from config.constants import (
    BACKTEST_COMMISSION_PCT, BACKTEST_SLIPPAGE_PCT, BACKTEST_INITIAL_CAPITAL_INR
)
from backtesting.metrics import compute_all_metrics, PerformanceMetrics

logger = structlog.get_logger(__name__)

# Combined India transaction cost per trade (one-way)
TOTAL_COST_PER_TRADE = BACKTEST_COMMISSION_PCT + BACKTEST_SLIPPAGE_PCT  # 0.04%


@dataclass
class BacktestResult:
    """Complete result from a single backtest run."""
    strategy_name:    str
    ticker:           str
    start_date:       str
    end_date:         str
    n_days:           int
    n_trades:         int
    initial_capital:  float
    final_equity:     float
    metrics:          PerformanceMetrics
    equity_curve:     pd.Series          # Full equity curve (₹)
    daily_returns:    pd.Series          # Daily return series
    trade_log:        pd.DataFrame       # Per-trade details (vectorbt format)
    commission_paid:  float              # Total ₹ paid in brokerage/slippage
    notes:            list[str] = field(default_factory=list)

    @property
    def sharpe_ratio(self) -> float:
        return self.metrics.sharpe_ratio

    @property
    def max_drawdown_pct(self) -> float:
        return self.metrics.max_drawdown_pct

    @property
    def cagr_pct(self) -> float:
        return self.metrics.cagr_pct

    @property
    def total_return_pct(self) -> float:
        return self.metrics.total_return_pct


class BacktestEngine:
    """
    Vectorbt-based backtesting engine for India NSE strategies.

    Usage:
        engine = BacktestEngine()
        result = engine.run(
            prices=banknifty_close,
            signals=mean_reversion_rsi_bb(banknifty_close),
            strategy_name="MeanReversionRSI_BB",
            ticker="BANKNIFTY"
        )
        print(result.sharpe_ratio)
    """

    def __init__(
        self,
        initial_capital:  float = BACKTEST_INITIAL_CAPITAL_INR,
        commission:       float = BACKTEST_COMMISSION_PCT,
        slippage:         float = BACKTEST_SLIPPAGE_PCT,
    ):
        self.initial_capital = initial_capital
        self.commission      = commission
        self.slippage        = slippage
        self.total_cost      = commission + slippage

    def run(
        self,
        prices: pd.Series,
        signals: pd.DataFrame,
        strategy_name: str = "Strategy",
        ticker: str = "UNKNOWN",
        benchmark_prices: Optional[pd.Series] = None,
    ) -> BacktestResult:
        """
        Run a backtest using vectorbt.

        Args:
            prices:           Close price Series indexed by date
            signals:          DataFrame with 'entries' and 'exits' bool columns
            strategy_name:    Human-readable strategy name
            ticker:           Instrument being traded
            benchmark_prices: Optional benchmark (e.g. Nifty 50) for alpha/beta
        Returns:
            BacktestResult
        """
        try:
            import vectorbt as vbt
        except ImportError:
            logger.error("backtest_engine.vectorbt_not_installed")
            raise

        logger.info(
            "backtest_engine.run",
            strategy=strategy_name, ticker=ticker,
            n_signals=int(signals["entries"].sum()),
        )

        # Align signals to prices
        entries = signals["entries"].reindex(prices.index).fillna(False)
        exits   = signals["exits"].reindex(prices.index).fillna(False)

        # Run vectorbt portfolio simulation
        pf = vbt.Portfolio.from_signals(
            close=prices,
            entries=entries,
            exits=exits,
            init_cash=self.initial_capital,
            fees=self.total_cost,        # Per trade, one-way
            slippage=0.0,                # Already included in fees
            freq="D",                    # Daily frequency
        )

        # Extract equity curve + returns
        equity_curve   = pf.value()
        daily_returns  = pf.returns()
        n_trades       = int(pf.trades.count())

        # Trade log
        try:
            trade_log = pf.trades.records_readable
        except Exception:
            trade_log = pd.DataFrame()

        # Trade-level returns for win rate
        trade_returns = pd.Series(dtype=float)
        try:
            if not trade_log.empty and "Return" in trade_log.columns:
                trade_returns = trade_log["Return"].rename(None)
        except Exception:
            pass

        # Benchmark returns
        benchmark_returns = None
        if benchmark_prices is not None and not benchmark_prices.empty:
            benchmark_returns = benchmark_prices.pct_change().dropna()

        # Commission paid estimate
        commission_paid = n_trades * 2 * self.total_cost * self.initial_capital

        metrics = compute_all_metrics(
            daily_returns=daily_returns,
            equity_curve=equity_curve,
            benchmark_returns=benchmark_returns,
            trade_returns=trade_returns if not trade_returns.empty else None,
            n_trades=n_trades,
        )

        notes: list[str] = []
        if n_trades == 0:
            notes.append("Zero trades generated — check signal logic or price data range.")
        if metrics.sharpe_ratio < 0:
            notes.append("Negative Sharpe — strategy is losing money. Review parameters.")

        start_date = str(prices.index[0].date()) if hasattr(prices.index[0], "date") else str(prices.index[0])
        end_date   = str(prices.index[-1].date()) if hasattr(prices.index[-1], "date") else str(prices.index[-1])

        result = BacktestResult(
            strategy_name=strategy_name,
            ticker=ticker,
            start_date=start_date,
            end_date=end_date,
            n_days=len(prices),
            n_trades=n_trades,
            initial_capital=self.initial_capital,
            final_equity=float(equity_curve.iloc[-1]),
            metrics=metrics,
            equity_curve=equity_curve,
            daily_returns=daily_returns,
            trade_log=trade_log,
            commission_paid=round(commission_paid, 2),
            notes=notes,
        )

        logger.info(
            "backtest_engine.done",
            sharpe=result.sharpe_ratio,
            max_dd=result.max_drawdown_pct,
            n_trades=n_trades,
            cagr=result.cagr_pct,
        )
        return result
