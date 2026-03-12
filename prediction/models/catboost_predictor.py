"""
CatBoost Directional Classifier — Native Categorical Handler
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CatBoost advantage over XGBoost/LGBM:
  - Ordered target statistics prevent target leakage on categoricals
  - No need to one-hot encode sector, expiry_week, market_regime
  - Especially strong when sector rotation and calendar effects are key drivers

Categorical features handled natively (NO one-hot encoding):
  vix_regime (0-5), day_of_week (0-4), expiry_day (0/1),
  results_season (0/1), budget_week (0/1), month_end_flag (0/1)

Blueprint ref: Part 1, Layer 3, item 7 — CatBoost for India categoricals
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import structlog
from pathlib import Path
from typing import Optional

from catboost import CatBoostClassifier, Pool

from config.constants import XGBOOST_N_CLASSES, PREDICTION_CONFIDENCE_THRESHOLD
from features.india_feature_set import ALL_FEATURE_COLUMNS

logger = structlog.get_logger(__name__)

# ── Native categorical feature indices (positions in ALL_FEATURE_COLUMNS) ──
# CatBoost needs INTEGER indices into the feature matrix, NOT column names
CATBOOST_CATEGORICAL_FEATURES = [
    "vix_regime",
    "day_of_week",
    "expiry_day",
    "results_season",
    "budget_week",
    "month_end_flag",
]

DEFAULT_PARAMS = {
    "loss_function":         "MultiClass",
    "eval_metric":           "Accuracy",
    "classes_count":         XGBOOST_N_CLASSES,
    "iterations":            500,
    "depth":                 6,
    "learning_rate":         0.05,
    "l2_leaf_reg":           3.0,
    "bagging_temperature":   0.5,
    "random_strength":       1.0,
    "min_data_in_leaf":      20,
    "random_seed":           42,
    "thread_count":          -1,
    "verbose":               False,
    "allow_writing_files":   False,  # no temp files
    "task_type":             "CPU",  # switch to "GPU" if CUDA available
}


class CatBoostPredictor:
    """
    CatBoost 5-class directional classifier.
    Handles Indian sector/calendar/regime features without one-hot encoding.
    """

    def __init__(self, params: Optional[dict] = None, horizon: int = 5):
        self.params   = {**DEFAULT_PARAMS, **(params or {})}
        self.horizon  = horizon
        self.model: Optional[CatBoostClassifier] = None
        self._is_fitted = False
        self._cat_feature_indices: list[int] = []
        self._feature_names: list[str] = []

    def _get_cat_indices(self, columns: list[str]) -> list[int]:
        return [
            columns.index(c)
            for c in CATBOOST_CATEGORICAL_FEATURES
            if c in columns
        ]

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

        self._feature_names       = list(X_clean.columns)
        self._cat_feature_indices = self._get_cat_indices(self._feature_names)

        # Cast categorical columns to int (CatBoost requires this)
        for col in CATBOOST_CATEGORICAL_FEATURES:
            if col in X_clean.columns:
                X_clean[col] = X_clean[col].fillna(0).astype(int)

        train_pool = Pool(
            data=X_clean,
            label=y_clean.astype(int),
            cat_features=self._cat_feature_indices,
            feature_names=self._feature_names,
        )

        eval_pool = None
        if X_val is not None and y_val is not None:
            X_v = X_val[ALL_FEATURE_COLUMNS].copy()
            for col in CATBOOST_CATEGORICAL_FEATURES:
                if col in X_v.columns:
                    X_v[col] = X_v[col].fillna(0).astype(int)
            eval_pool = Pool(
                data=X_v.fillna(0),
                label=y_val.dropna().astype(int),
                cat_features=self._cat_feature_indices,
            )

        self.model = CatBoostClassifier(**self.params)
        self.model.fit(train_pool, eval_set=eval_pool, use_best_model=eval_pool is not None)
        self._is_fitted = True

        logger.info("catboost.fitted", n_samples=len(X_clean), horizon=self.horizon)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if not self._is_fitted:
            raise RuntimeError("Model not fitted.")
        X_clean = X[ALL_FEATURE_COLUMNS].copy()
        for col in CATBOOST_CATEGORICAL_FEATURES:
            if col in X_clean.columns:
                X_clean[col] = X_clean[col].fillna(0).astype(int)
        pool = Pool(
            data=X_clean.fillna(0),
            cat_features=self._cat_feature_indices,
        )
        return self.model.predict_proba(pool)

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
        importance = self.model.get_feature_importance(type="FeatureImportance")
        return (
            pd.Series(importance, index=self._feature_names)
            .sort_values(ascending=False)
            .head(top_n)
        )

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.model.save_model(str(path) + ".cbm")
        joblib.dump({
            "params":              self.params,
            "horizon":             self.horizon,
            "feature_names":       self._feature_names,
            "cat_feature_indices": self._cat_feature_indices,
        }, str(path) + ".meta")
        logger.info("catboost.saved", path=str(path))

    def load(self, path: Path) -> None:
        path = Path(path)
        meta = joblib.load(str(path) + ".meta")
        self.model = CatBoostClassifier()
        self.model.load_model(str(path) + ".cbm")
        self.params                = meta["params"]
        self.horizon               = meta["horizon"]
        self._feature_names        = meta["feature_names"]
        self._cat_feature_indices  = meta["cat_feature_indices"]
        self._is_fitted            = True
        logger.info("catboost.loaded", path=str(path))