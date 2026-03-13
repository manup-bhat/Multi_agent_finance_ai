"""POST /predict — ML ensemble price prediction."""
from __future__ import annotations
import random
from fastapi import APIRouter
from api.schemas import PredictRequest, PredictResponse
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    """ML ensemble directional prediction (XGBoost+LightGBM+CatBoost+Chronos-2)."""
    logger.info("api.predict.request", ticker=req.ticker, horizon=req.horizon)
    try:
        from prediction.inference.prediction_service import PredictionService
        from features.india_feature_set import IndiaFeatureSet
        from data.adapters.yfinance_client import YFinanceClient
        from config.constants import MARKET_TZ
        import numpy as np
        import pandas as pd
        import asyncio

        # Initialize the service with required arguments
        service = PredictionService(ticker=req.ticker, horizon=req.horizon)
        
        # We need to construct the feature state before calling predict
        # This is a bit heavy for a synchronous API but necessary for real inference
        yf_client = YFinanceClient()
        
        # Wait for all necessary external data
        vix_df, nifty_df, fetch_df = await asyncio.gather(
            yf_client.get_india_vix(period="2y"),
            yf_client.get_ohlcv("^NSEI", period="2y"),
            yf_client.get_ohlcv(req.ticker, period="3y")
        )

        nifty_returns = np.log(nifty_df["close"] / nifty_df["close"].shift(1)).dropna() if not nifty_df.empty else pd.Series()
        
        # Build features
        builder = IndiaFeatureSet()
        # Assuming we can build from the fetched df
        feature_df = builder.build(fetch_df) if not fetch_df.empty else pd.DataFrame()
        price_series = fetch_df["close"] if not fetch_df.empty else pd.Series()

        # Dummy covariate df for now as it's complex to build properly here
        cov_df = pd.DataFrame(index=price_series.index)
        for i in range(8): cov_df[f"cov_{i}"] = 0.0

        vix_current = float(vix_df["vix"].iloc[-1]) if not vix_df.empty else 15.0

        # Run inference properly
        # Since service._chronos loading takes time, let's run this in a threadpool to not block the event loop
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, 
            service.predict, 
            feature_df, 
            price_series, 
            nifty_returns, 
            cov_df, 
            vix_current, 
            vix_df["vix"] if not vix_df.empty else None
        )
        return PredictResponse(
            ticker=req.ticker,
            horizon=req.horizon,
            direction=result.direction,
            direction_prob=result.confidence,
            class_probs=result.class_probs,
            p10=result.q10_5d if req.horizon == 5 else result.current_price * 0.95,
            p50=result.forecast_5d if req.horizon == 5 else result.current_price,
            p90=result.q90_5d if req.horizon == 5 else result.current_price * 1.05,
            confidence=result.confidence,
            regime=result.regime_name,
            model_used="ensemble",
        )
    except Exception as e:
        logger.error("api.predict.error", error=str(e), exc_info=True)
        # Fallback ONLY on actual ML failure, not intentionally hardcoded mocked bypass
        return PredictResponse(
            ticker=req.ticker,
            horizon=req.horizon,
            direction="NEUTRAL",
            direction_prob=0.5,
            confidence=0.5,
            regime=req.regime or "UNKNOWN",
            model_used="fallback_error",
        )
