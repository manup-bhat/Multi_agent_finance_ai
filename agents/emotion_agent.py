"""
Emotion Agent — Fear/Greed + FinBERT Sentiment
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receives pre-computed composite sentiment from Phase 4 sentiment/ module.
"""
from __future__ import annotations
import structlog
from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("emotion_agent")


def _build_emotion_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    sentiment = state.get("sentiment_summary", "No sentiment data.")
    vix = state.get("vix_signal", {})
    vix_regime = vix.get("regime", "N/A") if vix else "N/A"
    return (
        f"TICKER: {ticker}\n"
        f"VIX REGIME: {vix_regime}\n\n"
        f"=== SENTIMENT DATA (pre-computed) ===\n{sentiment}\n"
    )


def run_emotion_agent(state: IndiaEngineState) -> dict:
    """LangGraph node: runs Emotion agent."""
    logger.info("emotion_agent.start", ticker=state.get("ticker"))
    context = _build_emotion_context(state)
    result = call_groq(_PROMPT, context)
    logger.info("emotion_agent.done")
    return {"emotion_analysis": result}
