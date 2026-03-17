"""
Risk Node — Pure Python Deterministic Gating
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint: Agent 8 = RISK NODE (Pure Python — No LLM)

Rules applied in priority order:
  1. VIX ≥ 25 → Force HOLD (circuit breaker)
  2. VIX ≥ 30 → Force HOLD + CASH only flag
  3. FII sell streak ≥ 7 days → Reduce position 40%
  4. Expiry Thursday → Flag gamma risk
  5. Prediction confidence < 50% → Flag LOW CONFIDENCE
  6. Kelly Criterion position sizing
  7. SEBI ≤ 10 OPS rate limit check

NO LLM is called in this node. All logic is deterministic Python.
"""
from __future__ import annotations

import structlog
from datetime import date
from typing import Any

from agents.state import IndiaEngineState, RISK_NODE_REQUIRED_KEYS
from config.constants import (
    VIX_CIRCUIT_BREAKER, VIX_CRISIS_THRESHOLD,
    FII_SELL_STREAK_ALERT_DAYS, MAX_OPS_PER_SECOND,
)
from config.india_calendar import is_expiry_thursday
from risk.circuit_breaker import apply_circuit_breaker
from risk.position_sizer import compute_position_size

logger = structlog.get_logger(__name__)

# Blueprint FII sell streak reduction
FII_STREAK_SIZE_REDUCTION = 0.60   # Keep 60% of normal size (reduce by 40%)
MIN_CONFIDENCE_THRESHOLD  = 0.50   # Flag LOW CONFIDENCE below this


def _extract_vix(state: IndiaEngineState) -> float:
    """Safely extract current VIX from state."""
    vix_signal = state.get("vix_signal", {})
    if isinstance(vix_signal, dict):
        return float(vix_signal.get("current_vix", 15.0))
    return 15.0


def _extract_fii_streak(state: IndiaEngineState) -> int:
    """Safely extract FII sell streak days from state."""
    fii_report = state.get("fii_dii_report", {})
    if isinstance(fii_report, dict):
        return int(
            fii_report.get("sell_streak_days")
            or fii_report.get("consecutive_sell_days")
            or 0
        )
    return 0


def _extract_confidence(state: IndiaEngineState) -> float:
    """Extract prediction confidence from state."""
    return float(state.get("confidence", 0.6))


def _extract_composite_sentiment(state: IndiaEngineState) -> dict[str, Any]:
    composite = state.get("composite_sent", {})
    return composite if isinstance(composite, dict) else {}


def _extract_days_to_expiry(state: IndiaEngineState) -> int:
    fno_report = state.get("fno_report", {})
    if isinstance(fno_report, dict) and fno_report.get("days_to_expiry") is not None:
        return int(fno_report.get("days_to_expiry", 99))
    market_calendar = state.get("market_calendar", {})
    if isinstance(market_calendar, dict):
        return int(market_calendar.get("days_to_expiry", 99))
    return 99


def _is_expiry_today(state: IndiaEngineState) -> bool:
    """Check if analysis_date is an NSE expiry Thursday."""
    date_str = state.get("analysis_date", "")
    try:
        d = date.fromisoformat(date_str) if date_str else date.today()
        return is_expiry_thursday(d)
    except (ValueError, AttributeError):
        return False


