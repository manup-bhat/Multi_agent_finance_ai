"""
Brent Crude Tracker — India Macro Impact
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
India is the 3rd largest crude importer globally (~85% import dependent).
Brent crude directly impacts: CAD, inflation, INR, PSU oil stock earnings.

India-specific price thresholds (research-validated, March 2026):
  < 75 USD/bbl  → SUPPORTIVE   (low inflation, CAD comfortable, positive for markets)
  75–95 USD/bbl → NEUTRAL
  > 95 USD/bbl  → INFLATIONARY (CAD pressure, RBI rate concerns, FII risk-off)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass

logger = structlog.get_logger(__name__)

# Crude regime thresholds (India-specific)
CRUDE_SUPPORTIVE  = "SUPPORTIVE"
CRUDE_NEUTRAL     = "NEUTRAL"
CRUDE_INFLATIONARY = "INFLATIONARY"

CRUDE_SUPPORTIVE_MAX   = 75.0   # USD/bbl
CRUDE_NEUTRAL_MAX      = 95.0   # USD/bbl

# Nifty directional signals
CRUDE_NIFTY_POSITIVE = "POSITIVE"
CRUDE_NIFTY_NEGATIVE = "NEGATIVE"
CRUDE_NIFTY_NEUTRAL  = "NEUTRAL"


@dataclass
class CrudeAnalysis:
    """Brent crude analysis result."""
    current_price: float        # USD/bbl
    regime: str                 # SUPPORTIVE / NEUTRAL / INFLATIONARY
    change_pct_10d: float       # 10-day % change
    nifty_correlation_20d: float
    nifty_signal: str           # POSITIVE / NEUTRAL / NEGATIVE
    cad_risk: bool              # True if regime is INFLATIONARY
    inr_pressure: bool          # True if crude > 95 (CAD → INR pressure)
    description: str


def classify_crude_regime(
    brent_series: pd.Series | list[float] | np.ndarray,
) -> str:
    """
    Classify Brent crude into India macro impact regime.

    Returns:
        "SUPPORTIVE" / "NEUTRAL" / "INFLATIONARY"
    """
    s = np.asarray(brent_series, dtype=float)
    current = float(s[-1]) if len(s) > 0 else 80.0
    return classify_crude_from_price(current)


def classify_crude_from_price(price: float) -> str:
    """Classify a single crude price into regime."""
    if price < CRUDE_SUPPORTIVE_MAX:
        return CRUDE_SUPPORTIVE
    elif price < CRUDE_NEUTRAL_MAX:
        return CRUDE_NEUTRAL
    return CRUDE_INFLATIONARY


def crude_cad_impact_signal(price: float) -> str:
    """
    India-specific: crude > 95 → CAD widens → INR pressure → FII outflow risk.
    Returns a directional signal for the macro report.
    """
    if price > CRUDE_NEUTRAL_MAX:
        return CRUDE_NIFTY_NEGATIVE
    elif price < CRUDE_SUPPORTIVE_MAX:
        return CRUDE_NIFTY_POSITIVE
    return CRUDE_NIFTY_NEUTRAL


def compute_crude_nifty_correlation(
    brent_series: pd.Series | list[float] | np.ndarray,
    nifty_series: pd.Series | list[float] | np.ndarray,
    window: int = 20,
) -> float:
    """
    Rolling correlation between Brent (USD/bbl) and Nifty 50.

    Context: Moderate crude is correlated with global growth (positive).
    High crude = inflationary = negative for Nifty.

    Returns:
        Pearson correlation coefficient over last `window` days.
    """
    s1 = np.asarray(brent_series, dtype=float)
    s2 = np.asarray(nifty_series, dtype=float)
    n = min(len(s1), len(s2), window)
    if n < 5:
        return 0.0

    s1r = s1[-n:]
    s2r = s2[-n:]
    if np.std(s1r) == 0 or np.std(s2r) == 0:
        return 0.0
    return float(np.corrcoef(s1r, s2r)[0, 1])


def analyze_crude(
    brent_series: pd.Series | list[float] | np.ndarray,
    nifty_series: pd.Series | list[float] | np.ndarray | None = None,
    window: int = 10,
) -> CrudeAnalysis:
    """Full Brent crude analysis for India macro report."""
    s = np.asarray(brent_series, dtype=float)
    current = float(s[-1]) if len(s) > 0 else 80.0
    regime = classify_crude_from_price(current)
    nifty_signal = crude_cad_impact_signal(current)

    lookback = s[-window:] if len(s) >= window else s
    pct_change = round(
        (lookback[-1] - lookback[0]) / lookback[0] * 100, 4
    ) if len(lookback) >= 2 else 0.0

    nifty_corr = 0.0
    if nifty_series is not None:
        nifty_corr = compute_crude_nifty_correlation(s, nifty_series)

    cad_risk = regime == CRUDE_INFLATIONARY
    inr_pressure = current > CRUDE_NEUTRAL_MAX

    if regime == CRUDE_INFLATIONARY:
        desc = (
            f"Brent ${current:.1f}/bbl — INFLATIONARY. "
            f"India CAD pressured. INR at risk. FII outflow probability elevated."
        )
    elif regime == CRUDE_SUPPORTIVE:
        desc = (
            f"Brent ${current:.1f}/bbl — SUPPORTIVE. "
            f"Low import bill. Inflation comfortable. Positive for consumption."
        )
    else:
        desc = f"Brent ${current:.1f}/bbl — NEUTRAL. No significant macro stress."

    logger.info("crude.analysis", price=current, regime=regime, cad_risk=cad_risk)
    return CrudeAnalysis(
        current_price=round(current, 2),
        regime=regime,
        change_pct_10d=pct_change,
        nifty_correlation_20d=round(nifty_corr, 4),
        nifty_signal=nifty_signal,
        cad_risk=cad_risk,
        inr_pressure=inr_pressure,
        description=desc,
    )
