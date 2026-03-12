"""
nsefin adapter — option chains via direct NSE API.
pip: nsefin>=0.1.0 | import: nsefin

CONFIRMED BUGS in nsefin v0.1.5:
  BUG 1 get_fii_dii_activity(): missing '/' in URL → DNS fail
  BUG 2 get_option_chain(): df.drop(['CE.strikePrice',...]) → KeyError

NSE OPTION CHAIN BEHAVIOUR (confirmed March 2026):
  During market hours (09:15–15:30 IST): returns full JSON with records.data
  Outside market hours: returns {} (empty dict) — EXPECTED, not a code error.

TENACITY FIX:
  Wrong: @retry(..., retry=lambda e: ...)
  The `retry=` kwarg takes a tenacity retry_base object, not a plain lambda.
  Fix: use retry=retry_if_not_exception_type(MarketClosedError).
  This tells tenacity to never retry MarketClosedError — it propagates immediately.

ENDPOINTS (source-validated from jugaad_data/nse/live.py):
  Index:  /api/option-chain-indices?symbol=NIFTY
  Equity: /api/option-chain-equities?symbol=HDFCBANK
"""
from __future__ import annotations
import asyncio, time, random, re
from typing import Optional
import pandas as pd
from tenacity import retry, retry_if_not_exception_type, stop_after_attempt, wait_exponential
import structlog
from config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_NSE_INDEX_SYMBOLS = {"NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYIT"}


class MarketClosedError(ValueError):
    """NSE returns {} outside 09:15-15:30 IST. Expected — not a code bug."""
    pass


def _parse_nse_option_chain(data: dict | list, symbol: str) -> pd.DataFrame:
    """
    Parse NSE option chain JSON.
    Raises MarketClosedError (not ValueError) when NSE returns empty {}.
    This is critical — tenacity must NOT retry on MarketClosedError.
    """
    # Empty dict = market closed — raise specific error, not generic ValueError
    if isinstance(data, dict) and not data:
        raise MarketClosedError(
            f"NSE returned {{}} for {symbol} — market closed / outside 09:15-15:30 IST"
        )

    if isinstance(data, list):
        records_data = data
        underlying   = None
    else:
        records      = data.get("records", {})
        records_data = records.get("data", [])
        underlying   = records.get("underlyingValue", None)

        if not records_data:
            # Empty records also = market closed (pre-open or after-hours)
            raise MarketClosedError(
                f"NSE option chain records.data empty for {symbol}. "
                f"Market closed. Keys: {list(data.keys())}"
            )

    rows = []
    for item in records_data:
        if not isinstance(item, dict):
            continue
        strike = item.get("strikePrice", item.get("strike_price", 0))
        expiry = item.get("expiryDate",  item.get("expiry_date",  ""))
        for otype in ("CE", "PE"):
            if otype not in item:
                continue
            row = dict(item[otype])
            row["strike_price"]     = strike
            row["expiry_date"]      = expiry
            row["option_type"]      = otype
            row["underlying_value"] = underlying
            rows.append(row)

    if not rows:
        raise MarketClosedError(
            f"No CE/PE rows for {symbol}. "
            f"Sample keys: {list(records_data[0].keys()) if records_data else 'empty'}"
        )

    df = pd.DataFrame(rows)
    df.columns = [
        re.sub(r"([A-Z])", r"_\1", c).lower().lstrip("_").replace(" ", "_")
        for c in df.columns
    ]
    logger.info("nsefin.option_chain_parsed", symbol=symbol, rows=len(df))
    return df


def _fetch_option_chain_once(symbol: str) -> pd.DataFrame:
    """
    Single attempt at NSE option chain fetch — no retry logic here.
    Raises MarketClosedError (no retry) or other Exception (retryable).
    Separated from retry decorator so MarketClosedError is never retried.
    """
    from data.adapters.nse_session import nse_get_json
    clean    = symbol.upper().replace(".NS", "").replace(".BO", "")
    endpoint = (
        "/option-chain-indices"
        if clean in _NSE_INDEX_SYMBOLS
        else "/option-chain-equities"
    )
    data = nse_get_json(endpoint, params={"symbol": clean},
                        timeout=settings.nse_timeout_seconds)
    # _parse_nse_option_chain raises MarketClosedError or returns df
    return _parse_nse_option_chain(data, clean)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=3, max=20),
    retry=retry_if_not_exception_type(MarketClosedError),
)
def _fetch_option_chain_with_retry(symbol: str) -> pd.DataFrame:
    """
    Retry wrapper — retries on any non-MarketClosedError exception.
    MarketClosedError propagates immediately (no retry needed — NSE won't change).
    """
    return _fetch_option_chain_once(symbol)


class NSEFinClient:
    """
    Option chain via direct NSE API (bypasses nsefin's two confirmed bugs).
    MarketClosedError is correctly propagated — never retried, never swallowed.
    """

    def _delay(self) -> None:
        time.sleep(random.uniform(
            settings.nse_request_delay_min, settings.nse_request_delay_max
        ))

    async def get_option_chain(self, symbol: str) -> pd.DataFrame:
        """
        Primary: direct NSE API with jugaad-validated session.
        MarketClosedError → re-raised to caller (validator treats as WARN).
        Other errors → fallback to nsepython.
        """
        loop = asyncio.get_event_loop()

        def _sync():
            self._delay()
            return _fetch_option_chain_with_retry(symbol)

        try:
            df = await loop.run_in_executor(None, _sync)
            logger.info("nsefin.option_chain_ok",
                        symbol=symbol, rows=len(df), source="direct_nse")
            return df
        except MarketClosedError:
            raise  # validator catches this specifically → WARN not FAIL
        except Exception as e:
            logger.warning("nsefin.direct_failed_using_nsepython",
                           symbol=symbol, error=str(e))
            from data.adapters.nsepython_client import NSEPythonClient
            return await NSEPythonClient().get_option_chain(symbol)

    # ── Bhavcopy ──────────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _fetch_bhavcopy_sync(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        import nsefin
        self._delay()
        result = (
            nsefin.nse.get_equity_bhav_copy(trade_date)
            if trade_date else nsefin.nse.get_equity_bhav_copy()
        )
        if result is None or (isinstance(result, pd.DataFrame) and result.empty):
            raise ValueError("get_equity_bhav_copy empty")
        df = result if isinstance(result, pd.DataFrame) else pd.DataFrame(result)
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        logger.info("nsefin.bhavcopy", rows=len(df))
        return df

    async def get_bhavcopy(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_bhavcopy_sync, trade_date)

    async def health_check(self) -> dict:
        try:
            chain = await self.get_option_chain("NIFTY")
            return {
                "status": "ok",
                "rows": len(chain),
                "cols": list(chain.columns[:6]),
                "source": "direct_nse_jugaad_session",
            }
        except MarketClosedError as e:
            return {
                "status": "market_closed",
                "note": str(e),
                "action": "retry during 09:15-15:30 IST on a trading day",
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}