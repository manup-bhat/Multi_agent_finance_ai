"""
Macro Agent — FII/DII + VIX + Crude + INR + Global Cues
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Receives pre-computed macro signals from Phase 7 macro/ module.
Groq synthesizes them into an India macro market opinion.
"""
from __future__ import annotations

import structlog
from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("macro_agent")


def _build_macro_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    vix = state.get("vix_signal", {})
    fii = state.get("fii_dii_report", {})
    cues = state.get("global_cues", {})
    event = state.get("event_impact", {})

    def fmt(d: dict, label: str) -> str:
        if not d:
            return f"{label}: No data\n"
        return f"{label}:\n" + "\n".join(f"  {k}: {v}" for k, v in d.items()) + "\n"

    return (
        f"TICKER: {ticker}\n\n"
        + fmt(vix,   "INDIA VIX (pre-computed)")
        + fmt(fii,   "FII/DII FLOWS (pre-computed)")
        + fmt(cues,  "GLOBAL CUES (pre-computed)")
        + fmt(event, "EVENT CALENDAR (pre-computed)")
    )


def run_macro_agent(state: IndiaEngineState) -> dict:
    """LangGraph node: runs Macro agent, writes macro_analysis to state."""
    logger.info("macro_agent.start", ticker=state.get("ticker"))
    context = _build_macro_context(state)
    result = call_groq(_PROMPT, context, task="macro_agent")
    logger.info("macro_agent.done")
    return {"macro_analysis": result}
