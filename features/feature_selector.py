"""
SHAP-Based Feature Selector
━━━━━━━━━━━━━━━━━━━━━━━━━━
Removes low-importance or leaky features from the 70-feature set.
Runs AFTER walk-forward training. Blueprint: features/feature_selector.py

NEVER run before training — SHAP values require a fitted model.
NEVER remove India-specific features (FII/DII, VIX, PCR) without checking
  OOS accuracy drop > 1% — these have high economic signal despite
  sometimes low SHAP on individual folds.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
import structlog
from pathlib import Path
from typing import Optional

from features.india_feature_set import ALL_FEATURE_COLUMNS
from prediction.models.xgboost_predictor import XGBoostPredictor

logger = structlog.get_logger(__name__)

# India-specific features that must NEVER be removed regardless of SHAP
PROTECTED_INDIA_FEATURES = {
    "fii_net_cr", "fii_zscore_5d", "fii_streak", "fii_dii_consensus",
    "india_vix", "vix_regime", "pcr", "pcr_zscore",
    "oi_change_pct", "max_pain_distance", "expiry_day",
    "rbi_event_flag", "results_season",
}


class SHAPFeatureSelector:
    """
    Computes SHAP importances and removes features below a threshold.
    Protects India-specific high-alpha signals from removal.
    """

    def __init__(
        self,
        importance_threshold: float = 0.001,  # remove features with mean |SHAP| < this
        max_features:         int   = 60,      # never go below 60 features
    ):
        self.importance_threshold = importance_threshold
        self.max_features         = max_features
        self._shap_importances: Optional[pd.Series] = None
        self._selected_features: list[str] = ALL_FEATURE_COLUMNS.copy()

    def fit(
        self,
        model:   XGBoostPredictor,
        X_val:   pd.DataFrame,
    ) -> "SHAPFeatureSelector":
        """
        Compute SHAP feature importances on validation data.

        Args:
            model:  Fitted XGBoostPredictor (uses its internal XGBClassifier)
            X_val:  Validation feature DataFrame (from OOF fold, never train data)
        """
        X_clean = X_val[ALL_FEATURE_COLUMNS].fillna(0)
        explainer   = shap.TreeExplainer(model.model)
        shap_values = explainer.shap_values(X_clean)

        # shap_values: list of (n, 70) arrays — one per class
        # Mean absolute SHAP across classes and samples
        mean_shap = np.mean(
            [np.abs(sv).mean(axis=0) for sv in shap_values],
            axis=0,
        )
        self._shap_importances = pd.Series(
            mean_shap, index=ALL_FEATURE_COLUMNS
        ).sort_values(ascending=False)

        logger.info(
            "feature_selector.shap_computed",
            n_features=len(self._shap_importances),
            top_feature=self._shap_importances.index[0],
            top_importance=round(float(self._shap_importances.iloc[0]), 6),
        )
        return self

    def select(self) -> list[str]:
        """
        Return the selected feature list after removing low-importance features.
        Protected India features are always retained.

        Returns:
            Ordered list of selected feature names (subset of ALL_FEATURE_COLUMNS)
        """
        if self._shap_importances is None:
            raise RuntimeError("Call fit() before select()")

        # Features below threshold (candidates for removal)
        below = self._shap_importances[
            self._shap_importances < self.importance_threshold
        ].index.tolist()

        # Never remove protected India features
        to_remove = [f for f in below if f not in PROTECTED_INDIA_FEATURES]

        # Enforce minimum feature count
        n_removable = len(ALL_FEATURE_COLUMNS) - self.max_features
        to_remove   = to_remove[:n_removable]

        self._selected_features = [
            f for f in ALL_FEATURE_COLUMNS if f not in to_remove
        ]

        logger.info(
            "feature_selector.selected",
            total_original=len(ALL_FEATURE_COLUMNS),
            n_removed=len(to_remove),
            n_selected=len(self._selected_features),
            removed_features=to_remove,
        )
        return self._selected_features

    @property
    def importances(self) -> pd.Series:
        if self._shap_importances is None:
            raise RuntimeError("Call fit() first")
        return self._shap_importances

    def top_n(self, n: int = 20) -> pd.Series:
        """Return top-N most important features."""
        return self.importances.head(n)