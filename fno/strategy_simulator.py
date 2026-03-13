"""
Options Strategy Simulator
━━━━━━━━━━━━━━━━━━━━━━━━━
Payoff simulation for common F&O strategies:
  - Long/Short Straddle, Strangle
  - Bull/Bear Call/Put Spreads
  - Iron Condor, Iron Butterfly
  - Custom multi-leg strategies

Each leg is defined as:
  {"strike": K, "option_type": "CE"/"PE", "action": "BUY"/"SELL", "premium": p, "lots": n}
"""
from __future__ import annotations

import numpy as np
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

# NSE lot size defaults for common indices
DEFAULT_LOT_SIZES: dict[str, int] = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
}


@dataclass
class StrategyPayoff:
    """Strategy payoff analysis result."""
    strategy_name: str
    legs: list[dict]
    breakevens: list[float]
    max_profit: float           # positive value
    max_loss: float             # negative value
    net_premium: float          # positive = credit, negative = debit
    spot_range: np.ndarray
    payoff_array: np.ndarray
    risk_reward_ratio: float


def _leg_payoff_at_expiry(
    spot: float | np.ndarray,
    strike: float,
    option_type: str,
    action: str,
    premium: float,
    lots: int = 1,
    lot_size: int = 1,
) -> float | np.ndarray:
    """
    Compute payoff of a single leg at expiry for given spot(s).

    Returns:
        Payoff per unit (multiply by lots * lot_size for total P&L)
    """
    ot = option_type.upper().strip()
    act = action.upper().strip()

    if ot in ("CE", "C", "CALL"):
        intrinsic = np.maximum(0, spot - strike)
    elif ot in ("PE", "P", "PUT"):
        intrinsic = np.maximum(0, strike - spot)
    else:
        raise ValueError(f"Unknown option_type: {option_type}")

    if act == "BUY":
        pnl = (intrinsic - premium) * lots * lot_size
    elif act == "SELL":
        pnl = (premium - intrinsic) * lots * lot_size
    else:
        raise ValueError(f"Unknown action: {action}. Use BUY or SELL.")

    return pnl


