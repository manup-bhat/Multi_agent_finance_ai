"""
Anti-Lookahead Feature Validator
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint Validation Check #6 and #7:
  - max(train_indices) < min(test_indices) - EMBARGO  ← enforced per WFO fold
  - All features use .shift(1) — NO same-day data enters any model

Run this as a pre-training gate. If it fails, training must NOT proceed.
Used in: scripts/validate_anti_lookahead.py + tests/test_walk_forward.py

HARD RULE: This runs deterministic Python only. No model involvement.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass, field
from typing import Optional

from features.india_feature_set import ALL_FEATURE_COLUMNS
from config.constants import WFO_EMBARGO_DAYS

logger = structlog.get_logger(__name__)


@dataclass
class ValidationReport:
    """Result of the anti-lookahead validation."""
    passed:            bool = True
    n_features_checked: int = 0
    same_day_leaks:    list[str] = field(default_factory=list)
    wfo_violations:    list[str] = field(default_factory=list)
    null_columns:      list[str] = field(default_factory=list)
    warnings:          list[str] = field(default_factory=list)

    def summary(self) -> str:
        status = "✅ PASSED" if self.passed else "❌ FAILED"
        lines = [
            f"Anti-Lookahead Validation: {status}",
            f"  Features checked : {self.n_features_checked}",
            f"  Same-day leaks   : {len(self.same_day_leaks)} {self.same_day_leaks}",
            f"  WFO violations   : {len(self.wfo_violations)} {self.wfo_violations}",
            f"  Null columns     : {len(self.null_columns)} {self.null_columns}",
            f"  Warnings         : {len(self.warnings)}",
        ]
        for w in self.warnings:
            lines.append(f"    ⚠ {w}")
        return "\n".join(lines)


class FeatureValidator:
    """
    Validates that the 70-feature DataFrame has zero lookahead.

    Method:
      1. For each feature column, compute correlation between
         SAME-DAY raw close return and the feature value.
         Correlation > 0.8 flags potential same-day leakage.

      2. Verify that all feature columns are NaN on the FIRST row
         (shifted data should have NaN at position 0).

      3. Verify WFO fold indices: max(train) + embargo < min(test).

    This is a heuristic check. The ground truth is code review of
    IndiaFeatureSet._compute_*() methods — all must call .shift(1).
    """

    # Correlation threshold above which a feature is flagged as potentially leaky
    LEAK_CORRELATION_THRESHOLD = 0.80

    def validate_features(
        self,
        feature_df:   pd.DataFrame,
        close_series: pd.Series,
        check_top_n:  int = 70,
    ) -> ValidationReport:
        """
        Validate feature DataFrame for lookahead leakage.

        Args:
            feature_df:   Output of IndiaFeatureSet.build() — 70 columns
            close_series: Raw (unshifted) daily close prices (same index)
            check_top_n:  How many features to check (default: all 70)

        Returns:
            ValidationReport with pass/fail + details
        """
        report = ValidationReport()
        report.n_features_checked = min(check_top_n, len(feature_df.columns))

        # Compute same-day return (this should NOT correlate with lagged features)
        same_day_return = close_series.pct_change(1)

        cols_to_check = ALL_FEATURE_COLUMNS[:check_top_n]

        for col in cols_to_check:
            if col not in feature_df.columns:
                report.warnings.append(f"Column '{col}' missing from feature_df")
                continue

            series = feature_df[col]

            # ── Check 1: NaN at position 0 ────────────────────────────────────
            # All shifted features should be NaN at row 0 (no prior day to shift from)
            # Exception: calendar features (day_of_week etc.) — these are never shifted
            calendar_features = {
                "day_of_week", "expiry_day", "month_end_flag",
                "results_season", "budget_week", "rbi_event_flag",
            }
            if col not in calendar_features and not pd.isna(series.iloc[0]):
                report.warnings.append(
                    f"'{col}': row 0 is not NaN ({series.iloc[0]:.4f}) — "
                    "may not be properly shifted."
                )

            # ── Check 2: High correlation with same-day return ─────────────────
            # Align on common index, drop NaN
            aligned = pd.concat(
                [series, same_day_return], axis=1
            ).dropna()
            if len(aligned) < 50:
                continue

            try:
                corr = float(aligned.corr().iloc[0, 1])
                if abs(corr) > self.LEAK_CORRELATION_THRESHOLD:
                    report.same_day_leaks.append(
                        f"{col} (corr={corr:.3f})"
                    )
            except Exception:
                pass

            # ── Check 3: All-NaN column ────────────────────────────────────────
            if series.isna().all():
                report.null_columns.append(col)

        # ── Mark failure if any hard violations found ──────────────────────────
        if report.same_day_leaks or report.null_columns:
            report.passed = False

        logger.info(
            "feature_validator.result",
            passed=report.passed,
            same_day_leaks=len(report.same_day_leaks),
            null_columns=len(report.null_columns),
            warnings=len(report.warnings),
        )
        return report

    def validate_wfo_folds(
        self,
        train_indices: np.ndarray,
        test_indices:  np.ndarray,
        embargo:       int = WFO_EMBARGO_DAYS,
        fold_id:       int = 0,
    ) -> bool:
        """
        Validate a single WFO fold for embargo gap integrity.

        Returns True if valid, raises AssertionError if violated.
        """
        max_train = int(np.max(train_indices))
        min_test  = int(np.min(test_indices))
        gap       = min_test - max_train

        if gap <= embargo:
            msg = (
                f"Fold {fold_id}: WFO embargo violation! "
                f"Gap={gap} trading days, required > {embargo}. "
                f"max(train)={max_train}, min(test)={min_test}"
            )
            logger.error("feature_validator.wfo_violation", msg=msg)
            raise AssertionError(msg)

        logger.debug(
            "feature_validator.wfo_ok",
            fold_id=fold_id,
            gap=gap,
            embargo=embargo,
        )
        return True