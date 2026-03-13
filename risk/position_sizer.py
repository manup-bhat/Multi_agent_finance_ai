"""
Position Sizer — Kelly Criterion + India Lot Rules
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pure deterministic math. Zero LLM.

Kelly Criterion (half-Kelly for India risk management):
  f* = (edge / odds) × 0.5    (half-Kelly = safer for leveraged F&O)

  where:
    edge = win_prob - loss_prob
    odds = avg_win / avg_loss

India-specific constraints:
  - NSE F&O lot sizes (hardcoded for major indices/stocks)
  - SEBI margin requirement: 15–20% SPAN for index options
  - Max single position: 10% of portfolio (India practice)
  - Max leveraged F&O exposure: 20% of portfolio
"""
from __future__ import annotations
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

# Max position limits (India conservative practice)
MAX_SINGLE_POSITION_PCT = 0.10   # 10% max in any single stock/position
MAX_FNO_EXPOSURE_PCT    = 0.20   # 20% max in F&O
MIN_KELLY_FRACTION      = 0.01   # Don't take positions < 1%
MAX_KELLY_FRACTION      = 0.25   # Cap Kelly at 25% (safety)

# NSE lot sizes for major instruments (current as of 2026)
NSE_LOT_SIZES: dict[str, int] = {
    "NIFTY":     50,
    "BANKNIFTY": 15,
    "FINNIFTY":  40,
    "MIDCPNIFTY":75,
    "HDFCBANK":  550,
    "RELIANCE":  250,
    "TCS":       150,
    "INFY":      300,
    "ICICIBANK": 700,
    "SBIN":      1500,
    "DEFAULT":   100,
}


@dataclass
class PositionSizeResult:
    kelly_fraction: float          # Raw Kelly f*
    half_kelly_fraction: float     # Half-Kelly (recommended)
    capped_fraction: float         # After min/max capping
    vix_adjusted_fraction: float   # After VIX regime multiplier
    recommended_capital_pct: float # Final % of capital to deploy
    lot_size: int                  # NSE lot size (if applicable)
    max_lots: int                  # Maximum lots at recommended capital
    notes: list[str]


def compute_kelly_fraction(
    win_probability: float,
    avg_win_pct: float,
    avg_loss_pct: float,
) -> float:
    """
    Full Kelly Criterion.

    f* = (p × b - q) / b

    where:
        p = probability of win
        q = probability of loss = 1 - p
        b = avg_win / avg_loss (odds ratio)

    Returns:
        Kelly fraction (0.0–1.0, negative means don't bet)
    """
    if avg_loss_pct <= 0 or avg_win_pct <= 0:
        return 0.0
    b = avg_win_pct / avg_loss_pct
    q = 1.0 - win_probability
    kelly = (win_probability * b - q) / b
    return max(0.0, kelly)


def compute_position_size(
    win_probability: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    vix_multiplier: float = 1.0,
    portfolio_value: float = 1_000_000.0,
    ticker: str = "DEFAULT",
    price_per_unit: float = 100.0,
) -> PositionSizeResult:
    """
    Full position sizing with Kelly + VIX adjustment + India lot constraints.

    Args:
        win_probability:  Model's estimated probability of winning (0–1)
        avg_win_pct:      Average win as % of position (e.g. 0.05 = 5%)
        avg_loss_pct:     Average loss as % of position (e.g. 0.03 = 3%)
        vix_multiplier:   VIX regime multiplier (from volatility_checker)
        portfolio_value:  Total portfolio in INR
        ticker:           Instrument for lot size lookup
        price_per_unit:   Current price in INR

    Returns:
        PositionSizeResult
    """
    notes: list[str] = []
    kelly_raw = compute_kelly_fraction(win_probability, avg_win_pct, avg_loss_pct)
    half_kelly = kelly_raw * 0.5

    # Cap to safety limits
    capped = max(MIN_KELLY_FRACTION, min(half_kelly, MAX_KELLY_FRACTION))
    if capped >= MAX_KELLY_FRACTION:
        notes.append(f"Kelly capped at {MAX_KELLY_FRACTION:.0%} safety limit")

    # Apply VIX regime multiplier
    vix_adjusted = capped * vix_multiplier
    if vix_multiplier < 1.0:
        notes.append(f"VIX regime reduced size by {(1-vix_multiplier)*100:.0f}%")

    # Enforce max single position
    final_pct = min(vix_adjusted, MAX_SINGLE_POSITION_PCT)
    if final_pct < vix_adjusted:
        notes.append(f"Capped at {MAX_SINGLE_POSITION_PCT:.0%} max position rule")

    # Lot size
    lot_size = NSE_LOT_SIZES.get(ticker.upper().replace(".NS","").replace(".BO",""),
                                  NSE_LOT_SIZES["DEFAULT"])
    capital_to_deploy = portfolio_value * final_pct
    cost_per_lot = lot_size * price_per_unit * 0.15  # SPAN margin ~15%
    max_lots = max(0, int(capital_to_deploy / cost_per_lot)) if cost_per_lot > 0 else 0

    logger.info(
        "position_sizer.result",
        kelly=round(kelly_raw, 4), half_kelly=round(half_kelly, 4),
        vix_adj=round(vix_adjusted, 4), final=round(final_pct, 4),
        max_lots=max_lots,
    )
    return PositionSizeResult(
        kelly_fraction=round(kelly_raw, 4),
        half_kelly_fraction=round(half_kelly, 4),
        capped_fraction=round(capped, 4),
        vix_adjusted_fraction=round(vix_adjusted, 4),
        recommended_capital_pct=round(final_pct, 4),
        lot_size=lot_size,
        max_lots=max_lots,
        notes=notes,
    )
