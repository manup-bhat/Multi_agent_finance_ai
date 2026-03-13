"""
Drift Detector — Rolling Accuracy & Regime-Aware Drift Monitoring
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint:
  drift_detector.py: rolling 30-day accuracy per regime
  If accuracy < 55% → retrain_trigger.py → Optuna re-tunes models

This module:
  1. Computes rolling 30-day directional accuracy with a sliding window
  2. Detects accuracy drift per market regime (BULL / SIDEWAYS / BEAR)
  3. Uses simple statistical test (binomial Z-score) to distinguish
     noise vs genuine performance degradation
  4. Returns DriftReport with per-regime flags and overall drift verdict

Background: Concept drift in financial ML is common when:
  - Market regime changes (Bull → Bear) → historical features less predictive
  - Data distribution shifts (new sector correlation, policy change)
  - India-specific: RBI surprise, budget, FII structural change
"""
from __future__ import annotations

import math
import datetime
from dataclasses import dataclass, field
from typing import Optional
import structlog

logger = structlog.get_logger(__name__)

# Blueprint thresholds from config/constants.py
_MIN_ACCURACY   = 0.55   # matches WFO_MIN_DIRECTIONAL_ACCURACY
_MIN_SAMPLE     = 10     # minimum resolved rows for reliable drift detection
_Z_SCORE_ALERT  = -1.65  # 5th percentile one-tailed (significant underperformance)


@dataclass
class RegimeDriftStatus:
    """Per-regime drift assessment."""
    regime:         str
    n_predictions:  int
    n_correct:      int
    accuracy:       float
    z_score:        float          # binomial Z relative to 0.55 null hypothesis
    drift_detected: bool
    note:           str


@dataclass
class DriftReport:
    """Full drift detection output for a given window."""
    ticker:              str
    window_start:        datetime.date
    window_end:          datetime.date
    overall_accuracy:    float
    n_total:             int
    overall_drift:       bool       # True = significant drift detected
    regime_statuses:     list[RegimeDriftStatus]
    retrain_recommended: bool       # True if any regime is drifting
    notes:               list[str] = field(default_factory=list)


def _binomial_z(n_correct: int, n_total: int, p0: float = _MIN_ACCURACY) -> float:
    """
    One-sample binomial Z-score vs null hypothesis p0.

    Z = (p_hat - p0) / sqrt(p0 * (1 - p0) / n)
    Negative Z → underperforming. Z < -1.65 → significant at 5%.
    """
    if n_total < _MIN_SAMPLE:
        return 0.0
    p_hat = n_correct / n_total
    se    = math.sqrt(p0 * (1 - p0) / n_total)
    return (p_hat - p0) / se if se > 0 else 0.0


class DriftDetector:
    """
    Detects model accuracy drift over a rolling window.

    Usage:
        detector = DriftDetector(prediction_logger)
        report   = detector.detect(window_days=30, ticker="HDFCBANK.NS")
    """

    def __init__(self, prediction_logger):
        self.prediction_logger = prediction_logger

    def detect(
        self,
        window_days: int = 30,
        ticker: Optional[str] = None,
        as_of_date: Optional[datetime.date] = None,
    ) -> DriftReport:
        """
        Compute drift over the last `window_days` of resolved predictions.

        Args:
            window_days: Rolling window size in calendar days
            ticker:      Specific ticker or None for all
            as_of_date:  End of window (default: today)

        Returns:
            DriftReport
        """
        as_of_date   = as_of_date or datetime.date.today()
        window_start = as_of_date - datetime.timedelta(days=window_days)

        rows = self.prediction_logger.get_recent(ticker=ticker, days=window_days)
        resolved = [r for r in rows if r.directional_match is not None]

        if not resolved:
            logger.warning("drift_detector.no_resolved", ticker=ticker, window=window_days)
            return DriftReport(
                ticker=ticker or "ALL",
                window_start=window_start,
                window_end=as_of_date,
                overall_accuracy=0.0,
                n_total=0,
                overall_drift=False,
                regime_statuses=[],
                retrain_recommended=False,
                notes=["No resolved predictions in window — cannot assess drift."],
            )

        # ── Overall accuracy ──────────────────────────────────────────────────
        matches    = [r.directional_match for r in resolved]
        n_total    = len(matches)
        n_correct  = sum(matches)
        overall_acc = n_correct / n_total

        overall_z    = _binomial_z(n_correct, n_total)
        overall_drift = overall_z < _Z_SCORE_ALERT

        # ── Per-regime breakdown ──────────────────────────────────────────────
        regime_map: dict[str, list[int]] = {}
        for row in resolved:
            regime_map.setdefault(row.market_regime or "UNKNOWN", []).append(
                row.directional_match
            )

        regime_statuses: list[RegimeDriftStatus] = []
        any_regime_drift = False

        for regime, matches_list in regime_map.items():
            nr  = len(matches_list)
            nc  = sum(matches_list)
            acc = nc / nr
            z   = _binomial_z(nc, nr)
            drift = (z < _Z_SCORE_ALERT) and (nr >= _MIN_SAMPLE)

            if drift:
                any_regime_drift = True
                note = (f"⚠️ {regime} drift: {acc:.1%} accuracy, Z={z:.2f} "
                        f"(< -1.65 threshold)")
            elif nr < _MIN_SAMPLE:
                note = f"Only {nr} samples — insufficient for reliability."
            else:
                note = f"{regime}: {acc:.1%} — within tolerance."

            regime_statuses.append(RegimeDriftStatus(
                regime=regime, n_predictions=nr, n_correct=nc,
                accuracy=round(acc, 4), z_score=round(z, 4),
                drift_detected=drift, note=note,
            ))

        retrain_recommended = overall_drift or any_regime_drift

        notes: list[str] = []
        if overall_drift:
            notes.append(
                f"Overall accuracy {overall_acc:.1%} has drifted significantly "
                f"(Z={overall_z:.2f} < -1.65). Retrain recommended."
            )
        if not overall_drift and not any_regime_drift:
            notes.append(f"No drift detected. Overall accuracy = {overall_acc:.1%}.")

        logger.info(
            "drift_detector.result",
            ticker=ticker or "ALL",
            accuracy=round(overall_acc, 4),
            drift=overall_drift,
            retrain=retrain_recommended,
        )

        return DriftReport(
            ticker=ticker or "ALL",
            window_start=window_start,
            window_end=as_of_date,
            overall_accuracy=round(overall_acc, 4),
            n_total=n_total,
            overall_drift=overall_drift,
            regime_statuses=regime_statuses,
            retrain_recommended=retrain_recommended,
            notes=notes,
        )
