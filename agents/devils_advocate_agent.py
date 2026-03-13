"""
Devil's Advocate Agent — Contrarian Risk Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Weight is amplified when: prediction confidence < 55% OR VIX > 20.
Challenges the consensus established by the other 6 agents.
"""
from __future__ import annotations
import structlog
from agents.state import IndiaEngineState
from agents.base_agent import load_prompt, call_groq
from config.constants import PREDICTION_CONFIDENCE_THRESHOLD

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("devils_advocate_agent")

# Devil's advocate weight amplification threshold
DA_VIX_AMPLIFICATION_THRESHOLD = 20.0


def _should_amplify(state: IndiaEngineState) -> bool:
    """True if DA weight should be amplified (low confidence or high VIX)."""
    vix_signal = state.get("vix_signal", {})
    vix = float(vix_signal.get("current_vix", 0.0)) if vix_signal else 0.0
    confidence = state.get("confidence", 0.0) or 0.0
    return vix > DA_VIX_AMPLIFICATION_THRESHOLD or confidence < PREDICTION_CONFIDENCE_THRESHOLD


def _build_da_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    amplified = _should_amplify(state)
    vix_signal = state.get("vix_signal", {})
    vix = vix_signal.get("current_vix", "N/A") if vix_signal else "N/A"

    # Gather all agent verdicts for consensus picture
    analyses = {
        "QUANT": state.get("quant_analysis", "N/A"),
        "MACRO": state.get("macro_analysis", "N/A"),
        "FUNDAMENTAL": state.get("fundamental_analysis", "N/A"),
        "PREDICTION": state.get("prediction_analysis", "N/A"),
        "EMOTION": state.get("emotion_analysis", "N/A"),
        "F&O": state.get("fno_analysis", "N/A"),
    }

    consensus = "\n\n".join(
        f"--- {k} AGENT ---\n{v[:500]}" for k, v in analyses.items() if v != "N/A"
    )

    amplify_note = (
        "\n⚠️ AMPLIFIED WEIGHT: Prediction confidence < 55% or VIX > 20. "
        "Your contrarian analysis carries extra weight this session."
        if amplified else ""
    )

    return (
        f"TICKER: {ticker} | INDIA VIX: {vix}\n"
        f"{amplify_note}\n\n"
        f"=== CONSENSUS FROM OTHER AGENTS ===\n{consensus}\n\n"
        f"Challenge this consensus with rigorous contrarian arguments.\n"
    )


def run_devils_advocate_agent(state: IndiaEngineState) -> dict:
    """LangGraph node: runs Devil's Advocate."""
    logger.info("devils_advocate_agent.start", ticker=state.get("ticker"))
    context = _build_da_context(state)
    result = call_groq(_PROMPT, context)
    logger.info("devils_advocate_agent.done")
    return {"devils_advocate_analysis": result}
