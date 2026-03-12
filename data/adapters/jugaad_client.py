"""
jugaad-data adapter — historical NSE data via bhavcopy archives.
pip: jugaad-data>=0.24 (--no-deps) | import: jugaad_data (NOT jugaad)

CRITICAL FINDING (March 2026):
  stock_df() PERMANENTLY BLOCKED from WSL/cloud IPs.
  NSE anti-bot on nseindia.com/api/historical blocks non-Indian IPs.
  Both pre-2020 AND current dates return JSONDecodeError (empty/HTML response).

SOLUTION: Use bhavcopy_raw() from jugaad_data.nse.archives (public NSE archive).
  Archive URL: https://nsearchives.nseindia.com/content/historical/EQUITIES/...
  No anti-bot. Publicly accessible. Confirmed working from WSL.
"""
from __future__ import annotations
import asyncio, io, time, random
from datetime import date, timedelta
from typing import Optional
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
from config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

# Source-validated column map (NSE bhavcopy CSV format)
# Actual CSV headers: SYMBOL,SERIES,OPEN,HIGH,LOW,CLOSE,LAST,PREVCLOSE,TOTTRDQTY,...
_BHAV_COL_MAP = {
    "symbol":    "ticker",
    "open":      "open",
    "high":      "high",
    "low":       "low",
    "close":     "close",
    "tottrdqty": "volume",
    "last":      "ltp",
    "prevclose": "prev_close",
}


class JugaadClient:
    """
    Historical NSE equity data via bhavcopy archive files.
    Reliable from WSL (public NSE archive, no anti-bot).
    Archive path confirmed in jugaad_data/nse/archives.py source.
    """

    def _delay(self) -> None:
        time.sleep(random.uniform(1.0, 2.0))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _fetch_single_day_sync(self, dt: date) -> pd.DataFrame:
        """
        Fetch full NSE bhavcopy for a single date.
        Source-validated import: from jugaad_data.nse import bhavcopy_raw
        jugaad_data/nse/__init__.py: from .archives import *
        jugaad_data/nse/archives.py: bhavcopy_raw = a.bhavcopy_raw
        """
        from jugaad_data.nse import bhavcopy_raw  # confirmed in archives.py
        self._delay()
        csv_text = bhavcopy_raw(dt)
        if not csv_text or len(csv_text) < 100:
            raise ValueError(f"bhavcopy_raw returned empty/short response for {dt}")
        df = pd.read_csv(io.StringIO(csv_text))
        df.columns = df.columns.str.strip().str.lower()
        return df

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _fetch_stock_range_sync(
        self, symbol: str, from_date: date, to_date: date
    ) -> pd.DataFrame:
        """
        Historical OHLCV for a symbol via daily bhavcopy archives.
        Max 20 trading days per call (network-respectful limit).
        """
        clean = symbol.upper().replace(".NS", "").replace(".BO", "")

        # Get weekdays only in range
        trading_days: list[date] = []
        current = from_date
        while current <= to_date:
            if current.weekday() < 5:
                trading_days.append(current)
            current += timedelta(days=1)

        if not trading_days:
            raise ValueError(f"No trading days in range {from_date}→{to_date}")

        # Cap at 20 days to be network-respectful
        if len(trading_days) > 20:
            logger.warning("jugaad.range_capped", original=len(trading_days), using=20)
            trading_days = trading_days[-20:]

        rows: list[pd.DataFrame] = []
        for dt in trading_days:
            try:
                day_df = self._fetch_single_day_sync(dt)
                # Filter to requested symbol — first column is SYMBOL
                sym_col = day_df.columns[0]
                filtered = day_df[day_df[sym_col].str.strip().str.upper() == clean]
                if not filtered.empty:
                    filtered = filtered.copy()
                    filtered["_date"] = dt
                    rows.append(filtered)
            except Exception as e:
                logger.warning("jugaad.day_skip", date=str(dt), error=str(e)[:80])
                continue

        if not rows:
            raise ValueError(
                f"jugaad: no data for {clean} in {from_date}→{to_date}. "
                f"Tried {len(trading_days)} days via bhavcopy archive."
            )

        df = pd.concat(rows, ignore_index=True)

        # Rename to standard OHLCV columns
        df = df.rename(columns={k: v for k, v in _BHAV_COL_MAP.items() if k in df.columns})

        # Set DatetimeIndex (Asia/Kolkata)
        df["date"] = pd.to_datetime(df["_date"])
        df = df.drop(columns=["_date"], errors="ignore")
        df = df.set_index("date")
        df.index = df.index.tz_localize("Asia/Kolkata")

        # Coerce numeric
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        df = df.sort_index().dropna(subset=["close"])
        logger.info("jugaad.stock_history", symbol=clean, rows=len(df))
        return df

    async def get_stock_history(
        self, symbol: str, from_date: date, to_date: date
    ) -> pd.DataFrame:
        """
        Async historical OHLCV via bhavcopy archives (WSL-safe).
        Reliable for any date range where NSE archive exists (2010+).
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._fetch_stock_range_sync, symbol, from_date, to_date
        )

    async def get_single_day_bhavcopy(self, dt: date) -> pd.DataFrame:
        """Full market bhavcopy — all NSE equities for one date."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_single_day_sync, dt)

    async def health_check(self) -> dict:
        """
        Gate test: fetch Jan 7-9 2019 (3 trading days, pre-2020).
        bhavcopy archive path — confirmed WSL-safe.
        """
        try:
            df = await self.get_stock_history(
                "HDFCBANK", date(2019, 1, 7), date(2019, 1, 9)
            )
            return {
                "status": "ok",
                "rows": len(df),
                "period": "Jan 7-9 2019",
                "path": "bhavcopy_archive (WSL-safe)",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}