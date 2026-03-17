"""
Prediction Agent — TSFM Forecast Interpretation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receives pre-computed ML ensemble direction + Chronos-2 price targets.
Groq interprets what the numbers mean (never recomputes).
"""
from __future__ import annotations
import structlog
from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("prediction_agent")


def _build_prediction_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    horizon = state.get("horizon", 5)
    prediction = state.get("prediction_summary", "No prediction data.")
    regime = state.get("market_regime", "UNKNOWN")
    price_targets = state.get("price_targets", {})
    targets_text = "\n".join(
        f"  {k}: {v}" for k, v in price_targets.items()
    ) if price_targets else "  Not yet computed."

    return (
        f"TICKER: {ticker} | HORIZON: {horizon} days | REGIME: {regime}\n\n"
        f"=== ENSEMBLE FORECAST (pre-computed) ===\n{prediction}\n\n"
        f"=== PRICE TARGETS (Chronos-2, pre-computed) ===\n{targets_text}\n"
    )


def run_prediction_agent(state: IndiaEngineState) -> dict:
    """LangGraph node: runs Prediction agent."""
    logger.info("prediction_agent.start", ticker=state.get("ticker"))
    context = _build_prediction_context(state)
    result = call_groq(_PROMPT, context, task="prediction_agent")
    logger.info("prediction_agent.done")
    return {"prediction_analysis": result}
