"""
India Walk-Forward Validator
━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint spec (non-negotiable):
  Train window : 504 trading days  (2 years)
  Test window  : 63 trading days   (3 months)
  Embargo      : 5 trading days    (gap prevents leakage)
  Step         : 21 trading days   (rolls 1 month forward each fold)
  Min folds    : 8

Anti-lookahead assertion:
  max(train_indices) < min(test_indices) - EMBARGO   ← enforced per fold

Survivorship bias:
  Uses nifty_constituents.py historical membership lists.
  The 2018 Nifty 50 list ≠ 2026 Nifty 50 list.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass, field
from typing import Generator, Optional

from config.constants import (
    WFO_TRAIN_WINDOW_DAYS,
    WFO_TEST_WINDOW_DAYS,
    WFO_EMBARGO_DAYS,
    WFO_STEP_SIZE_DAYS,
    WFO_MIN_FOLDS,
    WFO_MIN_DIRECTIONAL_ACCURACY,
)

logger = structlog.get_logger(__name__)


@dataclass
class WFOFold:
    """Single walk-forward fold."""
    fold_id:          int
    train_start:      pd.Timestamp
    train_end:        pd.Timestamp
    embargo_end:      pd.Timestamp
    test_start:       pd.Timestamp
    test_end:         pd.Timestamp
    train_indices:    np.ndarray
    test_indices:     np.ndarray
    directional_accuracy: Optional[float] = None
    n_correct:        int = 0
    n_total:          int = 0


@dataclass
class WFOResult:
    """Aggregated results across all folds."""
    folds:              list[WFOFold] = field(default_factory=list)
    mean_accuracy:      float = 0.0
    std_accuracy:       float = 0.0
    min_accuracy:       float = 0.0
    passes_threshold:   bool  = False
    regime_accuracy:    dict[str, float] = field(default_factory=dict)

    @property
    def n_folds(self) -> int:
        return len(self.folds)


class IndiaWalkForwardValidator:
    """
    Walk-forward validator for India market ML models.

    Usage:
        wfv = IndiaWalkForwardValidator()
        for fold in wfv.generate_folds(feature_df):
            X_tr = feature_df.iloc[fold.train_indices]
            y_tr = labels.iloc[fold.train_indices]
            X_te = feature_df.iloc[fold.test_indices]
            y_te = labels.iloc[fold.test_indices]
            # train + evaluate
    """

    def __init__(
        self,
        train_days: int = WFO_TRAIN_WINDOW_DAYS,
        test_days:  int = WFO_TEST_WINDOW_DAYS,
        embargo:    int = WFO_EMBARGO_DAYS,
        step:       int = WFO_STEP_SIZE_DAYS,
        min_folds:  int = WFO_MIN_FOLDS,
    ):
        self.train_days = train_days
        self.test_days  = test_days
        self.embargo    = embargo
        self.step       = step
        self.min_folds  = min_folds

    def generate_folds(
        self,
        df: pd.DataFrame,
    ) -> Generator[WFOFold, None, None]:
        """
        Generate walk-forward folds from a time-indexed DataFrame.

        Args:
            df: Feature DataFrame with DatetimeIndex (trading days only).
                Must have >= train_days + embargo + test_days rows.

        Yields:
            WFOFold objects with train/test index arrays.

        Raises:
            ValueError: If anti-lookahead assertion fails.
        """
        n = len(df)
        required = self.train_days + self.embargo + self.test_days
        if n < required:
            raise ValueError(
                f"DataFrame too short: {n} rows, need >= {required} "
                f"(train={self.train_days} + embargo={self.embargo} + test={self.test_days})"
            )

        fold_id  = 0
        start    = 0

        while True:
            train_end_idx   = start + self.train_days
            embargo_end_idx = train_end_idx + self.embargo
            test_end_idx    = embargo_end_idx + self.test_days

            if test_end_idx > n:
                break

            train_idx   = np.arange(start, train_end_idx)
            test_idx    = np.arange(embargo_end_idx, test_end_idx)

            # ── CRITICAL: Anti-lookahead assertion ──────────────────────────
            assert max(train_idx) < min(test_idx) - 0, (
                f"Fold {fold_id}: lookahead detected! "
                f"max(train)={max(train_idx)} >= min(test)={min(test_idx)}"
            )
            assert min(test_idx) - max(train_idx) > self.embargo, (
                f"Fold {fold_id}: embargo gap insufficient. "
                f"Gap={min(test_idx) - max(train_idx)}, required>{self.embargo}"
            )

            train_dates = df.index[train_idx]
            test_dates  = df.index[test_idx]

            fold = WFOFold(
                fold_id=fold_id,
                train_start=train_dates[0],
                train_end=train_dates[-1],
                embargo_end=df.index[train_end_idx + self.embargo - 1],
                test_start=test_dates[0],
                test_end=test_dates[-1],
                train_indices=train_idx,
                test_indices=test_idx,
            )

            logger.debug(
                "wfo.fold_generated",
                fold_id=fold_id,
                train_start=str(fold.train_start.date()),
                train_end=str(fold.train_end.date()),
                test_start=str(fold.test_start.date()),
                test_end=str(fold.test_end.date()),
                embargo_days=self.embargo,
            )

            yield fold

            fold_id += 1
            start   += self.step

        if fold_id < self.min_folds:
            raise ValueError(
                f"Only {fold_id} folds generated; need >= {self.min_folds}. "
                "Extend the data range or reduce train/test window sizes."
            )

        logger.info("wfo.all_folds_generated", total_folds=fold_id)

    def validate_result(self, result: WFOResult) -> bool:
        """
        Check if walk-forward result meets blueprint accuracy threshold.
        Returns True if mean OOS accuracy >= 55%.
        """
        if result.mean_accuracy >= WFO_MIN_DIRECTIONAL_ACCURACY:
            logger.info(
                "wfo.validation_passed",
                mean_acc=round(result.mean_accuracy, 4),
                threshold=WFO_MIN_DIRECTIONAL_ACCURACY,
            )
            return True
        else:
            logger.warning(
                "wfo.validation_failed",
                mean_acc=round(result.mean_accuracy, 4),
                threshold=WFO_MIN_DIRECTIONAL_ACCURACY,
                action="trigger_retrain",
            )
            return False

    @staticmethod
    def compute_directional_accuracy(
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> float:
        """
        Compute directional accuracy (binary up/down, ignoring neutral).
        Neutral class (label=2) is excluded from accuracy calculation.

        Bullish (3,4) = UP; Bearish (0,1) = DOWN; Neutral (2) = excluded.
        """
        mask     = (y_true != 2) & (y_pred != 2)
        y_true_m = y_true[mask]
        y_pred_m = y_pred[mask]

        if len(y_true_m) == 0:
            return 0.5  # no non-neutral samples

        true_dir = (y_true_m >= 3).astype(int)
        pred_dir = (y_pred_m >= 3).astype(int)

        return float(np.mean(true_dir == pred_dir))