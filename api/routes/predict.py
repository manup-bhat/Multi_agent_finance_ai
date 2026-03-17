"""POST /predict — live price prediction using trained models or a data-driven fallback."""
from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import APIRouter
import structlog

from api.schemas import PredictRequest, PredictResponse
from config.constants import PREDICTION_CONFIDENCE_THRESHOLD
from data.adapters.nselib_client import NSELibClient
from data.adapters.yfinance_client import YFinanceClient
from features.covariate_builder import build_chronos_covariates
from features.india_feature_set import IndiaFeatureSet
from prediction.inference.prediction_service import get_prediction_service

logger = structlog.get_logger(__name__)
router = APIRouter()

MODEL_ROOT = Path("models/saved")
CLASS_LABELS = ["Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"]


def _simplify_direction(direction: str, bullish_prob: float, bearish_prob: float) -> str:
    upper = str(direction).upper().replace(" ", "_")
    if upper in {"VERY_BULLISH", "BULLISH"}:
        return "BULLISH"
    if upper in {"VERY_BEARISH", "BEARISH"}:
        return "BEARISH"
    if bullish_prob >= 0.6:
        return "BULLISH"
    if bearish_prob >= 0.6:
        return "BEARISH"
    return "NEUTRAL"


def _infer_regime(price_series: pd.Series) -> str:
    if len(price_series) < 21:
        return "SIDEWAYS"
    ret_20d = float(price_series.iloc[-1] / price_series.iloc[-21] - 1.0)
    if ret_20d > 0.03:
        return "BULL"
    if ret_20d < -0.03:
        return "BEAR"
    return "SIDEWAYS"


def _statistical_live_forecast(price_series: pd.Series, horizon: int) -> dict[str, object]:
    current_price = float(price_series.iloc[-1])
    forward_returns = np.log(price_series.shift(-horizon) / price_series).dropna()

    if len(forward_returns) < 30:
        raise ValueError("insufficient history for live statistical fallback")

    sample = forward_returns.tail(min(252, len(forward_returns)))
    q10, q50, q90 = np.quantile(sample, [0.10, 0.50, 0.90])
    p10 = current_price * float(np.exp(q10))
    p50 = current_price * float(np.exp(q50))
    p90 = current_price * float(np.exp(q90))

    bins = [-np.inf, -0.04, -0.01, 0.01, 0.04, np.inf]
    hist = pd.cut(sample, bins=bins, labels=CLASS_LABELS).value_counts(normalize=True)
    class_probs = {label: round(float(hist.get(label, 0.0)), 4) for label in CLASS_LABELS}
    bullish_prob = class_probs["Bullish"] + class_probs["Very Bullish"]
    bearish_prob = class_probs["Bearish"] + class_probs["Very Bearish"]
    neutral_prob = class_probs["Neutral"]

    direction = "BULLISH" if q50 > 0.01 else "BEARISH" if q50 < -0.01 else "NEUTRAL"
    confidence = max(bullish_prob, bearish_prob, neutral_prob)

    return {
        "direction": direction,
        "direction_prob": round(float(max(bullish_prob, bearish_prob)), 4),
        "class_probs": class_probs,
        "p10": round(float(p10), 2),
        "p50": round(float(p50), 2),
        "p90": round(float(p90), 2),
        "confidence": round(float(confidence), 4),
        "regime": _infer_regime(price_series),
        "model_used": "statistical_live_fallback",
    }


def _fallback_response(
    *,
    req: PredictRequest,
    price_series: pd.Series,
    model_used: str,
) -> PredictResponse:
    fallback = _statistical_live_forecast(price_series, req.horizon)
    if req.regime:
        fallback["regime"] = req.regime
    fallback["model_used"] = model_used
    return PredictResponse(ticker=req.ticker, horizon=req.horizon, **fallback)


