import asyncio
import pandas as pd
import numpy as np
import os

from prediction.inference.prediction_service import PredictionService
from features.india_feature_set import IndiaFeatureSet
from data.adapters.yfinance_client import YFinanceClient
from data.adapters.nselib_client import NSELibClient

async def get_test(tick):
    service = PredictionService(ticker=tick, horizon=5)
    yf_client = YFinanceClient()
    nse_client = NSELibClient()
    
    vix_df, nifty_df, fetch_df, macro_df, fii_dii = await asyncio.gather(
        yf_client.get_india_vix(period="2y"),
        yf_client.get_ohlcv("^NSEI", period="2y"),
        yf_client.get_ohlcv(tick, period="3y"),
        yf_client.get_macro_snapshot(),
        nse_client.get_fii_dii()
    )

    nifty_returns = np.log(nifty_df["close"] / nifty_df["close"].shift(1)).dropna()
    
    builder = IndiaFeatureSet()
    feature_df = builder.build(fetch_df, macro_df, fii_dii) 
    price_series = fetch_df["close"] 

    cov_df = pd.DataFrame(index=price_series.index)
    for i in range(8): cov_df[f"cov_{i}"] = 0.0

    vix_current = float(vix_df["vix"].iloc[-1])

    result = service.predict(
        feature_df, 
        price_series, 
        nifty_returns, 
        cov_df, 
        vix_current, 
        vix_df["vix"]
    )
    print(f"[{tick}] Direction: {result.direction} (conf: {result.confidence:.3f})")
    print(f"XGB: {result.xgb_proba} | LGBM: {result.lgbm_proba} | CatBoost: {result.catboost_proba}")
    print(f"Chronos: {result.forecast_5d:.2f}")

async def test_predict():
    await asyncio.gather(get_test("RELIANCE.NS"), get_test("TCS.NS"))

if __name__ == "__main__":
    asyncio.run(test_predict())
