"""
Accuracy Tracker — T+N Outcome Resolution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint:
  T+N: APScheduler runs accuracy_tracker.py → compare vs actual
  Compute rolling 30-day directional accuracy per regime.
  If accuracy < 55% → retrain_trigger.py → Optuna re-tunes models.

This module:
  1. Fetches unresolved predictions from DB
  2. Gets actual price at T+N (via yfinance)
  3. Determines actual direction (BULLISH/BEARISH/FLAT)
  4. Fills `actual_price_tn`, `directional_match`, `pct_error`
  5. Returns accuracy summary statistics per ticker and regime

Designed to be called by APScheduler daily at 18:30 IST (after NSE close + FII data).
"""
from __future__ import annotations

import datetime
import structlog
from dataclasses import dataclass, field
from typing import Optional

logger = structlog.get_logger(__name__)

# Blueprint directional threshold: ≥ 0.5% move = BULLISH/BEARISH, else FLAT
DIRECTION_THRESHOLD_PCT = 0.005   # 0.5% move = directional (not flat)


@dataclass
class AccuracySummary:
    """Rolling accuracy statistics for a ticker (or all tickers)."""
    ticker:               str
    n_resolved:           int
    n_correct:            int
    directional_accuracy: float          # n_correct / n_resolved
    avg_pct_error:        float          # mean |actual - p50| / p50
    regime_breakdown:     dict[str, float]  # {BULL: 0.68, BEAR: 0.51, SIDEWAYS: 0.59}
    period_days:          int
    below_threshold:      bool           # True if accuracy < WFO_MIN_DIRECTIONAL_ACCURACY
    notes:                list[str] = field(default_factory=list)


def classify_direction(
    price_at_prediction: float,
    price_at_resolution: float,
    threshold_pct: float = DIRECTION_THRESHOLD_PCT,
) -> str:
    """
    Classify a price move as BULLISH / BEARISH / FLAT.

    Blueprint: A move ≥ 0.5% is directional; < 0.5% is FLAT (HOLD is correct).
    """
    if price_at_prediction <= 0:
        return "FLAT"
    change = (price_at_resolution - price_at_prediction) / price_at_prediction
    if change >= threshold_pct:
        return "BULLISH"
    elif change <= -threshold_pct:
        return "BEARISH"
    return "FLAT"


def compute_accuracy(
    directional_matches: list[int],
    pct_errors: list[float],
    regime_labels: list[Optional[str]],
) -> AccuracySummary:
    """
    Compute directional accuracy from a list of match results.

    Args:
        directional_matches: List[int] — 1=correct, 0=wrong
        pct_errors:          List[float] — per-row |actual-p50|/p50 (may contain None)
        regime_labels:       List[str] — HMM regime per row

    Returns:
        AccuracySummary
    """
    n = len(directional_matches)
    if n == 0:
        return AccuracySummary(
            ticker="ALL", n_resolved=0, n_correct=0, directional_accuracy=0.0,
            avg_pct_error=0.0, regime_breakdown={}, period_days=0,
            below_threshold=True, notes=["No resolved predictions yet."],
        )

    n_correct = sum(directional_matches)
    accuracy  = n_correct / n

    valid_errors = [e for e in pct_errors if e is not None]
    avg_err = sum(valid_errors) / len(valid_errors) if valid_errors else 0.0

    # Per-regime accuracy
    regime_map: dict[str, list[int]] = {}
    for match, regime in zip(directional_matches, regime_labels):
        key = regime or "UNKNOWN"
        regime_map.setdefault(key, []).append(match)
    regime_breakdown = {
        k: round(sum(v) / len(v), 4) for k, v in regime_map.items()
    }

    from config.constants import WFO_MIN_DIRECTIONAL_ACCURACY
    below = accuracy < WFO_MIN_DIRECTIONAL_ACCURACY

    notes: list[str] = []
    if below:
        notes.append(
            f"⚠️ Accuracy {accuracy:.1%} < threshold {WFO_MIN_DIRECTIONAL_ACCURACY:.0%}. "
            "Retrain trigger recommended."
        )
    for regime, acc in regime_breakdown.items():
        if acc < WFO_MIN_DIRECTIONAL_ACCURACY:
            notes.append(f"{regime} regime accuracy {acc:.1%} below threshold.")

    return AccuracySummary(
        ticker="ALL",
        n_resolved=n,
        n_correct=n_correct,
        directional_accuracy=round(accuracy, 4),
        avg_pct_error=round(avg_err, 4),
        regime_breakdown=regime_breakdown,
        period_days=30,
        below_threshold=below,
        notes=notes,
    )