async def build_live_prediction_from_frames(
    req: PredictRequest,
    *,
    ohlcv_df: pd.DataFrame,
    macro_df: pd.DataFrame,
    nifty_df: pd.DataFrame | Exception | None,
    fii_df: pd.DataFrame | Exception | None,
    vix_df: pd.DataFrame | Exception | None,
) -> PredictResponse:
    if ohlcv_df.empty:
        raise ValueError(f"no live OHLCV for {req.ticker}")
    if macro_df is None or macro_df.empty:
        raise ValueError("macro snapshot unavailable")

    price_series = ohlcv_df["close"].copy()
    feature_builder = IndiaFeatureSet()
    features = feature_builder.build(
        ohlcv_df=ohlcv_df,
        macro_df=macro_df,
        fii_dii_df=None if isinstance(fii_df, Exception) else fii_df,
        fno_df=None,
        sector_df=None,
    ).dropna(how="all")

    validation = feature_builder.validate(features, price_series)
    if not validation.passed:
        logger.warning(
            "api.predict.feature_validation_failed",
            ticker=req.ticker,
            same_day_leaks=validation.same_day_leaks,
            null_columns=validation.null_columns,
        )
        return _fallback_response(
            req=req,
            price_series=price_series,
            model_used="feature_validation_fallback",
        )

    if len(features) < 120:
        return _fallback_response(
            req=req,
            price_series=price_series,
            model_used="statistical_live_fallback",
        )

    covariates = build_chronos_covariates(features, price_series)
    nifty_returns = (
        np.log(nifty_df["close"] / nifty_df["close"].shift(1)).dropna()
        if not isinstance(nifty_df, Exception) and nifty_df is not None and not nifty_df.empty
        else pd.Series(dtype=float)
    )
    vix_series = (
        vix_df["vix"] if not isinstance(vix_df, Exception) and vix_df is not None and not vix_df.empty
        else None
    )
    vix_current = float(vix_series.iloc[-1]) if vix_series is not None else 15.0

    try:
        service = get_prediction_service(
            ticker=req.ticker,
            horizon=req.horizon,
            model_dir=MODEL_ROOT,
        )
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            service.predict,
            features,
            price_series,
            nifty_returns,
            covariates["covariate_df"],
            vix_current,
            vix_series,
        )
        direction = _simplify_direction(result.direction, result.bullish_prob, result.bearish_prob)
        base_band = abs((result.q90_5d or result.current_price) - (result.q10_5d or result.current_price))
        band_pct = base_band / max(result.current_price, 1.0)
        if req.horizon == 5:
            p10, p50, p90 = result.q10_5d, result.forecast_5d, result.q90_5d
        elif req.horizon == 10:
            p50 = result.forecast_10d
            p10 = p50 * (1 - band_pct) if p50 else None
            p90 = p50 * (1 + band_pct) if p50 else None
        else:
            p50 = result.forecast_30d
            p10 = p50 * (1 - band_pct) if p50 else None
            p90 = p50 * (1 + band_pct) if p50 else None
        return PredictResponse(
            ticker=req.ticker,
            horizon=req.horizon,
            direction=direction,
            direction_prob=max(result.bullish_prob, result.bearish_prob),
            class_probs=result.class_probs,
            p10=p10,
            p50=p50,
            p90=p90,
            confidence=result.confidence,
            regime=req.regime or result.regime_name.upper(),
            model_used="ensemble" if result.is_high_confidence else "ensemble_low_confidence",
        )
    except Exception as exc:
        logger.warning("api.predict.live_model_unavailable", ticker=req.ticker, error=str(exc))
        return _fallback_response(
            req=req,
            price_series=price_series,
            model_used="statistical_live_fallback",
        )


async def build_live_prediction_response(req: PredictRequest) -> PredictResponse:
    yf = YFinanceClient()
    nselib = NSELibClient()

    ohlcv_df, macro_df, nifty_df, fii_df, vix_df = await asyncio.gather(
        yf.get_ohlcv(req.ticker, period="3y"),
        yf.get_macro_snapshot(period="3y"),
        yf.get_ohlcv("^NSEI", period="3y"),
        nselib.get_fii_dii(),
        yf.get_india_vix(period="3y"),
        return_exceptions=True,
    )

    if isinstance(ohlcv_df, Exception):
        raise ohlcv_df
    if ohlcv_df.empty:
        raise ValueError(f"no live OHLCV for {req.ticker}")

    if isinstance(macro_df, Exception) or macro_df is None or macro_df.empty:
        raise ValueError("macro snapshot unavailable")
    return await build_live_prediction_from_frames(
        req,
        ohlcv_df=ohlcv_df,
        macro_df=macro_df,
        nifty_df=nifty_df,
        fii_df=fii_df,
        vix_df=vix_df,
    )


@router.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest) -> PredictResponse:
    """Return a stock-specific forecast from trained models or a live statistical fallback."""
    logger.info("api.predict.request", ticker=req.ticker, horizon=req.horizon)
    try:
        return await build_live_prediction_response(req)
    except Exception as exc:
        logger.error("api.predict.error", ticker=req.ticker, error=str(exc), exc_info=True)
        return PredictResponse(
            ticker=req.ticker,
            horizon=req.horizon,
            direction="NEUTRAL",
            direction_prob=0.0,
            class_probs={label: 0.0 for label in CLASS_LABELS},
            confidence=0.0,
            regime=req.regime or "UNKNOWN",
            model_used="unavailable",
        )