def simulate_payoff(
    legs: list[dict],
    spot_range: np.ndarray | None = None,
    lot_size: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Simulate total payoff for a multi-leg strategy.

    Args:
        legs: list of dicts, each with keys:
              strike, option_type, action, premium, lots (optional, default=1)
        spot_range: array of spot prices to evaluate. If None, auto-generated.
        lot_size: contract lot size (default 1 for per-unit analysis)

    Returns:
        (spot_range, payoff_array)
    """
    if not legs:
        raise ValueError("Must provide at least one leg")

    strikes = [leg["strike"] for leg in legs]
    min_strike = min(strikes)
    max_strike = max(strikes)

    if spot_range is None:
        margin = (max_strike - min_strike) * 0.5 if max_strike > min_strike else max_strike * 0.1
        low = min_strike - margin
        high = max_strike + margin
        spot_range = np.linspace(max(0, low), high, 500)

    total_payoff = np.zeros_like(spot_range, dtype=np.float64)

    for leg in legs:
        total_payoff += _leg_payoff_at_expiry(
            spot=spot_range,
            strike=leg["strike"],
            option_type=leg["option_type"],
            action=leg["action"],
            premium=leg["premium"],
            lots=leg.get("lots", 1),
            lot_size=lot_size,
        )

    return spot_range, total_payoff


def compute_breakevens(
    legs: list[dict],
    lot_size: int = 1,
    precision: int = 2,
) -> list[float]:
    """
    Find breakeven points where payoff crosses zero.
    Uses fine-grained numerical search.

    Returns:
        Sorted list of breakeven prices.
    """
    strikes = [leg["strike"] for leg in legs]
    min_strike = min(strikes)
    max_strike = max(strikes)
    margin = (max_strike - min_strike) * 1.0 if max_strike > min_strike else max_strike * 0.2

    spot_range = np.linspace(max(0.01, min_strike - margin), max_strike + margin, 10000)
    _, payoff = simulate_payoff(legs, spot_range, lot_size)

    # Find zero crossings (sign changes)
    breakevens = []
    for i in range(1, len(payoff)):
        if payoff[i - 1] * payoff[i] < 0:  # sign change
            # Linear interpolation for precise crossing
            x1, x2 = spot_range[i - 1], spot_range[i]
            y1, y2 = payoff[i - 1], payoff[i]
            x_cross = x1 - y1 * (x2 - x1) / (y2 - y1)
            breakevens.append(round(float(x_cross), precision))

    return sorted(set(breakevens))


def compute_max_profit_loss(
    legs: list[dict],
    lot_size: int = 1,
) -> dict:
    """
    Compute max profit and max loss for a strategy.

    Returns:
        {"max_profit": float, "max_loss": float, "net_premium": float}
    """
    _, payoff = simulate_payoff(legs, lot_size=lot_size)

    max_profit = float(np.max(payoff))
    max_loss = float(np.min(payoff))
    net_premium = sum(
        leg["premium"] * leg.get("lots", 1) * lot_size * (-1 if leg["action"].upper() == "BUY" else 1)
        for leg in legs
    )

    return {
        "max_profit": round(max_profit, 2),
        "max_loss": round(max_loss, 2),
        "net_premium": round(net_premium, 2),
    }


def analyze_strategy(
    strategy_name: str,
    legs: list[dict],
    lot_size: int = 1,
) -> StrategyPayoff:
    """
    Full strategy analysis: payoff, breakevens, max P&L, risk-reward.
    """
    spot_range, payoff = simulate_payoff(legs, lot_size=lot_size)
    breakevens = compute_breakevens(legs, lot_size)
    pnl = compute_max_profit_loss(legs, lot_size)

    rr_ratio = (
        abs(pnl["max_profit"] / pnl["max_loss"])
        if pnl["max_loss"] != 0 else float("inf")
    )

    return StrategyPayoff(
        strategy_name=strategy_name,
        legs=legs,
        breakevens=breakevens,
        max_profit=pnl["max_profit"],
        max_loss=pnl["max_loss"],
        net_premium=pnl["net_premium"],
        spot_range=spot_range,
        payoff_array=payoff,
        risk_reward_ratio=round(rr_ratio, 2),
    )


# ── Pre-built Strategy Constructors ──────────────────────────────────────


def build_straddle(
    atm_strike: float,
    call_premium: float,
    put_premium: float,
    action: str = "BUY",
    lots: int = 1,
) -> list[dict]:
    """Build a straddle (same strike CE + PE)."""
    return [
        {"strike": atm_strike, "option_type": "CE", "action": action,
         "premium": call_premium, "lots": lots},
        {"strike": atm_strike, "option_type": "PE", "action": action,
         "premium": put_premium, "lots": lots},
    ]


def build_strangle(
    call_strike: float,
    put_strike: float,
    call_premium: float,
    put_premium: float,
    action: str = "BUY",
    lots: int = 1,
) -> list[dict]:
    """Build a strangle (OTM CE + OTM PE)."""
    return [
        {"strike": call_strike, "option_type": "CE", "action": action,
         "premium": call_premium, "lots": lots},
        {"strike": put_strike, "option_type": "PE", "action": action,
         "premium": put_premium, "lots": lots},
    ]


def build_iron_condor(
    put_buy_strike: float,
    put_sell_strike: float,
    call_sell_strike: float,
    call_buy_strike: float,
    premiums: dict,
    lots: int = 1,
) -> list[dict]:
    """
    Build an Iron Condor.
    premiums: {"put_buy": x, "put_sell": x, "call_sell": x, "call_buy": x}
    """
    return [
        {"strike": put_buy_strike, "option_type": "PE", "action": "BUY",
         "premium": premiums["put_buy"], "lots": lots},
        {"strike": put_sell_strike, "option_type": "PE", "action": "SELL",
         "premium": premiums["put_sell"], "lots": lots},
        {"strike": call_sell_strike, "option_type": "CE", "action": "SELL",
         "premium": premiums["call_sell"], "lots": lots},
        {"strike": call_buy_strike, "option_type": "CE", "action": "BUY",
         "premium": premiums["call_buy"], "lots": lots},
    ]


def build_bull_call_spread(
    buy_strike: float,
    sell_strike: float,
    buy_premium: float,
    sell_premium: float,
    lots: int = 1,
) -> list[dict]:
    """Build a Bull Call Spread (buy lower CE, sell higher CE)."""
    return [
        {"strike": buy_strike, "option_type": "CE", "action": "BUY",
         "premium": buy_premium, "lots": lots},
        {"strike": sell_strike, "option_type": "CE", "action": "SELL",
         "premium": sell_premium, "lots": lots},
    ]


def build_bear_put_spread(
    buy_strike: float,
    sell_strike: float,
    buy_premium: float,
    sell_premium: float,
    lots: int = 1,
) -> list[dict]:
    """Build a Bear Put Spread (buy higher PE, sell lower PE)."""
    return [
        {"strike": buy_strike, "option_type": "PE", "action": "BUY",
         "premium": buy_premium, "lots": lots},
        {"strike": sell_strike, "option_type": "PE", "action": "SELL",
         "premium": sell_premium, "lots": lots},
    ]
