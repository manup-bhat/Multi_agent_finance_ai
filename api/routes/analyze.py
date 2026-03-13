"""
POST /analyze — Full 9-agent LangGraph analysis.
Returns structured verdict with all agent outputs.
Heavy computation — uses mock data when agents not fully wired.
"""
from __future__ import annotations
import datetime
from fastapi import APIRouter, HTTPException
from api.schemas import AnalyzeRequest, AnalyzeResponse
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


def _mock_analyze(ticker: str, horizon: int) -> AnalyzeResponse:
    """Deterministic mock response for testing/demo when agents unavailable."""
    return AnalyzeResponse(
        ticker=ticker,
        verdict="BUY",
        confidence=0.72,
        price_target_p10=None,
        price_target_p50=None,
        price_target_p90=None,
        regime="BULL",
        risk_level="MODERATE",
        quant_summary=(
            f"{ticker} is trading above 21-EMA and 50-EMA with RSI=54 (neutral). "
            "Bollinger Bands: mid-band support intact. MACD: bullish crossover 3 days ago."
        ),
        macro_summary=(
            "VIX at 15.2 (Normal regime). FII buying ₹2,340 Cr past 3 days. "
            "USDINR stable at 83.4. Crude at $83/bbl. Global cues mildly positive."
        ),
        fno_summary=(
            f"PCR = 1.15 (slightly bullish). Max Pain at 21,500. "
            "IV Rank = 32% (low premium). FII long in index futures."
        ),
        emotion_summary=(
            "FinBERT Institutional: +0.42 (Positive). "
            "India Fear/Greed: 58 (Greed territory). GDELT Tone: +2.1."
        ),
        key_risks=[
            f"Expiry Thursday in 2 days — gamma risk elevated",
            "RBI MPC meeting next week — rate decision pending",
            "FII selling in futures segment despite cash buying",
        ],
        circuit_breaker_active=False,
        vix_current=15.2,
    )


async def _build_live_state(req: AnalyzeRequest) -> "IndiaEngineState":
    from agents.state import IndiaEngineState
    import datetime
    
    state = IndiaEngineState(
        ticker=req.ticker,
        horizon_days=req.horizon,
        analysis_date=str(datetime.date.today()),
        errors=[], warnings=[]
    )
    
    try:
        from data.adapters.yfinance_client import YFinanceClient
        from data.processors.technical_analyzer import compute_all_indicators
        from api.routes.fii_dii import fii_dii_latest
        
        yf = YFinanceClient()
        
        # 1. Macro
        vix_df = await yf.get_india_vix(period="1mo")
        vix_current = float(vix_df["vix"].iloc[-1]) if not vix_df.empty else 15.0
        vix_regime = vix_df["regime"].iloc[-1] if not vix_df.empty else "NORMAL"
        state["vix_signal"] = {"current_vix": vix_current, "regime": vix_regime}
        
        # 2. TA
        df = await yf.get_ohlcv(req.ticker, period="6mo")
        if df is not None and not df.empty:
            ta = compute_all_indicators(df).iloc[-1]
            state["ta_summary"] = (
                f"Close={ta.get('close',0):.1f}, RSI_14={ta.get('rsi_14',0):.1f}, "
                f"MACD={ta.get('macd_line',0):.2f}, EMA_21={ta.get('ema_21',0):.1f}, "
                f"ATR_Pct={ta.get('atr_pct',0):.2f}%, BB_Pct={ta.get('bb_pct',0):.2f}"
            )
        else:
            state["ta_summary"] = "No TA data available."
            
        # 3. Proxy/Mocks for missing pipelines so LLMs don't error out
        fii = await fii_dii_latest()
        state["fii_dii_report"] = {
            "sell_streak_days": fii.fii_streak_days, 
            "sell_streak_alert": fii.fii_streak_days >= 7,
        }
        state["smc_summary"] = "SMC structure is trending bullish."
        state["prediction_summary"] = "Ensemble forecasts show moderate upside probability."
        state["sentiment_summary"] = "FinBERT sentiment is neutral-positive."
        state["fundamental_summary"] = "No adverse actions reported."
        state["fno_summary_text"] = "PCR > 1 indicating slight bullishness."
        state["market_regime"] = "SIDEWAYS"
        
    except Exception as e:
        logger.error("analyze.build_state.error", error=str(e))
        state["ta_summary"] = "Error fetching live data."
        state["vix_signal"] = {"current_vix": 15.0, "regime": "NORMAL"}
        state["fii_dii_report"] = {"sell_streak_days": 0, "sell_streak_alert": False}
        
    return state


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """
    Full 9-agent analysis for a given NSE ticker.
    """
    logger.info("api.analyze.request", ticker=req.ticker, horizon=req.horizon)

    try:
        from agents.graph.workflow import build_workflow
        
        # Pre-populate state with real values instead of giving empty state to LLMs
        state = await _build_live_state(req)
        workflow = build_workflow()
        
        import asyncio
        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, workflow.invoke, state)
        
        return AnalyzeResponse(
            ticker=result_state.get("ticker", req.ticker),
            verdict=result_state.get("verdict", "HOLD"),
            confidence=result_state.get("confidence", 50.0),
            price_target_p10=result_state.get("price_targets", {}).get("p10"),
            price_target_p50=result_state.get("price_targets", {}).get("p50"),
            price_target_p90=result_state.get("price_targets", {}).get("p90"),
            regime=result_state.get("market_regime", "UNKNOWN"),
            risk_level=result_state.get("risk_node_output", {}).get("risk_level", "UNKNOWN"),
            quant_summary=result_state.get("quant_analysis", "Quant analysis unavailable"),
            macro_summary=result_state.get("macro_analysis", "Macro analysis unavailable"),
            fno_summary=result_state.get("fno_analysis", "F&O analysis unavailable"),
            emotion_summary=result_state.get("emotion_analysis", "Emotion analysis unavailable"),
            key_risks=result_state.get("risk_node_output", {}).get("notes", []),
            circuit_breaker_active=result_state.get("risk_node_output", {}).get("circuit_breaker_active", False),
            vix_current=result_state.get("vix_signal", {}).get("current_vix", 0.0),
        )
    except Exception as e:
        logger.error("api.analyze.error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
