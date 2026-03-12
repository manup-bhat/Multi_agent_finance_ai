"""
Ridge Meta-Learner Ensemble Predictor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Combines outputs from:
  1. XGBoost  (5-class proba → 5 features)
  2. LightGBM (5-class proba → 5 features)
  3. CatBoost (5-class proba → 5 features)
  4. HMM regime (one-hot 3 features)
  5. Chronos-2 direction_prob_up_{5,10,30}d (3 features)
= 21 meta-features → Ridge meta-learner

Blueprint hard rule: Ridge Regression ONLY. Never neural meta-learner.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import structlog
from pathlib import Path
from typing import Optional

from sklearn.linear_model import RidgeClassifier
from sklearn.preprocessing import StandardScaler

from config.constants import (
    XGBOOST_N_CLASSES,
    PREDICTION_CONFIDENCE_THRESHOLD,
)

logger = structlog.get_logger(__name__)

CLASS_LABELS = ["Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"]
REGIME_NAMES = {0: "Bear", 1: "Sideways", 2: "Bull"}

# Regime-specific base-model weights (applied when meta-learner not fitted)
REGIME_WEIGHTS: dict[int, dict[str, float]] = {
    2: {"xgboost": 0.35, "lightgbm": 0.30, "catboost": 0.35},  # Bull
    0: {"xgboost": 0.30, "lightgbm": 0.30, "catboost": 0.40},  # Bear
    1: {"xgboost": 0.33, "lightgbm": 0.34, "catboost": 0.33},  # Sideways
}


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - np.max(x))
    return e / e.sum()


class EnsemblePredictor:
    """
    Ridge meta-learner stacking XGBoost + LightGBM + CatBoost + HMM + Chronos.
    Regime-aware: different weights per market state.
    """

    def __init__(self, ridge_alpha: float = 1.0):
        self.ridge_alpha = ridge_alpha
        self._meta_model: Optional[RidgeClassifier] = None
        self._scaler = StandardScaler()
        self._is_fitted = False

    def _build_meta_features(
        self,
        xgb_proba:       np.ndarray,   # (n, 5)
        lgbm_proba:      np.ndarray,   # (n, 5)
        catboost_proba:  np.ndarray,   # (n, 5)
        regime_ids:      np.ndarray,   # (n,) int
        chronos_dir_5d:  np.ndarray,   # (n,) float
        chronos_dir_10d: np.ndarray,   # (n,) float
        chronos_dir_30d: np.ndarray,   # (n,) float
    ) -> np.ndarray:
        """Build 21-feature meta-matrix: 5+5+5+3+3 = 21."""
        regime_ohe = np.zeros((len(regime_ids), 3), dtype=np.float32)
        for i, r in enumerate(regime_ids):
            if 0 <= int(r) <= 2:
                regime_ohe[i, int(r)] = 1.0

        meta = np.hstack([
            xgb_proba.reshape(-1, 5),
            lgbm_proba.reshape(-1, 5),
            catboost_proba.reshape(-1, 5),
            regime_ohe,
            chronos_dir_5d.reshape(-1, 1),
            chronos_dir_10d.reshape(-1, 1),
            chronos_dir_30d.reshape(-1, 1),
        ])
        return meta.astype(np.float32)

    def fit(
        self,
        xgb_proba:       np.ndarray,
        lgbm_proba:      np.ndarray,
        catboost_proba:  np.ndarray,
        regime_ids:      np.ndarray,
        chronos_dir_5d:  np.ndarray,
        chronos_dir_10d: np.ndarray,
        chronos_dir_30d: np.ndarray,
        y_labels:        np.ndarray,
    ) -> None:
        """
        Fit Ridge meta-learner on OUT-OF-FOLD (validation) predictions only.
        NEVER fit on the same data as base models.
        """
        meta = self._build_meta_features(
            xgb_proba, lgbm_proba, catboost_proba,
            regime_ids, chronos_dir_5d, chronos_dir_10d, chronos_dir_30d,
        )
        meta_scaled = self._scaler.fit_transform(meta)

        self._meta_model = RidgeClassifier(
            alpha=self.ridge_alpha,
            class_weight="balanced",
            random_state=42,
        )
        self._meta_model.fit(meta_scaled, y_labels.astype(int))
        self._is_fitted = True

        logger.info(
            "ensemble.meta_fitted",
            n_samples=len(y_labels),
            meta_features=meta.shape[1],
            alpha=self.ridge_alpha,
        )

    def predict(
        self,
        xgb_proba:       np.ndarray,   # shape (5,)
        lgbm_proba:      np.ndarray,   # shape (5,)
        catboost_proba:  np.ndarray,   # shape (5,)
        regime_id:       int,
        chronos_dir_5d:  float,
        chronos_dir_10d: float,
        chronos_dir_30d: float,
    ) -> dict:
        """
        Produce final ensemble prediction for one sample.

        Returns:
            {
              "direction":          str
              "direction_class":    int [0-4]
              "confidence":         float
              "class_probs":        dict
              "bullish_prob":       float
              "bearish_prob":       float
              "regime_name":        str
              "model_weights_used": dict
              "chronos_dir_5d":     float
              "chronos_dir_10d":    float
              "chronos_dir_30d":    float
              "is_high_confidence": bool
            }
        """
        w = REGIME_WEIGHTS.get(regime_id, REGIME_WEIGHTS[1])

        # Regime-weighted base average (always computed as fallback)
        weighted_proba = (
            w["xgboost"]  * xgb_proba
            + w["lightgbm"] * lgbm_proba
            + w["catboost"] * catboost_proba
        )

        if self._is_fitted:
            meta = self._build_meta_features(
                xgb_proba.reshape(1, -1),
                lgbm_proba.reshape(1, -1),
                catboost_proba.reshape(1, -1),
                np.array([regime_id]),
                np.array([chronos_dir_5d]),
                np.array([chronos_dir_10d]),
                np.array([chronos_dir_30d]),
            )
            meta_scaled = self._scaler.transform(meta)
            pred_class  = int(self._meta_model.predict(meta_scaled)[0])
            # RidgeClassifier → decision_function → softmax for confidence
            scores     = self._meta_model.decision_function(meta_scaled)[0]
            probs      = _softmax(scores)
            confidence = float(probs[pred_class])
        else:
            probs      = weighted_proba.flatten()
            pred_class = int(np.argmax(probs))
            confidence = float(probs[pred_class])

        # Chronos divergence warning
        chronos_avg = (
            chronos_dir_5d
            + chronos_dir_10d * 0.8
            + chronos_dir_30d * 0.6
        ) / 2.4

        if pred_class >= 3 and chronos_avg < 0.35:
            logger.warning(
                "ensemble.chronos_bearish_divergence",
                ensemble_class=CLASS_LABELS[pred_class],
                chronos_avg_prob=round(chronos_avg, 3),
            )
        elif pred_class <= 1 and chronos_avg > 0.65:
            logger.warning(
                "ensemble.chronos_bullish_divergence",
                ensemble_class=CLASS_LABELS[pred_class],
                chronos_avg_prob=round(chronos_avg, 3),
            )

        return {
            "direction":          CLASS_LABELS[pred_class],
            "direction_class":    pred_class,
            "confidence":         round(confidence, 4),
            "class_probs":        {CLASS_LABELS[i]: round(float(probs[i]), 4) for i in range(5)},
            "bullish_prob":       round(float(probs[3] + probs[4]), 4),
            "bearish_prob":       round(float(probs[0] + probs[1]), 4),
            "regime_name":        REGIME_NAMES.get(regime_id, "Unknown"),
            "model_weights_used": w,
            "chronos_dir_5d":     round(chronos_dir_5d, 4),
            "chronos_dir_10d":    round(chronos_dir_10d, 4),
            "chronos_dir_30d":    round(chronos_dir_30d, 4),
            "is_high_confidence": confidence >= PREDICTION_CONFIDENCE_THRESHOLD,
        }

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "meta_model":  self._meta_model,
            "scaler":      self._scaler,
            "ridge_alpha": self.ridge_alpha,
            "is_fitted":   self._is_fitted,
        }, path)
        logger.info("ensemble.saved", path=str(path))

    def load(self, path: Path) -> None:
        data = joblib.load(Path(path))
        self._meta_model = data["meta_model"]
        self._scaler     = data["scaler"]
        self.ridge_alpha = data["ridge_alpha"]
        self._is_fitted  = data["is_fitted"]
        logger.info("ensemble.loaded", path=str(path))