"""
Quant Agent — Technical Analysis Synthesis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receives pre-computed TA indicators + SMC signals as formatted text.
Uses Groq Llama 3.3 70B to synthesize into an actionable quant opinion.
"""
from __future__ import annotations
import structlog
from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("quant_agent")


def _build_quant_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    horizon = state.get("horizon", 5)
    ta = state.get("ta_summary", "No TA data available.")
    smc = state.get("smc_summary", "No SMC data available.")
    regime = state.get("market_regime", "UNKNOWN")
    return (
        f"TICKER: {ticker}\nFORECAST HORIZON: {horizon} days\n"
        f"MARKET REGIME (HMM): {regime}\n\n"
        f"=== TECHNICAL INDICATORS (pre-computed) ===\n{ta}\n\n"
        f"=== SMC ANALYSIS (pre-computed) ===\n{smc}\n"
    )


def run_quant_agent(state: IndiaEngineState) -> IndiaEngineState:
    """LangGraph node: runs Quant agent, writes quant_analysis to state."""
    logger.info("quant_agent.start", ticker=state.get("ticker"))
    context = _build_quant_context(state)
    result = call_groq(_PROMPT, context)
    state["quant_analysis"] = result
    logger.info("quant_agent.done")
    return state
