"""
LightGBM Directional Classifier — Stacking Layer
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Same 5-class scheme as XGBoost. Used as stacking component
in the Ridge meta-learner ensemble.

LightGBM advantage: 2-10x faster training + native categorical via
is_categorical, but CatBoost (catboost_predictor.py) handles
Indian sector/expiry/regime better with ordered target statistics.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import structlog
from pathlib import Path
from typing import Optional

import lightgbm as lgb

from config.constants import XGBOOST_N_CLASSES, PREDICTION_CONFIDENCE_THRESHOLD
from features.india_feature_set import ALL_FEATURE_COLUMNS
from prediction.models.xgboost_predictor import RETURN_BINS, RETURN_LABELS

logger = structlog.get_logger(__name__)

# ── Categorical features for LightGBM ─────────────────────────────────────
# These are integer-encoded in IndiaFeatureSet before being passed to LGBM
LGBM_CATEGORICAL_COLS = [
    "vix_regime",     # 0-5 integer encoding
    "day_of_week",    # 0-4
    "expiry_day",     # 0/1
    "results_season", # 0/1
    "budget_week",    # 0/1
    "month_end_flag", # 0/1
]

DEFAULT_PARAMS = {
    "objective":        "multiclass",
    "num_class":        XGBOOST_N_CLASSES,
    "metric":           "multi_logloss",
    "n_estimators":     500,
    "max_depth":        7,
    "num_leaves":       63,
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.7,
    "min_child_samples": 20,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "random_state":     42,
    "n_jobs":           -1,
    "verbose":          -1,
    "importance_type":  "gain",
}


class LightGBMPredictor:
    """
    LightGBM 5-class directional classifier.
    Stacking layer alongside XGBoost and CatBoost.
    """

    def __init__(self, params: Optional[dict] = None, horizon: int = 5):
        self.params   = {**DEFAULT_PARAMS, **(params or {})}
        self.horizon  = horizon
        self.model: Optional[lgb.LGBMClassifier] = None
        self._is_fitted = False
        self._feature_names: list[str] = []

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> None:
        X_train = X_train[ALL_FEATURE_COLUMNS].copy()
        y_clean = y_train.dropna()
        X_clean = X_train.loc[y_clean.index].dropna()
        y_clean = y_clean.loc[X_clean.index]

        # Mark categorical features
        cat_cols = [c for c in LGBM_CATEGORICAL_COLS if c in X_clean.columns]

        self.model = lgb.LGBMClassifier(**self.params)
        self._feature_names = list(X_clean.columns)

        fit_kwargs: dict = {
            "X": X_clean,
            "y": y_clean.astype(int),
            "categorical_feature": cat_cols,
        }

        if X_val is not None and y_val is not None:
            X_v = X_val[ALL_FEATURE_COLUMNS].fillna(0)
            y_v = y_val.dropna().astype(int)
            fit_kwargs["eval_set"] = [(X_v, y_v)]
            fit_kwargs["callbacks"] = [lgb.early_stopping(50, verbose=False), lgb.log_evaluation(-1)]

        self.model.fit(**fit_kwargs)
        self._is_fitted = True

        logger.info("lightgbm.fitted", n_samples=len(X_clean), horizon=self.horizon)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Model not fitted.")
        X_clean = X[ALL_FEATURE_COLUMNS].fillna(0)
        return self.model.predict_proba(X_clean)

    def predict(self, X: pd.DataFrame) -> dict:
        proba = self.predict_proba(X.iloc[[-1]])[0]
        class_labels = ["Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"]
        pred_class   = int(np.argmax(proba))
        confidence   = float(proba[pred_class])
        return {
            "direction":       class_labels[pred_class],
            "direction_class": pred_class,
            "confidence":      round(confidence, 4),
            "class_probs":     {class_labels[i]: round(float(proba[i]), 4) for i in range(5)},
            "bullish_prob":    round(float(proba[3] + proba[4]), 4),
            "bearish_prob":    round(float(proba[0] + proba[1]), 4),
            "is_high_confidence": confidence >= PREDICTION_CONFIDENCE_THRESHOLD,
        }

    def get_feature_importance(self, top_n: int = 20) -> pd.Series:
        if not self._is_fitted:
            raise RuntimeError("Model not fitted.")
        return (
            pd.Series(self.model.feature_importances_, index=self._feature_names)
            .sort_values(ascending=False)
            .head(top_n)
        )

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model":     self.model,
            "params":    self.params,
            "horizon":   self.horizon,
            "feature_names": self._feature_names,
        }, path)
        logger.info("lightgbm.saved", path=str(path))

    def load(self, path: Path) -> None:
        data = joblib.load(Path(path))
        self.model          = data["model"]
        self.params         = data["params"]
        self.horizon        = data["horizon"]
        self._feature_names = data["feature_names"]
        self._is_fitted     = True
        logger.info("lightgbm.loaded", path=str(path))