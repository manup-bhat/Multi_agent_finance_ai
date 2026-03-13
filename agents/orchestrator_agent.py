"""
Orchestrator Agent — Gemini 2.5 Pro Final Synthesis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Synthesizes all 7 sub-agent analyses + Risk Node output into a
single structured India market research report.

Hierarchy (higher priority → lower):
  Risk Node > Macro > Prediction > Quant > F&O > Fundamental > Emotion > DA

Rule: If Risk Node says circuit_breaker_active=True, verdict MUST be HOLD.
"""
from __future__ import annotations
import re
import structlog
from agents.state import IndiaEngineState, VALID_VERDICTS
from agents.base_agent import load_prompt, call_gemini

logger = structlog.get_logger(__name__)
_PROMPT = load_prompt("orchestrator_agent")


def _build_orchestrator_context(state: IndiaEngineState) -> str:
    ticker = state.get("ticker", "N/A")
    horizon = state.get("horizon", 5)
    analysis_date = state.get("analysis_date", "N/A")
    regime = state.get("market_regime", "UNKNOWN")
    risk = state.get("risk_node_output", {})
    price_targets = state.get("price_targets", {})

    risk_summary = (
        f"  ⚠️ CIRCUIT BREAKER ACTIVE — OVERRIDE TO HOLD\n"
        if risk.get("circuit_breaker_active") else ""
    ) + "\n".join(f"  - {n}" for n in risk.get("notes", []))

    targets_text = "\n".join(
        f"  {k}: ₹{v:,.2f}" for k, v in price_targets.items()
    ) if price_targets else "  Not computed."

    def section(label: str, content: str) -> str:
        trimmed = (content or "Not available.")[:800]
        return f"\n{'='*60}\n{label}\n{'='*60}\n{trimmed}\n"

    all_analyses = (
        section("QUANT AGENT", state.get("quant_analysis", ""))
        + section("MACRO AGENT", state.get("macro_analysis", ""))
        + section("FUNDAMENTAL AGENT", state.get("fundamental_analysis", ""))
        + section("PREDICTION AGENT", state.get("prediction_analysis", ""))
        + section("EMOTION AGENT", state.get("emotion_analysis", ""))
        + section("F&O AGENT", state.get("fno_analysis", ""))
        + section("DEVIL'S ADVOCATE", state.get("devils_advocate_analysis", ""))
    )

    return (
        f"TICKER: {ticker} | DATE: {analysis_date} | HORIZON: {horizon} days | REGIME: {regime}\n\n"
        f"=== RISK NODE OUTPUT (DETERMINISTIC — HIGHEST PRIORITY) ===\n"
        f"  Circuit Breaker: {risk.get('circuit_breaker_active', False)}\n"
        f"  Position Size Multiplier: {risk.get('position_size_multiplier', 1.0):.1%}\n"
        f"  Kelly Fraction: {risk.get('kelly_fraction', 0.05):.1%}\n"
        f"  Risk Level: {risk.get('risk_level', 'UNKNOWN')}\n"
        f"  Override Verdict: {risk.get('override_verdict', 'N/A')}\n"
        f"{risk_summary}\n\n"
        f"=== PRICE TARGETS (from Prediction Engine) ===\n{targets_text}\n"
        f"{all_analyses}"
    )


def _parse_verdict(report: str) -> str:
    """Extract verdict from report text. Fallback to HOLD on parse failure."""
    for verdict in VALID_VERDICTS:
        pattern = rf"VERDICT:\s*{re.escape(verdict)}"
        if re.search(pattern, report, re.IGNORECASE):
            return verdict
    # Try simpler match
    for verdict in ["STRONG_BUY", "STRONG_SELL", "BUY", "SELL", "HOLD"]:
        if verdict in report.upper():
            return verdict
    return "HOLD"


def run_orchestrator_agent(state: IndiaEngineState) -> IndiaEngineState:
    """LangGraph node: runs Orchestrator (Gemini 2.5 Pro), writes final report."""
    ticker = state.get("ticker", "N/A")
    logger.info("orchestrator_agent.start", ticker=ticker)

    # Safety: if circuit breaker active, enforce HOLD regardless
    risk = state.get("risk_node_output", {})
    if risk.get("circuit_breaker_active", False):
        state["verdict"] = "HOLD"
        logger.info("orchestrator_agent.circuit_breaker_enforced")

    context = _build_orchestrator_context(state)
    report = call_gemini(_PROMPT, context, max_tokens=4096)
    state["orchestrator_report"] = report

    # Parse verdict from report (only if not already forced to HOLD)
    if not risk.get("circuit_breaker_active", False):
        parsed_verdict = _parse_verdict(report)
        if parsed_verdict in VALID_VERDICTS:
            state["verdict"] = parsed_verdict

    logger.info("orchestrator_agent.done", verdict=state.get("verdict", "HOLD"))
    return state
