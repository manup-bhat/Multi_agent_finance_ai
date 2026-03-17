"""
Simple drawdown monitoring utilities.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class DrawdownSnapshot:
    current_drawdown_pct: float
    max_drawdown_pct: float
    peak_value: float
    latest_value: float


def compute_drawdown_snapshot(equity_curve: pd.Series) -> DrawdownSnapshot:
    """Return current and max drawdown for a portfolio equity curve."""
    if equity_curve is None or equity_curve.empty:
        return DrawdownSnapshot(
            current_drawdown_pct=0.0,
            max_drawdown_pct=0.0,
            peak_value=0.0,
            latest_value=0.0,
        )

    peak = equity_curve.cummax()
    drawdown = (equity_curve / peak) - 1.0
    return DrawdownSnapshot(
        current_drawdown_pct=float(drawdown.iloc[-1]),
        max_drawdown_pct=float(drawdown.min()),
        peak_value=float(peak.iloc[-1]),
        latest_value=float(equity_curve.iloc[-1]),
    )
