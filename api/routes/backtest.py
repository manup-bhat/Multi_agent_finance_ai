"""POST /backtest — run strategy backtest using Phase 9 engine."""
from __future__ import annotations

import math

from fastapi import APIRouter, HTTPException
import pandas as pd
import structlog

from api.schemas import BacktestRequest, BacktestResponse
from data.adapters.nselib_client import NSELibClient
from data.adapters.yfinance_client import YFinanceClient

logger = structlog.get_logger(__name__)
router = APIRouter()

INDEX_TICKER_MAP = {
    "BANKNIFTY": "^NSEBANK",
    "NIFTY": "^NSEI",
    "NIFTY50": "^NSEI",
}


def _resolve_price_ticker(raw_ticker: str) -> str:
    normalized = raw_ticker.strip().upper()
    return INDEX_TICKER_MAP.get(normalized, raw_ticker)


def _extract_close(df: pd.DataFrame, label: str) -> pd.Series:
    if df is None or df.empty or "close" not in df.columns:
        raise ValueError(f"missing close series for {label}")
    return df["close"].copy()


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        num = float(value)
    except (TypeError, ValueError):
        return default
    return num if math.isfinite(num) else default


def _normalize_percent(value: object) -> float:
    num = _safe_float(value)
    return num * 100.0 if abs(num) <= 2.0 else num


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """Run a live-data backtest without synthetic market inputs."""
    logger.info("api.backtest", strategy=req.strategy, ticker=req.ticker)
    try:
        from backtesting.engine import BacktestEngine
        from backtesting.strategies import (
            ema_momentum,
            fii_flow_momentum,
            mean_reversion_rsi_bb,
            vix_gated_momentum,
        )

        yf = YFinanceClient()
        nselib = NSELibClient()
        price_ticker = _resolve_price_ticker(req.ticker)

        prices_df = await yf.get_ohlcv(price_ticker, period=f"{req.years}y")
        benchmark_df = await yf.get_ohlcv("^NSEI", period=f"{req.years}y")
        prices = _extract_close(prices_df, req.ticker)
        benchmark_prices = benchmark_df["close"].copy() if benchmark_df is not None and not benchmark_df.empty else None

        if req.strategy == "mean_reversion":
            signals = mean_reversion_rsi_bb(prices)
        elif req.strategy == "ema_momentum":
            signals = ema_momentum(prices)
        elif req.strategy == "vix_gated":
            vix_df = await yf.get_india_vix(period=f"{req.years}y")
            if vix_df is None or vix_df.empty or "vix" not in vix_df.columns:
                raise ValueError("India VIX history unavailable for vix_gated strategy")
            vix = vix_df["vix"].copy()
            signals = vix_gated_momentum(prices, vix)
        elif req.strategy == "fii_flow":
            fii_df = await nselib.get_fii_dii(days=max(req.years * 252, 90))
            if fii_df.empty or "fii_net_value" not in fii_df.columns:
                raise ValueError("FII flow history unavailable for fii_flow strategy")
            signals = fii_flow_momentum(prices, fii_df["fii_net_value"])
        else:
            signals = mean_reversion_rsi_bb(prices)

        engine = BacktestEngine(initial_capital=100000)
        result = engine.run(
            prices=prices,
            signals=signals,
            strategy_name=req.strategy,
            ticker=req.ticker,
            benchmark_prices=benchmark_prices,
        )

        dates_str = [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in result.equity_curve.index]

        if benchmark_prices is not None:
            b_aligned = benchmark_prices.reindex(result.equity_curve.index).ffill()
            if not b_aligned.empty and b_aligned.iloc[0] > 0:
                b_curve = (b_aligned / b_aligned.iloc[0]) * engine.initial_capital
                b_curve_list = b_curve.ffill().tolist()
            else:
                b_curve_list = []
        else:
            b_curve_list = []

        win_rate_value = getattr(result, "win_rate_pct", None)
        if win_rate_value is None:
            metrics = getattr(result, "metrics", None)
            win_rate_value = getattr(metrics, "win_rate_pct", None)
            if win_rate_value is None and metrics is not None:
                win_rate_value = getattr(metrics, "win_rate", 0.0)

        sharpe_ratio = round(_safe_float(result.sharpe_ratio), 3)
        cagr_pct = round(_normalize_percent(getattr(result, "cagr_pct", 0.0)), 2)
        max_drawdown_pct = round(_normalize_percent(getattr(result, "max_drawdown_pct", 0.0)), 2)
        win_rate_pct = round(_normalize_percent(win_rate_value), 2)

        return BacktestResponse(
            strategy=req.strategy,
            ticker=req.ticker,
            sharpe_ratio=sharpe_ratio,
            cagr_pct=cagr_pct,
            max_drawdown_pct=max_drawdown_pct,
            win_rate_pct=win_rate_pct,
            n_trades=result.n_trades,
            blueprint_gate_passed=sharpe_ratio >= 0.8,
            dates=dates_str,
            equity_curve=[_safe_float(v) for v in result.equity_curve.tolist()],
            benchmark_curve=[_safe_float(v) for v in b_curve_list],
        )
    except Exception as e:
        logger.error("api.backtest.error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")
