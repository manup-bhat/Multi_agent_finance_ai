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
    numeric_snapshot = ""

    if not fno_text and fno_dict:
        # Build from dict if no pre-formatted text
        fno_text = "\n".join(f"  {k}: {v}" for k, v in fno_dict.items())
    if fno_dict:
        numeric_snapshot = (
            "\n=== F&O NUMERIC SNAPSHOT (DETERMINISTIC) ===\n"
            f"PCR_OI={fno_dict.get('pcr_oi')}\n"
            f"MAX_PAIN={fno_dict.get('max_pain_strike')}\n"
            f"SUPPORT={fno_dict.get('support_strike')}\n"
            f"RESISTANCE={fno_dict.get('resistance_strike')}\n"
            f"IV_RANK={fno_dict.get('iv_rank')}\n"
            f"IV_PERCENTILE={fno_dict.get('iv_percentile')}\n"
            f"PIN_RISK={fno_dict.get('pin_risk')}\n"
            f"OI_BUILDUP={fno_dict.get('oi_buildup')}\n"
        )

    return (
        f"TICKER: {ticker}\n"
        f"EXPIRY RISK EVENT: {expiry_risk}\n\n"
        f"=== F&O ANALYSIS (pre-computed) ===\n{fno_text or 'No F&O data.'}\n"
        f"{numeric_snapshot}"
    )


def run_fno_agent(state: IndiaEngineState) -> dict:
    """LangGraph node: runs F&O agent."""
    logger.info("fno_agent.start", ticker=state.get("ticker"))
    context = _build_fno_context(state)
    result = call_groq(_PROMPT, context, task="fno_agent")
    logger.info("fno_agent.done")
    return {"fno_analysis": result}
