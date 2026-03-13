"""
India Engine Shared Agent State
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LangGraph TypedDict defining ALL fields shared between agents.

Design principles:
1. All numerical analysis is PRE-COMPUTED before agents run.
   Agents receive structured dicts and formatted text — NEVER raw data.
2. LLMs never calculate math. All metrics are Python-computed.
3. Each agent reads from state and writes exactly one output key.
4. The Risk Node is pure Python — it reads all agent outputs and
   applies deterministic gating rules (VIX, FII streak, Kelly).
5. The Orchestrator reads everything and produces the final report.
"""
from __future__ import annotations

from typing import Any, Optional, TypedDict


class IndiaEngineState(TypedDict, total=False):
    """
    Shared state for the 9-agent LangGraph workflow.

    Lifecycle:
      Stage 0 (pre-flight) → populates: ticker, horizon, analysis_date,
                              vix_signal, fii_dii_report, global_cues,
                              event_impact, fno_report, market_regime
      Stage 1–2 (data) →     populates: ta_summary, fundamental_summary,
                              prediction_summary, sentiment_summary
      Stage 3 (agents) →     each agent populates its own output key
      Stage 4 (risk+orch) →  risk_node_output, orchestrator_report

    All 'summary' fields are plain-text formatted for LLM consumption.
    All 'report' fields are structured dicts for deterministic use.
    """

    # ── Request ───────────────────────────────────────────────────
    ticker: str                      # e.g. "HDFCBANK.NS"
    horizon: int                     # forecast horizon in days (5/10/30)
    analysis_date: str               # ISO date string "2026-03-13"

    # ── Pre-computed macro inputs (from Phase 7 macro/) ───────────
    vix_signal: dict[str, Any]       # VIXSignal as dict
    fii_dii_report: dict[str, Any]   # FIIDIIReport as dict
    global_cues: dict[str, Any]      # GlobalCuesReport as dict
    event_impact: dict[str, Any]     # EventImpactReport as dict
    market_regime: str               # "BULL" | "BEAR" | "SIDEWAYS" (HMM)

    # ── Pre-computed F&O inputs (from Phase 6 fno/) ───────────────
    fno_report: dict[str, Any]       # FnO reporter dict
    fno_summary_text: str            # Plain-text F&O summary for LLM

    # ── Pre-computed TA / feature inputs ──────────────────────────
    ta_summary: str                  # pandas-ta indicators → formatted text
    smc_summary: str                 # BOS/CHoCH/OB/FVG summary text
    prediction_summary: str          # Ensemble forecast text (no numbers, interpretive)
    sentiment_summary: str           # Composite FinBERT + Fear/Greed text
    fundamental_summary: str         # News + SEBI + corporate actions text

    # ── Agent outputs (each agent writes exactly one key) ─────────
    quant_analysis: str              # Quant agent (TA + SMC synthesis)
    macro_analysis: str              # Macro agent (FII/DII/VIX/crude/INR)
    fundamental_analysis: str        # Fundamental agent (news + SEBI)
    prediction_analysis: str         # Prediction agent (TSFM + ensemble)
    emotion_analysis: str            # Emotion agent (sentiment)
    fno_analysis: str                # F&O agent (options strategy)
    devils_advocate_analysis: str    # Devil's advocate (contrarian risks)

    # ── Risk node output (pure Python, no LLM) ────────────────────
    risk_node_output: dict[str, Any] # See RiskNodeOutput structure

    # ── Orchestrator final output ──────────────────────────────────
    orchestrator_report: str         # Full Gemini-synthesized report text
    verdict: str                     # "STRONG_BUY"|"BUY"|"HOLD"|"SELL"|"STRONG_SELL"
    confidence: float                # 0.0 – 1.0
    price_targets: dict[str, float]  # {"p10": x, "p50": y, "p90": z}
    recommended_strategy: str        # F&O strategy name

    # ── Meta ──────────────────────────────────────────────────────
    errors: list[str]                # Non-fatal errors accumulated
    warnings: list[str]             # Non-fatal warnings


# Valid verdict values (used for validation in tests)
VALID_VERDICTS = frozenset(
    {"STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"}
)

# Valid regime labels
VALID_REGIMES = frozenset({"BULL", "BEAR", "SIDEWAYS"})

# Required keys in risk_node_output
RISK_NODE_REQUIRED_KEYS = frozenset({
    "circuit_breaker_active",
    "position_size_multiplier",
    "fii_streak_alert",
    "gamma_risk_flag",
    "low_confidence_flag",
    "kelly_fraction",
    "sebi_compliant",
    "override_verdict",
    "risk_level",
    "notes",
})

# Required sections in orchestrator_report (used for validation)
REPORT_REQUIRED_SECTIONS = [
    "VERDICT",
    "CONFIDENCE",
    "TECHNICAL",
    "MACRO",
    "F&O",
    "SENTIMENT",
    "RISKS",
    "PRICE TARGETS",
    "STRATEGY",
]


def make_empty_state(ticker: str = "", horizon: int = 5) -> IndiaEngineState:
    """Create a minimal valid state for testing."""
    from datetime import date
    return IndiaEngineState(
        ticker=ticker,
        horizon=horizon,
        analysis_date=str(date.today()),
        errors=[],
        warnings=[],
    )
