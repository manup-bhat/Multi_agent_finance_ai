"""
nselib adapter — delivery %, bulk deals, India VIX, holidays, FII derivatives.
pip: nselib>=2.4.2 | import: nselib

CONFIRMED WORKING (live diagnostic, March 2026):
  nselib.trading_holiday_calendar()                         → 241 rows ✓
  nselib.capital_market.price_volume_and_deliverable_*()    → 21 rows ✓
  nselib.derivatives.fii_derivatives_statistics(date_str)   → 1 arg (single date) ✓
  nselib.derivatives.participant_wise_open_interest(date)   → 1 arg (single date) ✓

FII/DII NSE API RESPONSE FORMAT (confirmed from live diagnostic):
  [
    {"category": "DII",     "date": "12-Mar-2026", "buyValue": "19439.56",
     "sellValue": "11989.79", "netValue": "7449.77"},
    {"category": "FII/FPI", "date": "12-Mar-2026", "buyValue": "15373.05",
     "sellValue": "22422.92", "netValue": "-7049.87"}
  ]
  → list of 2 rows (one per category). NOT wide format.
  → Must PIVOT: category rows → columns (fii_buy, fii_sell, fii_net, dii_buy, ...)
"""
from __future__ import annotations
import asyncio, time, random
from datetime import date, datetime, timedelta
from typing import Optional
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
from config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def _pivot_fii_dii(data: list[dict]) -> pd.DataFrame:
    """
    Convert NSE fiidiiTradeReact response to wide-format FII/DII DataFrame.

    Input (confirmed live format):
      [
        {"category":"DII",     "date":"12-Mar-2026", "buyValue":"19439.56",
         "sellValue":"11989.79", "netValue":"7449.77"},
        {"category":"FII/FPI", "date":"12-Mar-2026", "buyValue":"15373.05",
         "sellValue":"22422.92", "netValue":"-7049.87"}
      ]

    Output columns:
      fii_buy_value, fii_sell_value, fii_net_value,
      dii_buy_value, dii_sell_value, dii_net_value

    Index: DatetimeIndex(Asia/Kolkata)
    """
    # Group by date — API may return multiple dates
    date_map: dict[str, dict] = {}
    for row in data:
        raw_date = row.get("date", "")
        cat      = str(row.get("category", "")).upper().strip()
        prefix   = "fii" if "FII" in cat or "FPI" in cat else "dii"

        if raw_date not in date_map:
            date_map[raw_date] = {"date": raw_date}

        for src, dst in [("buyValue", f"{prefix}_buy_value"),
                         ("sellValue", f"{prefix}_sell_value"),
                         ("netValue",  f"{prefix}_net_value")]:
            val = row.get(src, "0")
            try:
                date_map[raw_date][dst] = float(str(val).replace(",", ""))
            except (ValueError, TypeError):
                date_map[raw_date][dst] = 0.0

    if not date_map:
        raise ValueError("FII/DII pivot: no date entries found in response")

    df = pd.DataFrame(list(date_map.values()))

    # Parse date → index
    df["date"] = pd.to_datetime(df["date"], format="%d-%b-%Y", errors="coerce")
    df = df.dropna(subset=["date"]).set_index("date")
    df.index = df.index.tz_localize("Asia/Kolkata")

    # Ensure all 6 standard columns exist
    for col in ("fii_buy_value", "fii_sell_value", "fii_net_value",
                "dii_buy_value", "dii_sell_value", "dii_net_value"):
        if col not in df.columns:
            df[col] = 0.0

    return df.sort_index()