class AccuracyTracker:
    """
    APScheduler-compatible accuracy tracker.

    Usage:
        tracker = AccuracyTracker(prediction_logger, price_fetcher)
        summary = tracker.run(as_of_date=date.today())
    """

    def __init__(
        self,
        prediction_logger,          # feedback.prediction_logger.PredictionLogger
        price_fetcher=None,         # Callable[[str, date], float] — yfinance fetch
    ):
        self.prediction_logger = prediction_logger
        self.price_fetcher     = price_fetcher or self._default_price_fetcher

    @staticmethod
    def _default_price_fetcher(ticker: str, as_of_date: datetime.date) -> Optional[float]:
        """
        Default: fetch closing price from yfinance for given date.
        Returns None if unavailable.
        """
        try:
            import yfinance as yf
            end_dt = as_of_date + datetime.timedelta(days=5)   # allow for holidays
            data   = yf.download(ticker, start=as_of_date, end=end_dt,
                                 progress=False, auto_adjust=True)
            if data.empty:
                return None
            import pandas as pd
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return float(data["Close"].iloc[0])
        except Exception as e:
            logger.warning("accuracy_tracker.price_fetch_failed", ticker=ticker, error=str(e))
            return None

    def resolve_pending(self, as_of_date: datetime.date) -> int:
        """
        Find unresolved rows, fetch actual prices, fill actuals.

        Returns: number of rows resolved
        """
        # Fetch all rows where actual hasn't been filled but window has passed
        from feedback.prediction_logger import PredictionRecord
        resolved = 0

        recent = self.prediction_logger.get_recent(days=90)
        for row in recent:
            if row.actual_price_tn is not None:
                continue   # already resolved

            resolution_date = row.analysis_date + datetime.timedelta(days=row.horizon_days)
            if resolution_date > as_of_date:
                continue   # not yet due

            actual_price = self.price_fetcher(row.ticker, resolution_date)
            if actual_price is None:
                logger.warning("accuracy_tracker.no_price", ticker=row.ticker,
                                date=str(resolution_date))
                continue

            # Estimate entry price: we use predicted_p50 as the "prediction-time price"
            # In production this would be fetched from DB's analysis_date close price
            entry_price = row.predicted_p50 or actual_price
            actual_dir  = classify_direction(entry_price, actual_price)

            self.prediction_logger.fill_actual(
                row_id=row.id,
                actual_price_tn=actual_price,
                actual_direction=actual_dir,
            )
            resolved += 1

        logger.info("accuracy_tracker.resolved", n=resolved, date=str(as_of_date))
        return resolved

    def compute_rolling_accuracy(
        self,
        days: int = 30,
        ticker: Optional[str] = None,
    ) -> AccuracySummary:
        """
        Compute rolling directional accuracy for the last N days.

        Returns:
            AccuracySummary with per-regime breakdown
        """
        rows = self.prediction_logger.get_recent(ticker=ticker, days=days)
        resolved_rows = [r for r in rows if r.directional_match is not None]

        matches = [r.directional_match for r in resolved_rows]
        errors  = [r.pct_error for r in resolved_rows]
        regimes = [r.market_regime for r in resolved_rows]

        summary = compute_accuracy(matches, errors, regimes)
        summary.ticker      = ticker or "ALL"
        summary.period_days = days
        logger.info(
            "accuracy_tracker.summary",
            ticker=summary.ticker,
            accuracy=summary.directional_accuracy,
            n=summary.n_resolved,
            below_threshold=summary.below_threshold,
        )
        return summary

    def run(self, as_of_date: Optional[datetime.date] = None) -> AccuracySummary:
        """
        Full accuracy cycle: resolve pending rows + compute rolling stats.
        Designed to be called daily by APScheduler at 18:30 IST.
        """
        as_of_date = as_of_date or datetime.date.today()
        self.resolve_pending(as_of_date)
        return self.compute_rolling_accuracy(days=30)
