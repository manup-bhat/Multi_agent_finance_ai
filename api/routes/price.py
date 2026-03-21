"""
GET /api/price/{ticker} — OHLCV candlestick data for TradingView Lightweight Charts.

Returns candles in SECONDS (Unix timestamp), not milliseconds.
Supports period: 1D, 1W, 1M, 3M, 6M, 1Y, 2Y
Also returns /api/price/{ticker}/volume-profile for Volume Profile chart.
"""
from __future__ import annotations

import numpy as np
from fastapi import APIRouter, HTTPException, Query
import structlog

from data.adapters.yfinance_client import YFinanceClient

logger = structlog.get_logger(__name__)
router = APIRouter()

# Maps frontend period labels → (yfinance period, yfinance interval)
PERIOD_MAP: dict[str, tuple[str, str]] = {
    "1D":  ("1d",   "5m"),
    "1W":  ("5d",   "30m"),
    "1M":  ("1mo",  "1d"),
    "3M":  ("3mo",  "1d"),
    "6M":  ("6mo",  "1d"),
    "1Y":  ("1y",   "1d"),
    "2Y":  ("2y",   "1d"),
    # Legacy aliases
    "1d":  ("1d",   "5m"),
    "1w":  ("5d",   "30m"),
    "1mo": ("1mo",  "1d"),
    "3mo": ("3mo",  "1d"),
    "6mo": ("6mo",  "1d"),
    "1y":  ("1y",   "1d"),
    "2y":  ("2y",   "1d"),
}

INDEX_ALIAS: dict[str, str] = {
    "NIFTY":     "^NSEI",
    "NIFTY50":   "^NSEI",
    "BANKNIFTY": "^NSEBANK",
    "SENSEX":    "^BSESN",
    "FINNIFTY":  "NIFTY_FIN_SERVICE.NS",
}


def _resolve_ticker(ticker: str) -> str:
    """Normalise NSE ticker to yfinance format."""
    upper = ticker.strip().upper()
    if upper in INDEX_ALIAS:
        return INDEX_ALIAS[upper]
    # Already has suffix
    if "." in upper:
        return upper
    # Default to NSE
    return f"{upper}.NS"


@router.get("/api/price/{ticker}")
async def get_price_data(
    ticker: str,
    period: str = Query(default="3M", description="1D|1W|1M|3M|6M|1Y|2Y"),
):
    """
    OHLCV data for Lightweight Charts.
    Returns Unix timestamps in SECONDS (not milliseconds).
    """
    yf_period, yf_interval = PERIOD_MAP.get(period, ("3mo", "1d"))
    yf_ticker = _resolve_ticker(ticker)

    logger.info("api.price.fetch", ticker=ticker, yf_ticker=yf_ticker,
                period=period, yf_period=yf_period, interval=yf_interval)

    try:
        yf_client = YFinanceClient()
        df = await yf_client.get_ohlcv(yf_ticker, period=yf_period, interval=yf_interval)
    except Exception as exc:
        logger.warning("api.price.yfinance_fail", ticker=yf_ticker, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Data fetch failed: {exc}") from exc

    if df is None or df.empty:
        raise HTTPException(
            status_code=404,
            detail=f"No price data found for '{ticker}' (resolved: {yf_ticker}). "
                   "Ensure the ticker is a valid NSE symbol e.g. RELIANCE, TCS, INFY.",
        )

    candles = []
    volume_bars = []

    for ts, row in df.iterrows():
        try:
            unix_time = int(ts.timestamp())  # SECONDS — not milliseconds
            o = float(row.get("open", row.get("Open", 0)))
            h = float(row.get("high", row.get("High", 0)))
            lo = float(row.get("low", row.get("Low", 0)))
            c = float(row.get("close", row.get("Close", 0)))
            v = float(row.get("volume", row.get("Volume", 0)))

            if any(not np.isfinite(x) for x in [o, h, lo, c]):
                continue

            candles.append({
                "time": unix_time,
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(lo, 2),
                "close": round(c, 2),
            })
            volume_bars.append({
                "time": unix_time,
                "value": round(v, 0),
                "color": "#059669" if c >= o else "#DC2626",
            })
        except Exception:
            continue  # Skip malformed rows silently

    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"Ticker '{ticker}' returned empty OHLCV after filtering.",
        )

    # Sort ascending (required by Lightweight Charts)
    candles.sort(key=lambda x: x["time"])
    volume_bars.sort(key=lambda x: x["time"])

    return {
        "ticker": ticker,
        "yf_ticker": yf_ticker,
        "period": period,
        "interval": yf_interval,
        "count": len(candles),
        "candles": candles,
        "volume": volume_bars,
    }


@router.get("/api/price/{ticker}/info")
async def get_ticker_info(ticker: str):
    """Basic company/index info for display in chart header."""
    yf_ticker = _resolve_ticker(ticker)
    try:
        import yfinance as yf
        info = yf.Ticker(yf_ticker).info or {}
        return {
            "ticker": ticker,
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "INR"),
            "exchange": info.get("exchange", "NSE"),
        }
    except Exception as exc:
        return {"ticker": ticker, "name": ticker, "error": str(exc)}


@router.get("/ticker/search")
async def search_ticker(q: str = Query(..., min_length=1)):
    """
    Fast prefix search across NSE universe.
    Returns best matches for dropdown autocomplete.
    """
    try:
        import yfinance as yf
        # yfinance search
        results = yf.Search(q, max_results=8).quotes or []
        matches = []
        for r in results:
            sym = r.get("symbol", "")
            # Only include NSE/BSE listings
            exch = r.get("exchange", "").upper()
            if exch in ("NSE", "BSE", "NSI", "BOM") or sym.endswith((".NS", ".BO")):
                matches.append({
                    "symbol": sym.replace(".NS", "").replace(".BO", ""),
                    "name": r.get("longname") or r.get("shortname") or sym,
                    "exchange": exch,
                })
        return {"query": q, "results": matches}
    except Exception as exc:
        return {"query": q, "results": [], "error": str(exc)}
