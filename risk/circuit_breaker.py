"""
Circuit Breaker — Deterministic VIX Override
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure Python. Zero LLM. Hard override when India VIX crosses thresholds.

Blueprint rules:
  VIX ≥ 25 (CIRCUIT BREAKER) → override all verdicts to HOLD
  VIX ≥ 30 (CRISIS)          → force CASH/GOLD only
"""
from __future__ import annotations
import structlog
from config.constants import VIX_CIRCUIT_BREAKER, VIX_CRISIS_THRESHOLD

logger = structlog.get_logger(__name__)


def is_circuit_breaker_active(vix: float) -> bool:
    """True if VIX ≥ 25 (circuit breaker threshold)."""
    return vix >= VIX_CIRCUIT_BREAKER


def is_crisis_mode(vix: float) -> bool:
    """True if VIX ≥ 30 (full crisis — cash only)."""
    return vix >= VIX_CRISIS_THRESHOLD


def apply_circuit_breaker(verdict: str, vix: float) -> tuple[str, str]:
    """
    Apply circuit breaker logic to a proposed verdict.

    Returns:
        (overridden_verdict, reason)
    """
    if is_crisis_mode(vix):
        reason = f"CRISIS (VIX={vix:.1f} ≥ {VIX_CRISIS_THRESHOLD}): forced HOLD. Deploy CASH/GOLD only."
        logger.warning("circuit_breaker.crisis", vix=vix, original=verdict, override="HOLD")
        return "HOLD", reason

    if is_circuit_breaker_active(vix):
        reason = f"CIRCUIT BREAKER (VIX={vix:.1f} ≥ {VIX_CIRCUIT_BREAKER}): forced HOLD."
        logger.warning("circuit_breaker.active", vix=vix, original=verdict, override="HOLD")
        return "HOLD", reason

    return verdict, ""