class NSELibClient:

    def _delay(self) -> None:
        time.sleep(random.uniform(
            settings.nse_request_delay_min, settings.nse_request_delay_max
        ))

    # ── FII/DII via correct NSE session + pivot ───────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=20))
    def _fetch_fii_dii_sync(self) -> pd.DataFrame:
        """
        NSE /api/fiidiiTradeReact — confirmed returning 2-row list.
        Pivot category rows → wide FII/DII columns.
        """
        from data.adapters.nse_session import nse_get_json
        self._delay()
        data = nse_get_json("/fiidiiTradeReact", timeout=settings.nse_timeout_seconds)

        if not isinstance(data, list) or len(data) == 0:
            raise ValueError(
                f"FII/DII: expected list, got {type(data).__name__}. "
                f"Value: {str(data)[:100]}"
            )

        df = _pivot_fii_dii(data)

        if df.empty:
            raise ValueError("FII/DII: empty DataFrame after pivot")

        logger.info(
            "nselib.fii_dii_fetched",
            rows=len(df),
            cols=list(df.columns),
            source="nse_direct_pivot",
            latest_fii_net=float(df["fii_net_value"].iloc[-1]),
            latest_dii_net=float(df["dii_net_value"].iloc[-1]),
        )
        return df

    async def get_fii_dii(self, days: int = 90) -> pd.DataFrame:
        """FII/DII cash market — direct NSE API with pivot."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_fii_dii_sync)

    async def get_fii_dii_zscore(self, lookback_days: int = 90) -> pd.DataFrame:
        """FII/DII net flows with 5-day rolling Z-score."""
        df  = await self.get_fii_dii(days=lookback_days)
        result = pd.DataFrame(index=df.index)
        for name in ("fii", "dii"):
            col = f"{name}_net_value"
            if col in df.columns:
                result[f"{name}_net"] = df[col]
                mu  = result[f"{name}_net"].rolling(5).mean()
                std = result[f"{name}_net"].rolling(5).std().replace(0, 1)
                result[f"{name}_zscore_5d"] = (result[f"{name}_net"] - mu) / std
        if "fii_net" in result.columns and "dii_net" in result.columns:
            result["consensus"] = result.apply(
                lambda r: (
                    "STRONG_BULL"       if r["fii_net"] > 0 and r["dii_net"] > 0
                    else "STRONG_BEAR"  if r["fii_net"] < 0 and r["dii_net"] < 0
                    else "FII_BULL_DII_BEAR" if r["fii_net"] > 0
                    else "DII_BULL_FII_BEAR"
                ), axis=1,
            )
        return result.dropna(how="all")

    # ── FII derivatives (1 arg — single date confirmed) ───────────────
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
    def _fetch_fii_derivatives_sync(self, trade_date: str) -> pd.DataFrame:
        import nselib.derivatives as deriv
        self._delay()
        df = deriv.fii_derivatives_statistics(trade_date)
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            raise ValueError(f"fii_derivatives_statistics empty for {trade_date}")
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        logger.info("nselib.fii_derivatives", date=trade_date, rows=len(df))
        return df

    async def get_fii_derivatives(self) -> pd.DataFrame:
        today = datetime.now().strftime("%d-%m-%Y")
        loop  = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_fii_derivatives_sync, today)

    # ── Participant OI (1 arg — single date confirmed) ────────────────
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=2, max=10))
    def _fetch_participant_oi_sync(self, trade_date: str) -> pd.DataFrame:
        import nselib.derivatives as deriv
        self._delay()
        df = deriv.participant_wise_open_interest(trade_date)
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            raise ValueError(f"participant_wise_open_interest empty for {trade_date}")
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        logger.info("nselib.participant_oi", date=trade_date, rows=len(df))
        return df

    async def get_participant_oi(self) -> pd.DataFrame:
        today = datetime.now().strftime("%d-%m-%Y")
        loop  = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_participant_oi_sync, today)

    # ── Delivery % (confirmed working) ───────────────────────────────
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
    def _fetch_delivery_sync(self, symbol: str, period: str) -> pd.DataFrame:
        from nselib import capital_market
        self._delay()
        df = capital_market.price_volume_and_deliverable_position_data(
            symbol=symbol.replace(".NS", "").replace(".BO", ""), period=period
        )
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            raise ValueError(f"delivery data empty for {symbol}")
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        df.columns = [c.replace("ï»¿", "").replace('"', "").strip() for c in df.columns]
        return df

    async def get_delivery_data(self, symbol: str, period: str = "1M") -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_delivery_sync, symbol, period)

    # ── Bulk deals ────────────────────────────────────────────────────
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=8))
    def _fetch_bulk_deals_sync(self) -> pd.DataFrame:
        from nselib import capital_market
        self._delay()
        df = capital_market.bulk_deal_data()
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            raise ValueError("bulk_deal_data empty")
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        return df

    async def get_bulk_deals(self) -> pd.DataFrame:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_bulk_deals_sync)

    # ── Holidays (241 rows confirmed) ─────────────────────────────────
    @retry(stop=stop_after_attempt(2), wait=wait_exponential(min=1, max=5))
    def _fetch_holidays_sync(self, year: int) -> list[date]:
        try:
            import nselib
            self._delay()
            df = nselib.trading_holiday_calendar()
            if df is not None and not df.empty:
                date_col = "tradingDate" if "tradingDate" in df.columns else df.columns[1]
                prod_col = "Product" if "Product" in df.columns else None
                equity   = (
                    df[df[prod_col].str.contains("Capital Market", na=False)]
                    if prod_col else df
                )
                if equity.empty:
                    equity = df
                parsed = pd.to_datetime(equity[date_col], dayfirst=True, errors="coerce")
                result = [
                    d.date() for d in parsed.dropna()
                    if hasattr(d, "year") and d.year == year
                ]
                if result:
                    logger.info("nselib.holidays_ok", year=year, count=len(result))
                    return sorted(result)
        except Exception as e:
            logger.warning("nselib.holidays_failed", error=str(e))
        try:
            import holidays as hdays
            india  = hdays.India(years=year)
            result = sorted(india.keys())
            logger.info("holidays.from_pylib", year=year, count=len(result))
            return result
        except Exception as e:
            logger.warning("holidays.pylib_failed", error=str(e))
            return []

    async def get_trading_holidays(self, year: Optional[int] = None) -> list[date]:
        if year is None:
            year = datetime.now().year
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_holidays_sync, year)

    async def is_trading_day(self, check_date: Optional[date] = None) -> bool:
        if check_date is None:
            check_date = datetime.now().date()
        if check_date.weekday() >= 5:
            return False
        return check_date not in await self.get_trading_holidays(check_date.year)

    async def health_check(self) -> dict:
        result: dict = {}
        try:
            df = await self.get_fii_dii()
            result["fii_dii"] = (
                f"ok ({len(df)} rows, "
                f"fii_net={df['fii_net_value'].iloc[-1]:.2f}, "
                f"dii_net={df['dii_net_value'].iloc[-1]:.2f})"
            )
        except Exception as e:
            result["fii_dii"] = f"error: {str(e)[:120]}"
        try:
            df = await self.get_delivery_data("HDFCBANK", period="1M")
            result["delivery"] = f"ok ({len(df)} rows)"
        except Exception as e:
            result["delivery"] = f"error: {str(e)[:80]}"
        try:
            holidays = await self.get_trading_holidays(2026)
            result["holidays"] = f"ok ({len(holidays)})"
        except Exception as e:
            result["holidays"] = f"error: {str(e)[:80]}"
        status = "ok" if all("error" not in v for v in result.values()) else "partial"
        return {"status": status, **result}