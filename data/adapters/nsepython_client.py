"""
nsepython adapter — FALLBACK only. Never call directly; invoked by nsefin_client.
pip: nsepython>=2.97 | Known: anti-bot sensitive, longer delays required.
"""
from __future__ import annotations
import asyncio, time, random
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential
import structlog
from config.settings import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


class NSEPythonClient:

    def _delay(self) -> None:
        time.sleep(random.uniform(
            settings.nse_request_delay_min + 1.0,
            settings.nse_request_delay_max + 2.0,
        ))

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=20))
    def _fetch_option_chain_sync(self, symbol: str) -> pd.DataFrame:
        import nsepython
        self._delay()
        raw = nsepython.option_chain(symbol)
        if not raw:
            raise ValueError(f"nsepython empty for {symbol}")
        records = []
        for item in raw.get("records", {}).get("data", []):
            for otype in ("CE", "PE"):
                if otype in item:
                    row = item[otype].copy()
                    row["option_type"] = otype
                    row["strike_price"] = item.get("strikePrice", 0)
                    records.append(row)
        df = pd.DataFrame(records)
        df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
        logger.info("nsepython.option_chain", symbol=symbol, rows=len(df), note="FALLBACK")
        return df

    async def get_option_chain(self, symbol: str) -> pd.DataFrame:
        logger.warning("nsepython.fallback_invoked", symbol=symbol)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_option_chain_sync, symbol)

    async def health_check(self) -> dict:
        try:
            df = await self.get_option_chain("NIFTY")
            return {"status": "ok", "rows": len(df), "source": "nsepython_fallback"}
        except Exception as e:
            return {"status": "error", "error": str(e)}