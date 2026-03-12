"""
Feature engineering pipeline — orchestrates data fetching + feature building.
Called by prediction_agent and training pipeline.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
import pandas as pd
import structlog

from features.india_feature_set import IndiaFeatureSet
from features.feature_validator import validate_features

logger = structlog.get_logger(__name__)


class FeatureEngineer:
    """
    Async feature engineering pipeline.
    Fetches all required data sources and builds the 70-feature DataFrame.
    """

    def __init__(self):
        self._fset = IndiaFeatureSet()

    async def build_for_ticker(self,
                                ticker: str,
                                lookback_days: int = 600) -> pd.DataFrame:
        """
        Build 70-feature DataFrame for a single ticker.
        Fetches OHLCV, macro, FII/DII, sector data concurrently.
        """
        from data.adapters.yfinance_client  import YFinanceClient
        from data.adapters.nselib_client    import NSELibClient
        from config.constants import SECTOR_TICKERS

        yf   = YFinanceClient()
        nsec = NSELibClient()
        period = f"{lookback_days}d"

        # Fetch all data concurrently
        ohlcv_task, macro_task, fii_task, sector_tasks = (
            asyncio.create_task(yf.get_ohlcv(ticker, period=period)),
            asyncio.create_task(yf.get_macro_snapshot(period=period)),
            asyncio.create_task(nsec.get_fii_dii(days=lookback_days)),
            [asyncio.create_task(yf.get_ohlcv(t, period=period))
             for t in list(SECTOR_TICKERS.values())[:10]],
        )

        ohlcv_df = await ohlcv_task
        macro_df = await macro_task
        fii_df   = await fii_task
        sector_results = await asyncio.gather(*sector_tasks, return_exceptions=True)

        # Build sector DataFrame
        sector_df = pd.DataFrame()
        for i, (name, tkr) in enumerate(list(SECTOR_TICKERS.items())[:10]):
            if not isinstance(sector_results[i], Exception) and not sector_results[i].empty:
                sector_df[tkr] = sector_results[i]["close"]

        # Delivery %
        delivery_series = None
        try:
            sym = ticker.replace(".NS", "").replace(".BO", "")
            del_df = await nsec.get_delivery_data(sym, period="1M")
            del_col = next((c for c in del_df.columns if "deliv" in c.lower()), None)
            if del_col:
                delivery_series = del_df[del_col].astype(float)
        except Exception as e:
            logger.warning("feature_engineer.delivery_failed",
                            ticker=ticker, error=str(e))

        # Build features
        features = self._fset.build(
            ohlcv_df=ohlcv_df,
            macro_df=macro_df,
            fii_dii_df=fii_df,
            sector_df=sector_df,
            delivery_series=delivery_series,
        )

        # Validate
        validate_features(features, ticker=ticker)

        return features