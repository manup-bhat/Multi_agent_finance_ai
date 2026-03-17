"""
yfinance adapter — OHLCV, India VIX, sectors, FX, commodities.
This is the primary source for all price/index data.
"""
from __future__ import annotations
import asyncio
from typing import Optional
import pandas as pd
import yfinance as yf
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
from config.settings import get_settings
from config.constants import (
    SECTOR_TICKERS, VIX_COMPLACENCY_MAX, VIX_NORMAL_MAX,
    VIX_ELEVATED_MAX, VIX_CIRCUIT_BREAKER, VIX_CRISIS,
)
from data.adapters.base_adapter import BaseAdapter

logger = structlog.get_logger(__name__)
settings = get_settings()


def _classify_vix(vix: float) -> str:
    if vix < VIX_COMPLACENCY_MAX:  return "COMPLACENCY"
    if vix < VIX_NORMAL_MAX:       return "NORMAL"
    if vix < VIX_ELEVATED_MAX:     return "ELEVATED"
    if vix < VIX_CRISIS:           return "HIGH"
    return "CRISIS"


class YFinanceClient(BaseAdapter):
    """Async-compatible yfinance wrapper. All timestamps in Asia/Kolkata."""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def _fetch_sync(self, ticker: str, period: str, interval: str) -> pd.DataFrame:
        cache_key = self._cache_key("ohlcv", ticker, period, interval)
        ttl_seconds = settings.yfinance_cache_ttl_minutes * 60

        def _load() -> pd.DataFrame:
            df = yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
            if df.empty:
                raise ValueError(f"yfinance empty for {ticker}")
            if getattr(df.index, "tz", None) is None:
                df.index = df.index.tz_localize("Asia/Kolkata")
            else:
                df.index = df.index.tz_convert("Asia/Kolkata")
            df.columns = df.columns.str.lower()
            df["ticker"] = ticker
            df = df.dropna(subset=["close"])
            logger.info("yfinance.fetched", ticker=ticker, rows=len(df))
            return df

        return self._cached(key=cache_key, ttl_seconds=ttl_seconds, loader=_load)

    async def get_ohlcv(self, ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
        """Async OHLCV. ticker: 'HDFCBANK.NS', '^NSEI', '^INDIAVIX' etc."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, ticker, period, interval)

    async def get_india_vix(self, period: str = "1y") -> pd.DataFrame:
        """India VIX with regime label. Triggers circuit breaker warning if VIX >= 25."""
        df = await self.get_ohlcv(settings.yfinance_india_vix_ticker, period=period)
        vix_df = df[["close"]].rename(columns={"close": "vix"})
        vix_df["regime"] = vix_df["vix"].apply(_classify_vix)
        current = float(vix_df["vix"].iloc[-1])
        if current >= VIX_CIRCUIT_BREAKER:
            logger.warning("vix.circuit_breaker_active", vix=current,
                           action="OVERRIDE_ALL_VERDICTS_TO_HOLD")
        return vix_df

    async def get_all_sectors(self, period: str = "1y") -> dict[str, pd.DataFrame]:
        """Fetch all 10 NSE sector indices concurrently."""
        tasks = {n: self.get_ohlcv(t, period=period) for n, t in SECTOR_TICKERS.items()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        out: dict[str, pd.DataFrame] = {}
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error("yfinance.sector_failed", sector=name, error=str(result))
            else:
                out[name] = result
        return out

    async def get_macro_snapshot(self, period: str = "1y") -> pd.DataFrame:
        """All macro series merged: usdinr, brent_crude, gold, nifty50, banknifty, india_vix."""
        tickers = {
            "usdinr":      settings.yfinance_usdinr_ticker,
            "brent_crude": settings.yfinance_crude_ticker,
            "gold":        settings.yfinance_gold_ticker,
            "nifty50":     settings.yfinance_nifty_ticker,
            "banknifty":   settings.yfinance_banknifty_ticker,
            "india_vix":   settings.yfinance_india_vix_ticker,
        }
        tasks = {n: self.get_ohlcv(t, period=period) for n, t in tickers.items()}
        results = await asyncio.gather(*tasks.values(), return_exceptions=True)
        merged: Optional[pd.DataFrame] = None
        for name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning("yfinance.macro_failed", name=name, error=str(result))
                continue
            s = result["close"].rename(name)
            s.index = s.index.normalize()
            merged = s.to_frame() if merged is None else merged.join(s, how="outer")
        if merged is None:
            raise RuntimeError("All macro fetches failed")
        return merged.ffill().dropna(how="all")

    async def get_batch_ohlcv(self, tickers: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
        """Fetch multiple tickers concurrently. Skips failures with warning."""
        tasks = [self.get_ohlcv(t, period=period) for t in tickers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return {t: r for t, r in zip(tickers, results) if not isinstance(r, Exception)}

    async def health_check(self) -> dict:
        try:
            df  = await self.get_ohlcv("HDFCBANK.NS", period="5d")
            vix = await self.get_india_vix(period="5d")
            return {
                "status": "ok",
                "hdfcbank_rows": len(df),
                "vix_latest": float(vix["vix"].iloc[-1]),
                "vix_regime": vix["regime"].iloc[-1],
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
