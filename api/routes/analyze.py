"""
POST /analyze — live end-to-end analysis.

The route now builds state from real data only. When the LLM workflow is
unavailable, it falls back to a deterministic synthesis rather than demo text.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
import structlog

from agents.risk_node import run_risk_node
from agents.state import IndiaEngineState, validate_state_payload
from api.routes.predict import build_live_prediction_from_frames
from api.routes.sentiment import build_fallback_sentiment_response, build_live_sentiment_response
from api.schemas import AnalyzeRequest, AnalyzeResponse, PredictRequest
from config.india_calendar import (
    classify_market_event,
    get_event_description,
    get_market_calendar_context,
)
from data.adapters.nsefin_client import MarketClosedError, NSEFinClient
from data.adapters.nselib_client import NSELibClient
from data.adapters.yfinance_client import YFinanceClient
from data.processors.smc_analyzer import detect_smc_zones
from data.processors.technical_analyzer import compute_all_indicators
from fno.fno_reporter import build_fno_report, build_fno_summary_text
from macro.fii_dii_tracker import build_flow_report
from macro.india_vix_monitor import detect_vix_reversion_signal

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


def _fii_trend_from_net(value: float | None) -> str:
    if value is None:
        return "UNKNOWN"
    if value > 0:
        return "BUYING"
    if value < 0:
        return "SELLING"
    return "NEUTRAL"


def _compute_fii_net_5d(fii_df) -> float | None:
    if isinstance(fii_df, Exception) or fii_df is None or fii_df.empty or "fii_net_value" not in fii_df.columns:
        return None
    return round(float(fii_df["fii_net_value"].tail(5).sum()), 2)


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
    composite_sent = state.get("composite_sent", {})
    fii_report = state.get("fii_dii_report", {})
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
        fii_net_5d=fii_report.get("fii_net_5d"),
        fear_greed_index=composite_sent.get("fear_greed_index"),
        social_bullish_pct=composite_sent.get("social_bullish_pct"),
        social_post_volume=composite_sent.get("social_post_volume"),
        euphoria_flag=composite_sent.get("euphoria_flag"),
        sentiment_window=composite_sent.get("sentiment_window_days"),
        recommended_strategy=state.get("recommended_strategy"),
        errors=list(state.get("errors", [])),
        warnings=list(state.get("warnings", [])),
    )


async def _build_live_state(req: AnalyzeRequest) -> IndiaEngineState:
    yf = YFinanceClient()
    nsefin = NSEFinClient()
    nselib = NSELibClient()

    ohlcv_df, macro_df, vix_df, nifty_df, fii_df = await asyncio.gather(
        yf.get_ohlcv(req.ticker, period="1y"),
        yf.get_macro_snapshot(period="1y"),
        yf.get_india_vix(period="6mo"),
        yf.get_ohlcv("^NSEI", period="1y"),
        nselib.get_fii_dii(),
        return_exceptions=True,
    )

    if isinstance(ohlcv_df, Exception):
        raise ohlcv_df
    if isinstance(macro_df, Exception):
        raise macro_df
    if isinstance(vix_df, Exception):
        raise vix_df
    if ohlcv_df.empty:
        raise ValueError(f"no live OHLCV for {req.ticker}")
    if macro_df.empty:
        raise ValueError("macro snapshot unavailable")

    prediction_task = asyncio.create_task(
        build_live_prediction_from_frames(
            PredictRequest(ticker=req.ticker, horizon=req.horizon),
            ohlcv_df=ohlcv_df,
            macro_df=macro_df,
            nifty_df=nifty_df,
            fii_df=fii_df,
            vix_df=vix_df,
        )
    )
    sentiment_task = (
        asyncio.create_task(
            build_live_sentiment_response(
                req.ticker,
                current_vix=float(vix_df["vix"].iloc[-1]) if not vix_df.empty else None,
            )
        )
        if req.include_sentiment
        else None
    )
    fno_task = (
        asyncio.create_task(
            nsefin.get_option_chain(req.ticker.replace(".NS", "").replace(".BO", ""))
        )
        if req.include_fno
        else None
    )

    indicators = compute_all_indicators(ohlcv_df.copy())
    latest_ta = indicators.iloc[-1]
    smc = detect_smc_zones(ohlcv_df)
    prediction = None
    prediction_error = ""
    try:
        prediction = await prediction_task
    except Exception as exc:
        logger.warning("api.analyze.prediction_unavailable", ticker=req.ticker, error=str(exc))
        prediction_error = str(exc)

    sentiment_error = ""
    if sentiment_task is not None:
        try:
            sentiment = await sentiment_task
        except Exception as exc:
            logger.warning("api.analyze.sentiment_unavailable", ticker=req.ticker, error=str(exc))
            sentiment = build_fallback_sentiment_response(req.ticker, str(exc))
            sentiment_error = str(exc)
    else:
        sentiment = None

    flow_report = None
    if not isinstance(fii_df, Exception) and not fii_df.empty:
        try:
            flow_report = build_flow_report(fii_df)
        except Exception as exc:
            logger.warning("api.analyze.fii_report_unavailable", ticker=req.ticker, error=str(exc))
            fii_df = exc
    calendar_context = get_market_calendar_context()
    analysis_day = calendar_context["last_trading_day"]
    vix_signal = detect_vix_reversion_signal(vix_df["vix"] if not vix_df.empty else [15.0])
    fii_net_5d = _compute_fii_net_5d(fii_df)

    state = IndiaEngineState(
        ticker=req.ticker,
        horizon=req.horizon,
        analysis_date=str(analysis_day),
        errors=[],
        warnings=[],
    )
    if prediction_error:
        state["errors"].append(f"PREDICTION_UNAVAILABLE: {prediction_error}")
    if sentiment_error:
        state["errors"].append(f"SENTIMENT_UNAVAILABLE: {sentiment_error}")
    if isinstance(fii_df, Exception):
        state["errors"].append(f"FII_DII_UNAVAILABLE: {fii_df}")
    if isinstance(nifty_df, Exception):
        state["warnings"].append(f"NIFTY_REFERENCE_UNAVAILABLE: {nifty_df}")
    if vix_signal.is_circuit_breaker:
        state["warnings"].append("VIX_CIRCUIT_BREAKER_ACTIVE")

    state["vix_signal"] = {
        "current_vix": vix_signal.current_vix,
        "regime": vix_signal.regime,
        "z_score_20d": vix_signal.z_score_20d,
        "circuit_breaker": vix_signal.is_circuit_breaker,
        "crisis_mode": vix_signal.is_crisis,
        "signal": vix_signal.signal,
    }
    state["fii_dii_report"] = {
        "sell_streak_days": flow_report.sell_streak_days if flow_report else 0,
        "sell_streak_alert": flow_report.sell_streak_alert if flow_report else False,
        "fii_net_crore": flow_report.latest_fii_net if flow_report else None,
        "dii_net_crore": flow_report.latest_dii_net if flow_report else None,
        "fii_net_5d": fii_net_5d,
        "consensus": flow_report.consensus if flow_report else "UNKNOWN",
        "fii_trend": _fii_trend_from_net(flow_report.latest_fii_net if flow_report else None),
    }
    state["global_cues"] = {
        "usdinr": float(macro_df["usdinr"].ffill().iloc[-1]) if "usdinr" in macro_df.columns else None,
        "brent_crude": float(macro_df["brent_crude"].ffill().iloc[-1]) if "brent_crude" in macro_df.columns else None,
    }
    event_type = classify_market_event(analysis_day)
    state["market_calendar"] = {
        "is_open": bool(calendar_context["is_open"]),
        "last_trading_day": str(calendar_context["last_trading_day"]),
        "is_expiry_thursday": bool(calendar_context["is_expiry_thursday"]),
        "days_to_expiry": int(calendar_context["days_to_expiry"]),
        "is_rbi_day": bool(calendar_context["is_rbi_day"]),
        "is_budget_day": bool(calendar_context["is_budget_day"]),
        "is_result_week": bool(calendar_context["is_result_week"]),
        "event_flag": str(calendar_context["event_flag"]),
    }
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
        f"FII={state['fii_dii_report'].get('fii_trend', 'UNKNOWN')} {state['fii_dii_report'].get('fii_net_crore')} cr | "
        f"USDINR={state['global_cues'].get('usdinr')} | "
        f"Brent={state['global_cues'].get('brent_crude')}"
    )

    if sentiment is not None:
        state["warnings"].extend(list(getattr(sentiment, "warnings", [])))
        state["composite_sent"] = {
            "institutional_score": sentiment.institutional_score,
            "india_specific_score": sentiment.india_specific_score,
            "social_bullish_pct": sentiment.social_bullish_pct,
            "social_post_volume": sentiment.social_post_volume,
            "alpha_vantage_score": sentiment.alpha_vantage_score,
            "gdelt_macro_tone": sentiment.gdelt_macro_tone,
            "earnings_tone": sentiment.earnings_tone,
            "composite_score": sentiment.composite_score,
            "fear_greed": sentiment.fear_greed_index,
            "fear_greed_index": sentiment.fear_greed_index,
            "sentiment_window_days": sentiment.sentiment_window_days,
            "high_volume_flag": sentiment.high_volume_flag,
            "euphoria_flag": sentiment.euphoria_flag,
        }
        state["sentiment_summary"] = (
            f"FinBERT institutional sentiment: {sentiment.composite_label.replace('_', ' ').title()} ({sentiment.institutional_score:+.2f}). "
            f"India-specific score: {sentiment.india_specific_score:+.2f}. "
            f"StockTwits community: {sentiment.social_bullish_pct:.0f}% bullish on {req.ticker.replace('.NS', '')}. "
            f"Social volume: {sentiment.social_post_volume} posts in the last {sentiment.sentiment_window_days} day(s). "
            f"Fear/Greed Index: {sentiment.fear_greed_index:.1f} ({sentiment.fear_greed_label}). "
            f"Alpha Vantage signal: {sentiment.alpha_vantage_score:+.2f}. "
            f"{'Euphoria risk flag active.' if sentiment.euphoria_flag else 'No euphoria flag.'}"
        )
        headlines = [a.headline for a in sentiment.articles[:5]]
        state["fundamental_summary"] = " | ".join(headlines) if headlines else "No ticker-specific headlines found."
        state["fundamental_documents"] = [
            {
                "id": f"{req.ticker}:{idx}",
                "headline": article.headline,
                "summary": article.headline,
                "source": article.source,
                "date": article.date,
            }
            for idx, article in enumerate(sentiment.articles[:10])
        ]
    else:
        state["sentiment_summary"] = "Sentiment analysis disabled."
        state["composite_sent"] = {
            "institutional_score": 0.0,
            "india_specific_score": 0.0,
            "social_bullish_pct": 50.0,
            "social_post_volume": 0,
            "alpha_vantage_score": 0.0,
            "gdelt_macro_tone": 0.0,
            "earnings_tone": 0.0,
            "composite_score": 0.0,
            "fear_greed": 50.0,
            "fear_greed_index": 50.0,
            "sentiment_window_days": 3,
            "high_volume_flag": False,
            "euphoria_flag": False,
        }
        state["fundamental_summary"] = "Sentiment analysis disabled."
        state["fundamental_documents"] = []

    if fno_task is not None:
        try:
            chain_df = await fno_task
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
            state["errors"].append(f"FNO_UNAVAILABLE: {exc}")
            state["fno_report"] = {}
            state["fno_summary_text"] = "F&O data unavailable."
    else:
        state["fno_report"] = {}
        state["fno_summary_text"] = "F&O analysis disabled for this request."

    return validate_state_payload(state)


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
        from agents.graph.workflow import get_workflow

        workflow = get_workflow()
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, workflow.invoke, state)
        if isinstance(result_state, dict):
            merged = state.copy()
            merged.update(result_state)
            return _build_deterministic_response(merged)
    except Exception as exc:
        logger.warning("api.analyze.workflow_failed", ticker=req.ticker, error=str(exc))

    return _build_deterministic_response(state)