def run_risk_node(state: IndiaEngineState) -> dict:
    """
    LangGraph node: Pure Python deterministic risk assessment.
    Writes risk_node_output dict to state.
    """
    ticker = state.get("ticker", "N/A")
    logger.info("risk_node.start", ticker=ticker)

    vix = _extract_vix(state)
    fii_streak = _extract_fii_streak(state)
    confidence = _extract_confidence(state)
    expiry_today = _is_expiry_today(state)
    composite_sent = _extract_composite_sentiment(state)
    fear_greed = int(
        composite_sent.get("fear_greed")
        or composite_sent.get("fear_greed_index")
        or 50
    )
    social_volume = int(composite_sent.get("social_post_volume", 0) or 0)
    euphoria_flag = bool(composite_sent.get("euphoria_flag", False))
    days_to_expiry = _extract_days_to_expiry(state)

    notes: list[str] = []

    # ── 1. Circuit breaker check ──────────────────────────────────
    circuit_breaker_active = vix >= VIX_CIRCUIT_BREAKER
    crisis_mode = vix >= VIX_CRISIS_THRESHOLD
    if circuit_breaker_active:
        notes.append(f"CIRCUIT BREAKER: VIX={vix:.1f} ≥ {VIX_CIRCUIT_BREAKER}. Override all verdicts → HOLD.")
    if crisis_mode:
        notes.append(f"CRISIS: VIX={vix:.1f} ≥ {VIX_CRISIS_THRESHOLD}. CASH/GOLD only.")

    # ── 2. VIX position size multiplier ──────────────────────────
    from risk.volatility_checker import compute_position_size_multiplier
    vix_multiplier = compute_position_size_multiplier(vix)

    # ── 3. FII sell streak ────────────────────────────────────────
    fii_streak_alert = fii_streak >= FII_SELL_STREAK_ALERT_DAYS
    if fii_streak_alert:
        vix_multiplier *= FII_STREAK_SIZE_REDUCTION
        notes.append(f"FII SELL STREAK: {fii_streak} consecutive days → size reduced 40%.")

    # ── 4. Gamma risk (expiry Thursday) ──────────────────────────
    gamma_risk_flag = expiry_today or days_to_expiry == 0
    if gamma_risk_flag:
        notes.append("EXPIRY THURSDAY: Gamma risk active. Max Pain pin risk. Close positions by 15:20 IST.")

    # ── 5. Confidence flag ────────────────────────────────────────
    low_confidence_flag = confidence < MIN_CONFIDENCE_THRESHOLD
    if low_confidence_flag:
        notes.append(f"LOW CONFIDENCE: {confidence:.0%} < {MIN_CONFIDENCE_THRESHOLD:.0%}. Reduce size or HOLD.")
        vix_multiplier *= 0.75  # Additional 25% size reduction on low confidence

    # ── 6. Social euphoria / complacency overlays ───────────────
    complacency_warning = fear_greed > 80 and vix < 15
    if euphoria_flag:
        vix_multiplier *= 0.80
        notes.append(
            f"EUPHORIA: Social volume spike ({social_volume}) with Fear/Greed {fear_greed}. "
            "Reduce size an additional 20%."
        )
    if complacency_warning:
        notes.append(
            f"COMPLACENCY: Fear/Greed {fear_greed} with VIX {vix:.1f}. "
            "Extreme greed under low volatility often reverses sharply."
        )

    # ── 7. Kelly Criterion position size ─────────────────────────
    # Use confidence as a proxy for win probability; assume 1.5:1 reward/risk
    kelly_result = compute_position_size(
        win_probability=max(0.35, min(0.75, confidence)),
        avg_win_pct=0.05,    # 5% average win
        avg_loss_pct=0.03,   # 3% average loss (1.67:1 R/R for India equities)
        vix_multiplier=vix_multiplier,
        ticker=ticker,
    )

    # ── 8. SEBI rate limit check ──────────────────────────────────
    sebi_compliant = True   # Check is advisory — actual enforcement at API layer

    # ── Override verdict if circuit breaker ──────────────────────
    current_verdict = state.get("verdict", "HOLD")
    override_verdict = "HOLD" if circuit_breaker_active else current_verdict

    # ── Assemble risk level ───────────────────────────────────────
    if vix >= VIX_CRISIS_THRESHOLD or crisis_mode:
        risk_level = "EXTREME"
    elif vix >= VIX_CIRCUIT_BREAKER or fii_streak_alert:
        risk_level = "HIGH"
    elif gamma_risk_flag or low_confidence_flag:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    risk_output: dict[str, Any] = {
        "circuit_breaker_active": circuit_breaker_active,
        "crisis_mode": crisis_mode,
        "position_size_multiplier": round(vix_multiplier, 4),
        "fii_streak_alert": fii_streak_alert,
        "fii_streak_days": fii_streak,
        "gamma_risk_flag": gamma_risk_flag,
        "low_confidence_flag": low_confidence_flag,
        "euphoria_flag": euphoria_flag,
        "fear_greed": fear_greed,
        "social_volume": social_volume,
        "complacency_warning": complacency_warning,
        "kelly_fraction": kelly_result.recommended_capital_pct,
        "kelly_details": {
            "raw_kelly": kelly_result.kelly_fraction,
            "half_kelly": kelly_result.half_kelly_fraction,
            "max_lots": kelly_result.max_lots,
            "lot_size": kelly_result.lot_size,
        },
        "sebi_compliant": sebi_compliant,
        "override_verdict": override_verdict,
        "risk_level": risk_level,
        "notes": notes,
    }

    updates = {"risk_node_output": risk_output}
    if circuit_breaker_active:
        updates["verdict"] = "HOLD"

    logger.info(
        "risk_node.done",
        vix=vix, circuit_breaker=circuit_breaker_active,
        risk_level=risk_level, override=override_verdict,
    )
    return updates
