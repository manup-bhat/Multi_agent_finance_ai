"""POST /backtest — run strategy backtest using Phase 9 engine."""
from fastapi import APIRouter
from api.schemas import BacktestRequest, BacktestResponse
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/backtest", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest):
    """Run vectorbt backtest. Uses Phase 9 engine."""
    logger.info("api.backtest", strategy=req.strategy, ticker=req.ticker)
    try:
        from backtesting.engine import BacktestEngine
        from backtesting.strategies import mean_reversion_rsi_bb, ema_momentum, vix_gated_momentum
        import pandas as pd
        import yfinance as yf
        
        # Download real prices
        prices_df = yf.download(req.ticker, period=f"{req.years}y", progress=False, auto_adjust=True)
        if prices_df is None or prices_df.empty:
            raise ValueError(f"Could not fetch data for {req.ticker}")
        
        # Flatten multi-level columns if any
        if isinstance(prices_df.columns, pd.MultiIndex):
            prices_df.columns = prices_df.columns.get_level_values(0)
            
        prices = prices_df["Close"]
        
        benchmark_df = yf.download("^NSEI", period=f"{req.years}y", progress=False, auto_adjust=True)
        if benchmark_df is not None and not benchmark_df.empty:
            if isinstance(benchmark_df.columns, pd.MultiIndex):
                benchmark_df.columns = benchmark_df.columns.get_level_values(0)
            benchmark_prices = benchmark_df["Close"]
        else:
            benchmark_prices = None
        
        # Generate signals based on requested strategy
        if req.strategy == "mean_reversion":
            signals = mean_reversion_rsi_bb(prices)
        elif req.strategy == "ema_momentum":
            signals = ema_momentum(prices)
        elif req.strategy == "vix_gated":
            vix_df = yf.download("^INDIAVIX", period=f"{req.years}y", progress=False, auto_adjust=True)
            if vix_df is not None and not vix_df.empty:
                if isinstance(vix_df.columns, pd.MultiIndex):
                    vix_df.columns = vix_df.columns.get_level_values(0)
                vix = vix_df["Close"]
            else:
                vix = pd.Series(15.0, index=prices.index)
            signals = vix_gated_momentum(prices, vix)
        elif req.strategy == "fii_flow":
            # Just fallback to EMA momentum if true FII is unavailable in backtest engine perfectly aligned yet
            signals = ema_momentum(prices)
        else:
            signals = mean_reversion_rsi_bb(prices)
            
        engine = BacktestEngine(initial_capital=100000)
        result = engine.run(prices=prices, signals=signals, strategy_name=req.strategy, ticker=req.ticker, benchmark_prices=benchmark_prices)
        
        dates_str = [str(d.date()) if hasattr(d, "date") else str(d)[:10] for d in result.equity_curve.index]
        
        # We need a benchmark curve for charting (indexed at starting capital)
        if benchmark_prices is not None:
             b_aligned = benchmark_prices.reindex(result.equity_curve.index).ffill()
             if not b_aligned.empty and b_aligned.iloc[0] > 0:
                 b_curve = (b_aligned / b_aligned.iloc[0]) * engine.initial_capital
                 b_curve_list = b_curve.ffill().tolist()
             else:
                 b_curve_list = []
        else:
             b_curve_list = []
             
        return BacktestResponse(
            strategy=req.strategy,
            ticker=req.ticker,
            sharpe_ratio=round(result.sharpe_ratio, 3),
            cagr_pct=round(result.cagr_pct, 2),
            max_drawdown_pct=round(result.max_drawdown_pct, 2),
            win_rate_pct=round(result.metrics.win_rate_pct, 2),
            n_trades=result.n_trades,
            blueprint_gate_passed=result.sharpe_ratio >= 0.8,
            dates=dates_str,
            equity_curve=result.equity_curve.tolist(),
            benchmark_curve=b_curve_list
        )
    except Exception as e:
        from fastapi import HTTPException
        logger.error("api.backtest.error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Backtest failed: {str(e)}")
