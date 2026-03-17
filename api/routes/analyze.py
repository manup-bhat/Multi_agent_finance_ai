"""
POST /analyze — live end-to-end analysis.

The route now builds state from real data only. When the LLM workflow is
unavailable, it falls back to a deterministic synthesis rather than demo text.
"""
from __future__ import annotations

import asyncio
import datetime as dt

from fastapi import APIRouter, HTTPException
import structlog

from agents.risk_node import run_risk_node
from agents.state import IndiaEngineState
from api.routes.fii_dii import fii_dii_latest
from api.routes.predict import build_live_prediction_response
from api.routes.sentiment import build_live_sentiment_response
from api.schemas import AnalyzeRequest, AnalyzeResponse, PredictRequest
from config.india_calendar import classify_market_event, get_event_description
from data.adapters.nsefin_client import MarketClosedError, NSEFinClient
from data.adapters.yfinance_client import YFinanceClient
from data.processors.smc_analyzer import detect_smc_zones
from data.processors.technical_analyzer import compute_all_indicators
from fno.fno_reporter import build_fno_report, build_fno_summary_text

logger = structlog.get_logger(__name__)
router = APIRouter()


def _map_direction_to_verdict(direction: str, confidence: float) -> str:
    if direction == "BULLISH":
        return "STRONG_BUY" if confidence >= 0.7 else "BUY"
    if direction == "BEARISH":
        return "STRONG_SELL" if confidence >= 0.7 else "SELL"
    return "HOLD"


def _summarize_prediction(pred) -> str:
    bits = [
        f"Direction={pred.direction}",
        f"Confidence={pred.confidence:.1%}",
        f"Regime={pred.regime}",
        f"Model={pred.model_used}",
    ]
    if pred.p50 is not None:
        bits.append(f"P50={pred.p50:.2f}")
    if pred.p10 is not None and pred.p90 is not None:
        bits.append(f"Band={pred.p10:.2f}–{pred.p90:.2f}")
    return " | ".join(bits)


def _build_deterministic_response(state: IndiaEngineState) -> AnalyzeResponse:
    risk_updates = run_risk_node(state)
    state.update(risk_updates)

    confidence = float(state.get("confidence", 0.0))
    verdict = state.get("verdict") or _map_direction_to_verdict(
        str(state.get("prediction_direction", "NEUTRAL")),
        confidence,
    )
    if state.get("risk_node_output", {}).get("circuit_breaker_active"):
        verdict = "HOLD"

    price_targets = state.get("price_targets", {})
    return AnalyzeResponse(
        ticker=state.get("ticker", ""),
        verdict=verdict,
        confidence=confidence,
        price_target_p10=price_targets.get("p10"),
        price_target_p50=price_targets.get("p50"),
        price_target_p90=price_targets.get("p90"),
        regime=state.get("market_regime", "UNKNOWN"),
        risk_level=state.get("risk_node_output", {}).get("risk_level", "UNKNOWN"),
        quant_summary=state.get("ta_summary", "Technical summary unavailable."),
        macro_summary=state.get("macro_analysis", state.get("macro_summary", "Macro summary unavailable.")),
        fno_summary=state.get("fno_analysis", state.get("fno_summary_text", "F&O summary unavailable.")),
        emotion_summary=state.get("emotion_analysis", state.get("sentiment_summary", "Sentiment summary unavailable.")),
        key_risks=state.get("risk_node_output", {}).get("notes", []),
        circuit_breaker_active=state.get("risk_node_output", {}).get("circuit_breaker_active", False),
        vix_current=state.get("vix_signal", {}).get("current_vix"),
    )


