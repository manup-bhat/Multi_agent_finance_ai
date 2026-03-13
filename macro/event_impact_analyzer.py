"""
Event Impact Analyzer — Rules-Based India Market Event Logic
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Deterministic Python rules for each India market event type.
No LLM involved. Based on historical behaviour + blueprint rules.

Event types (from config/india_calendar.py):
  RBI_MPC_ANNOUNCEMENT  → extreme caution, reduce size 50%
  BUDGET                → avoid new positions until 14:00 IST
  RBI_MPC               → caution week, reduce leveraged positions
  EXPIRY_DAY            → pin risk, straddle/strangle premium decay
  RESULTS_SEASON        → stock-specific volatility, reduce concentration
  EXPIRY_WEEK           → rising gamma, writer positioning active
  NORMAL                → standard risk rules apply
"""
from __future__ import annotations

from datetime import date
from dataclasses import dataclass
from typing import Optional

import structlog

from config.india_calendar import (
    classify_market_event,
    get_event_description,
    EVENT_RBI_MPC_DAY,
    EVENT_BUDGET,
    EVENT_RBI_MPC,
    EVENT_EXPIRY_DAY,
    EVENT_RESULTS_SEASON,
    EVENT_EXPIRY_WEEK,
    EVENT_NORMAL,
)
from config.constants import (
    VIX_ELEVATED_MAX,
    VIX_CIRCUIT_BREAKER,
)

logger = structlog.get_logger(__name__)


@dataclass
class EventImpactReport:
    """Complete event impact analysis for a trading day."""
    date: date
    event_type: str
    event_description: str
    volatility_multiplier: float    # Expected VIX spike above base
    position_size_multiplier: float # 0.0 – 1.0
    avoid_new_positions: bool
    preferred_strategies: list[str]
    avoid_strategies: list[str]
    vix_adjustment: float           # Expected VIX change on this event type
    trading_rules: list[str]
    risk_level: str                 # "LOW" / "MODERATE" / "HIGH" / "EXTREME"


# ── Event configurations ─────────────────────────────────────────────────────

_EVENT_CONFIG: dict[str, dict] = {
    EVENT_RBI_MPC_DAY: {
        "volatility_multiplier": 1.5,
        "position_size_multiplier": 0.5,
        "avoid_new_positions": True,
        "preferred_strategies": ["Straddle (pre-announcement)", "Stay Cash"],
        "avoid_strategies": ["Directional options", "Leveraged F&O"],
        "vix_adjustment": 3.0,
        "trading_rules": [
            "Reduce all leveraged positions by 50% before 10:00 IST",
            "Avoid naked options — IV will spike",
            "Straddle at ATM is a valid play if IV is not already elevated",
            "Post-announcement: wait 15 min for volatility to settle",
            "Rate-sensitive sectors (banking, NBFC, realty) will move sharply",
        ],
        "risk_level": "EXTREME",
    },
    EVENT_BUDGET: {
        "volatility_multiplier": 2.0,
        "position_size_multiplier": 0.3,
        "avoid_new_positions": True,
        "preferred_strategies": ["Straddle", "Stay Cash"],
        "avoid_strategies": ["All directional positions before 14:00 IST"],
        "vix_adjustment": 5.0,
        "trading_rules": [
            "Avoid all new positions until after Budget speech (typically ends 14:00 IST)",
            "Extreme circuit breaker risk if market disliked Budget",
            "Straddle is only F&O strategy suitable pre-Budget",
            "Post-Budget: wait 30 min for direction to crystallise",
            "Capital gains/STT changes can cause sharp sector rotations",
        ],
        "risk_level": "EXTREME",
    },
    EVENT_RBI_MPC: {
        "volatility_multiplier": 1.2,
        "position_size_multiplier": 0.7,
        "avoid_new_positions": False,
        "preferred_strategies": ["Iron Condor (sell premium)", "Defensive positions"],
        "avoid_strategies": ["High leverage", "Rate-sensitive naked longs"],
        "vix_adjustment": 1.5,
        "trading_rules": [
            "Reduce leveraged exposure on rate-sensitive stocks (HDFC, SBI, ICICI)",
            "Avoid adding to positions in banking / NBFC sector",
            "Iron Condor is valid if VIX is not already elevated",
        ],
        "risk_level": "HIGH",
    },
    EVENT_EXPIRY_DAY: {
        "volatility_multiplier": 1.1,
        "position_size_multiplier": 0.8,
        "avoid_new_positions": False,
        "preferred_strategies": ["Sell OTM options (theta decay)", "Max Pain play"],
        "avoid_strategies": ["Long straddles (theta crushed on expiry)"],
        "vix_adjustment": 1.0,
        "trading_rules": [
            "ATM max pain gravity zone applies — spot tends to pin near max pain",
            "Option theta decay is accelerated — avoid being long options",
            "Close all positions by 15:20 IST to avoid settlement risk",
            "Intraday volatility peaks near 14:00–15:00 IST on expiry",
        ],
        "risk_level": "MODERATE",
    },
    EVENT_RESULTS_SEASON: {
        "volatility_multiplier": 1.15,
        "position_size_multiplier": 0.85,
        "avoid_new_positions": False,
        "preferred_strategies": ["Straddle on individual stocks", "Cash-neutral pairs"],
        "avoid_strategies": ["Concentrated positions in results stocks"],
        "vix_adjustment": 1.5,
        "trading_rules": [
            "Reduce concentration: no single stock > 5% of portfolio",
            "Avoid holding naked positions into results announcements",
            "Straddle on individual results stocks can capture the jump",
        ],
        "risk_level": "MODERATE",
    },
    EVENT_EXPIRY_WEEK: {
        "volatility_multiplier": 1.05,
        "position_size_multiplier": 0.9,
        "avoid_new_positions": False,
        "preferred_strategies": ["Covered calls", "Iron Condor", "OTM credit spreads"],
        "avoid_strategies": ["Long gamma positions (theta headwind)"],
        "vix_adjustment": 0.5,
        "trading_rules": [
            "Gamma is rising — option writers are active near max pain",
            "Ideal for credit strategies (iron condor, credit spread)",
            "Watch for sudden intraday reversals due to writer delta hedging",
        ],
        "risk_level": "MODERATE",
    },
    EVENT_NORMAL: {
        "volatility_multiplier": 1.0,
        "position_size_multiplier": 1.0,
        "avoid_new_positions": False,
        "preferred_strategies": ["Any strategy per model signal"],
        "avoid_strategies": [],
        "vix_adjustment": 0.0,
        "trading_rules": ["Standard risk rules apply. Follow model signals."],
        "risk_level": "LOW",
    },
}


