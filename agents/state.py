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

from enum import Enum
from typing import Any, Optional, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Verdict(str, Enum):
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


class Regime(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    SIDEWAYS = "SIDEWAYS"


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
    market_calendar: dict[str, Any]  # Trading-day / event-window context
    market_regime: Regime | str      # "BULL" | "BEAR" | "SIDEWAYS" (HMM)

    # ── Pre-computed F&O inputs (from Phase 6 fno/) ───────────────
    fno_report: dict[str, Any]       # FnO reporter dict
    fno_summary_text: str            # Plain-text F&O summary for LLM

    # ── Pre-computed TA / feature inputs ──────────────────────────
    ta_summary: str                  # pandas-ta indicators → formatted text
    smc_summary: str                 # BOS/CHoCH/OB/FVG summary text
    prediction_summary: str          # Ensemble forecast text (no numbers, interpretive)
    sentiment_summary: str           # Composite FinBERT + Fear/Greed text
    composite_sent: dict[str, Any]   # Structured sentiment metrics for risk / DA
    fundamental_summary: str         # News + SEBI + corporate actions text
    fundamental_documents: list[dict[str, Any]]  # Optional docs for RAG indexing

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
    workflow_validation: dict[str, Any]  # Pre-orchestrator readiness checks

    # ── Orchestrator final output ──────────────────────────────────
    orchestrator_report: str         # Full Gemini-synthesized report text
    verdict: Verdict | str           # "STRONG_BUY"|"BUY"|"HOLD"|"SELL"|"STRONG_SELL"
    confidence: float                # 0.0 – 1.0
    price_targets: dict[str, float]  # {"p10": x, "p50": y, "p90": z}
    recommended_strategy: str        # F&O strategy name

    # ── Meta ──────────────────────────────────────────────────────
    errors: list[str]                # Non-fatal errors accumulated
    warnings: list[str]             # Non-fatal warnings


# Valid verdict values (used for validation in tests)
VALID_VERDICTS = tuple(verdict.value for verdict in Verdict)

# Valid regime labels
VALID_REGIMES = tuple(regime.value for regime in Regime)

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


class IndiaEngineStateModel(BaseModel):
    """
    Runtime validator for shared state payloads.

    LangGraph still passes plain dict state between nodes, so this model is used
    as a validation layer rather than as the state container itself.
    """

    model_config = ConfigDict(extra="allow", use_enum_values=True)

    ticker: str = ""
    horizon: int = 5
    analysis_date: str
    market_regime: Regime | None = None
    verdict: Verdict | None = None
    confidence: float | None = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    price_targets: dict[str, float | None] = Field(default_factory=dict)
    fno_report: dict[str, Any] = Field(default_factory=dict)

    @field_validator("analysis_date")
    @classmethod
    def _validate_analysis_date(cls, value: str) -> str:
        from datetime import date

        date.fromisoformat(value)
        return value

    @field_validator("horizon")
    @classmethod
    def _validate_horizon(cls, value: int) -> int:
        if value < 1 or value > 30:
            raise ValueError("horizon must be between 1 and 30")
        return value

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float | None) -> float | None:
        if value is None:
            return value
        if value < 0.0 or value > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return value


def validate_state_payload(state: dict[str, Any]) -> IndiaEngineState:
    """Validate and normalize a state dict without changing the graph contract."""
    model = IndiaEngineStateModel.model_validate(state)
    return model.model_dump(exclude_none=True)


def make_empty_state(ticker: str = "", horizon: int = 5) -> IndiaEngineState:
    """Create a minimal valid state for testing."""
    from config.india_calendar import get_last_trading_day

    return IndiaEngineState(
        ticker=ticker,
        horizon=horizon,
        analysis_date=str(get_last_trading_day()),
        errors=[],
        warnings=[],
    )