async def _build_live_state(req: AnalyzeRequest) -> IndiaEngineState:
    yf = YFinanceClient()
    nsefin = NSEFinClient()

    ohlcv_df, macro_df, vix_df, fii = await asyncio.gather(
        yf.get_ohlcv(req.ticker, period="1y"),
        yf.get_macro_snapshot(period="1y"),
        yf.get_india_vix(period="6mo"),
        fii_dii_latest(),
    )

    if ohlcv_df.empty:
        raise ValueError(f"no live OHLCV for {req.ticker}")

    indicators = compute_all_indicators(ohlcv_df.copy())
    latest_ta = indicators.iloc[-1]
    smc = detect_smc_zones(ohlcv_df)
    try:
        prediction = await build_live_prediction_response(
            PredictRequest(ticker=req.ticker, horizon=req.horizon)
        )
    except Exception as exc:
        logger.warning("api.analyze.prediction_unavailable", ticker=req.ticker, error=str(exc))
        prediction = None

    if req.include_sentiment:
        try:
            sentiment = await build_live_sentiment_response(req.ticker)
        except Exception as exc:
            logger.warning("api.analyze.sentiment_unavailable", ticker=req.ticker, error=str(exc))
            sentiment = None
    else:
        sentiment = None

    state = IndiaEngineState(
        ticker=req.ticker,
        horizon=req.horizon,
        analysis_date=dt.date.today().isoformat(),
        errors=[],
        warnings=[],
    )

    current_vix = float(vix_df["vix"].iloc[-1]) if not vix_df.empty else None
    state["vix_signal"] = {
        "current_vix": current_vix or 0.0,
        "regime": vix_df["regime"].iloc[-1] if not vix_df.empty else "UNKNOWN",
    }
    state["fii_dii_report"] = {
        "sell_streak_days": fii.fii_streak_days,
        "sell_streak_alert": fii.fii_streak_days >= 7,
        "fii_net_crore": fii.fii_net_crore,
        "dii_net_crore": fii.dii_net_crore,
        "consensus": fii.consensus,
    }
    state["global_cues"] = {
        "usdinr": float(macro_df["usdinr"].ffill().iloc[-1]) if "usdinr" in macro_df.columns else None,
        "brent_crude": float(macro_df["brent_crude"].ffill().iloc[-1]) if "brent_crude" in macro_df.columns else None,
    }
    event_type = classify_market_event(dt.date.today())
    state["event_impact"] = {
        "event_type": event_type,
        "description": get_event_description(event_type),
    }
    state["market_regime"] = (
        prediction.regime if prediction and prediction.regime in {"BULL", "BEAR", "SIDEWAYS"} else "SIDEWAYS"
    )

    state["ta_summary"] = (
        f"Close={latest_ta.get('close', ohlcv_df['close'].iloc[-1]):.2f} | "
        f"RSI14={latest_ta.get('rsi_14', 0.0):.1f} | "
        f"MACD Hist={latest_ta.get('macd_hist', 0.0):.3f} | "
        f"EMA21={latest_ta.get('ema_21', 0.0):.2f} | "
        f"EMA50={latest_ta.get('ema_50', 0.0):.2f} | "
        f"ATR%={latest_ta.get('atr_pct', 0.0):.2f}"
    )
    state["smc_summary"] = (
        f"Bias={smc.get('current_bias', 'NEUTRAL')} | "
        f"BOS={smc.get('summary', {}).get('bos_count', 0)} | "
        f"CHoCH={smc.get('summary', {}).get('choch_count', 0)} | "
        f"OB={smc.get('summary', {}).get('ob_count', 0)} | "
        f"FVG={smc.get('summary', {}).get('fvg_count', 0)}"
    )
    if prediction is not None:
        state["prediction_summary"] = _summarize_prediction(prediction)
        state["prediction_direction"] = prediction.direction
        state["confidence"] = prediction.confidence
        state["price_targets"] = {
            "p10": prediction.p10,
            "p50": prediction.p50,
            "p90": prediction.p90,
        }
    else:
        state["prediction_summary"] = "Prediction unavailable."
        state["prediction_direction"] = "NEUTRAL"
        state["confidence"] = 0.0
        state["price_targets"] = {}
    state["macro_summary"] = (
        f"VIX={state['vix_signal']['current_vix']:.2f} ({state['vix_signal']['regime']}) | "
        f"FII={fii.fii_trend} {fii.fii_net_crore} cr | "
        f"USDINR={state['global_cues'].get('usdinr')} | "
        f"Brent={state['global_cues'].get('brent_crude')}"
    )

    if sentiment is not None:
        state["sentiment_summary"] = (
            f"Composite={sentiment.composite_score:+.2f} ({sentiment.composite_label}) | "
            f"FearGreed={sentiment.fear_greed_index:.1f} ({sentiment.fear_greed_label}) | "
            f"Articles={len(sentiment.articles)}"
        )
        headlines = [a.headline for a in sentiment.articles[:5]]
        state["fundamental_summary"] = " | ".join(headlines) if headlines else "No ticker-specific headlines found."
    else:
        state["sentiment_summary"] = "Sentiment analysis disabled."
        state["fundamental_summary"] = "Sentiment analysis disabled."

    if req.include_fno:
        try:
            symbol = req.ticker.replace(".NS", "").replace(".BO", "")
            chain_df = await nsefin.get_option_chain(symbol)
            spot = float(ohlcv_df["close"].iloc[-1])
            report = build_fno_report(chain_df, spot=spot)
            state["fno_report"] = report
            state["fno_summary_text"] = build_fno_summary_text(report)
            state["recommended_strategy"] = report.get("oi_buildup_description", "")
        except MarketClosedError as exc:
            state["warnings"].append(str(exc))
            state["fno_report"] = {}
            state["fno_summary_text"] = "F&O data unavailable because the option chain is not published outside market hours."
        except Exception as exc:
            state["warnings"].append(str(exc))
            state["fno_report"] = {}
            state["fno_summary_text"] = "F&O data unavailable."
    else:
        state["fno_report"] = {}
        state["fno_summary_text"] = "F&O analysis disabled for this request."

    return state


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest) -> AnalyzeResponse:
    """Run the live analysis pipeline for a ticker."""
    logger.info("api.analyze.request", ticker=req.ticker, horizon=req.horizon)
    try:
        state = await _build_live_state(req)
    except Exception as exc:
        logger.error("api.analyze.build_state_failed", ticker=req.ticker, error=str(exc))
        raise HTTPException(status_code=503, detail=f"Live analysis data unavailable: {exc}") from exc

    try:
        from agents.graph.workflow import build_workflow

        workflow = build_workflow()
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, workflow.invoke, state)
        if isinstance(result_state, dict):
            merged = state.copy()
            merged.update(result_state)
            return _build_deterministic_response(merged)
    except Exception as exc:
        logger.warning("api.analyze.workflow_failed", ticker=req.ticker, error=str(exc))

    return _build_deterministic_response(state)