def compute_event_volatility_multiplier(event_type: str, current_vix: float = 15.0) -> float:
    """
    Compute expected volatility multiplier for an event type.
    If VIX is already elevated, the multiplier is capped (can't spike much more).
    """
    cfg = _EVENT_CONFIG.get(event_type, _EVENT_CONFIG[EVENT_NORMAL])
    base_mult = cfg["volatility_multiplier"]

    # Dampen multiplier when VIX is already high
    if current_vix >= VIX_CIRCUIT_BREAKER:
        return min(base_mult, 1.1)   # circuit breaker already active
    elif current_vix >= VIX_ELEVATED_MAX:
        return min(base_mult, 1.3)
    return base_mult


def get_event_trading_rules(event_type: str) -> dict:
    """
    Return trading rules for an event type.

    Returns:
        dict with position_size_multiplier, rules, preferred/avoid strategies
    """
    cfg = _EVENT_CONFIG.get(event_type, _EVENT_CONFIG[EVENT_NORMAL])
    return {
        "position_size_multiplier": cfg["position_size_multiplier"],
        "avoid_new_positions": cfg["avoid_new_positions"],
        "preferred_strategies": cfg["preferred_strategies"],
        "avoid_strategies": cfg["avoid_strategies"],
        "trading_rules": cfg["trading_rules"],
        "risk_level": cfg["risk_level"],
    }


def build_event_impact_report(
    dt: Optional[date] = None,
    current_vix: float = 15.0,
) -> EventImpactReport:
    """
    Build a complete event impact report for a given date.

    Args:
        dt: Date to analyze (defaults to today)
        current_vix: Current India VIX (affects dampened multiplier)

    Returns:
        EventImpactReport dataclass
    """
    from datetime import date as date_cls
    if dt is None:
        dt = date_cls.today()

    event_type = classify_market_event(dt)
    cfg = _EVENT_CONFIG.get(event_type, _EVENT_CONFIG[EVENT_NORMAL])
    vol_mult = compute_event_volatility_multiplier(event_type, current_vix)

    report = EventImpactReport(
        date=dt,
        event_type=event_type,
        event_description=get_event_description(event_type),
        volatility_multiplier=vol_mult,
        position_size_multiplier=cfg["position_size_multiplier"],
        avoid_new_positions=cfg["avoid_new_positions"],
        preferred_strategies=cfg["preferred_strategies"],
        avoid_strategies=cfg["avoid_strategies"],
        vix_adjustment=cfg["vix_adjustment"],
        trading_rules=cfg["trading_rules"],
        risk_level=cfg["risk_level"],
    )
    logger.info(
        "event_impact.report",
        date=str(dt), event_type_key=event_type,
        risk=cfg["risk_level"], size_mult=cfg["position_size_multiplier"],
    )
    return report
