"""
F&O Agent — Options Strategy Synthesis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receives pre-computed F&O report from Phase 6 fno/ module.
Groq synthesizes Max Pain, PCR, OI, IV Rank into a strategy recommendation.
"""
from __future__ import annotations
import structlog
from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("fno_agent")


def _build_fno_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    fno_text = state.get("fno_summary_text", "")
    fno_dict = state.get("fno_report", {})
    event = state.get("event_impact", {})
    expiry_risk = event.get("event_type", "NORMAL") if event else "NORMAL"

    if not fno_text and fno_dict:
        # Build from dict if no pre-formatted text
        fno_text = "\n".join(f"  {k}: {v}" for k, v in fno_dict.items())

    return (
        f"TICKER: {ticker}\n"
        f"EXPIRY RISK EVENT: {expiry_risk}\n\n"
        f"=== F&O ANALYSIS (pre-computed) ===\n{fno_text or 'No F&O data.'}\n"
    )


def run_fno_agent(state: IndiaEngineState) -> IndiaEngineState:
    """LangGraph node: runs F&O agent."""
    logger.info("fno_agent.start", ticker=state.get("ticker"))
    context = _build_fno_context(state)
    result = call_groq(_PROMPT, context)
    state["fno_analysis"] = result
    logger.info("fno_agent.done")
    return state
