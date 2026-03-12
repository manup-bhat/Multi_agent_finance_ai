"""
XGBoost Directional Classifier
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
5-class directional prediction:
  0 = Very Bearish  (< -2%)
  1 = Bearish       (-2% to -0.5%)
  2 = Neutral       (-0.5% to +0.5%)
  3 = Bullish       (+0.5% to +2%)
  4 = Very Bullish  (> +2%)

Uses 70 India features from IndiaFeatureSet.
CatBoost handles sector/expiry/regime categoricals natively (see catboost_predictor.py).
XGBoost: treats everything as float — all features pre-encoded.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import structlog
from pathlib import Path
from typing import Optional

import xgboost as xgb

from config.constants import (
    XGBOOST_N_CLASSES,
    PREDICTION_CONFIDENCE_THRESHOLD,
)
from features.india_feature_set import ALL_FEATURE_COLUMNS

logger = structlog.get_logger(__name__)

# ── Label thresholds (5-class) ─────────────────────────────────────────────
RETURN_BINS   = [-np.inf, -0.02, -0.005, 0.005, 0.02, np.inf]
RETURN_LABELS = [0, 1, 2, 3, 4]

# ── Default hyperparameters (Optuna-tuned reference values) ───────────────
DEFAULT_PARAMS = {
    "objective":        "multi:softprob",
    "num_class":        XGBOOST_N_CLASSES,
    "eval_metric":      "mlogloss",
    "n_estimators":     500,
    "max_depth":        6,
    "learning_rate":    0.05,
    "subsample":        0.8,
    "colsample_bytree": 0.7,
    "min_child_weight": 5,
    "gamma":            0.1,
    "reg_alpha":        0.1,
    "reg_lambda":       1.0,
    "tree_method":      "hist",   # fast histogram method
    "random_state":     42,
    "n_jobs":           -1,
    "verbosity":        0,
}


class XGBoostPredictor:
    """
    XGBoost 5-class directional classifier.
    Always trained with walk-forward validation (see india_walk_forward.py).
    """

    def __init__(self, params: Optional[dict] = None, horizon: int = 5):
        """
        Args:
            params:  XGBoost hyperparams (None = use DEFAULT_PARAMS)
            horizon: Prediction horizon in days (affects label construction)
        """
        self.params  = {**DEFAULT_PARAMS, **(params or {})}
        self.horizon = horizon
        self.model: Optional[xgb.XGBClassifier] = None
        self._feature_names: list[str] = []
        self._is_fitted = False

    @staticmethod
    def make_labels(close_series: pd.Series, horizon: int = 5) -> pd.Series:
        """
        Create 5-class directional labels from forward N-day log returns.

        CRITICAL: forward returns are what we're predicting — no shift here.
        The shift(1) is already applied to all FEATURES in IndiaFeatureSet.build().
        Labels are aligned with the ROW that contains the feature information.

        Args:
            close_series: Daily close price (already loaded, unshifted)
            horizon:      Days ahead for return calculation

        Returns:
            Series of integer labels [0-4], NaN for last `horizon` rows
        """
        fwd_return = np.log(
            close_series.shift(-horizon) / close_series
        )
        labels = pd.cut(
            fwd_return,
            bins=RETURN_BINS,
            labels=RETURN_LABELS,
        ).astype(float)
        return labels

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: Optional[pd.DataFrame] = None,
        y_val: Optional[pd.Series] = None,
    ) -> None:
        """
        Train XGBoost classifier.

        Args:
            X_train: Feature matrix (70 columns from IndiaFeatureSet)
            y_train: Integer labels [0-4]
            X_val:   Validation set (optional; enables early stopping)
            y_val:   Validation labels
        """
        X_train = X_train[ALL_FEATURE_COLUMNS].copy()
        y_clean = y_train.dropna()
        X_clean = X_train.loc[y_clean.index].dropna()
        y_clean = y_clean.loc[X_clean.index]

        if len(X_clean) < 100:
            raise ValueError(
                f"Too few training samples: {len(X_clean)}. Need >= 100."
            )

        self.model = xgb.XGBClassifier(**self.params)
        self._feature_names = list(X_clean.columns)

        fit_kwargs: dict = {"X": X_clean, "y": y_clean.astype(int)}

        if X_val is not None and y_val is not None:
            X_val_clean = X_val[ALL_FEATURE_COLUMNS].fillna(0)
            y_val_clean = y_val.dropna().astype(int)
            fit_kwargs["eval_set"] = [(X_val_clean, y_val_clean)]
            fit_kwargs["verbose"] = False

        self.model.fit(**fit_kwargs)
        self._is_fitted = True

        logger.info(
            "xgboost.fitted",
            n_samples=len(X_clean),
            horizon=self.horizon,
            n_estimators=self.model.best_iteration if hasattr(self.model, "best_iteration") else self.params["n_estimators"],
        )

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """
        Return class probability array shape (n_samples, 5).
        Column i = P(label == i).
        """
        if not self._is_fitted or self.model is None:
            raise RuntimeError("Model not fitted. Call fit() first.")

        X_clean = X[ALL_FEATURE_COLUMNS].fillna(0)
        return self.model.predict_proba(X_clean)

    def predict(self, X: pd.DataFrame) -> dict:
        """
        Return structured prediction dict for a single row.

        Returns:
            {
              "direction": "Very Bullish" | "Bullish" | "Neutral" | "Bearish" | "Very Bearish",
              "direction_class": int [0-4],
              "confidence": float [0-1],
              "class_probs": dict {class_label: probability},
              "bullish_prob": float (P(class >= 3)),
              "bearish_prob": float (P(class <= 1)),
            }
        """
        proba = self.predict_proba(X.iloc[[-1]])  # last row
        probs = proba[0]  # shape (5,)

        class_labels = ["Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"]
        pred_class   = int(np.argmax(probs))
        confidence   = float(probs[pred_class])

        return {
            "direction":       class_labels[pred_class],
            "direction_class": pred_class,
            "confidence":      round(confidence, 4),
            "class_probs":     {class_labels[i]: round(float(probs[i]), 4) for i in range(5)},
            "bullish_prob":    round(float(probs[3] + probs[4]), 4),
            "bearish_prob":    round(float(probs[0] + probs[1]), 4),
            "is_high_confidence": confidence >= PREDICTION_CONFIDENCE_THRESHOLD,
        }

    def get_feature_importance(self, top_n: int = 20) -> pd.Series:
        """Return top-N feature importances by XGBoost gain."""
        if not self._is_fitted:
            raise RuntimeError("Model not fitted.")
        importance = self.model.feature_importances_
        return (
            pd.Series(importance, index=self._feature_names)
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
        logger.info("xgboost.saved", path=str(path))

    def load(self, path: Path) -> None:
        data = joblib.load(Path(path))
        self.model          = data["model"]
        self.params         = data["params"]
        self.horizon        = data["horizon"]
        self._feature_names = data["feature_names"]
        self._is_fitted     = True
        logger.info("xgboost.loaded", path=str(path))