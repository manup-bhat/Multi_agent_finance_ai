"""
Fundamental Agent — News + SEBI + Corporate Actions
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receives pre-processed text from the sentiment pipeline + news scrapers.
"""
from __future__ import annotations
import structlog
from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("fundamental_agent")


def _build_fundamental_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    fundamental = state.get("fundamental_summary", "No fundamental data.")
    return f"TICKER: {ticker}\n\n=== FUNDAMENTAL DATA (pre-processed) ===\n{fundamental}\n"


def run_fundamental_agent(state: IndiaEngineState) -> dict:
    """LangGraph node: runs Fundamental agent, writes fundamental_analysis to state."""
    logger.info("fundamental_agent.start", ticker=state.get("ticker"))
    context = _build_fundamental_context(state)
    result = call_groq(_PROMPT, context)
    logger.info("fundamental_agent.done")
    return {"fundamental_analysis": result}
