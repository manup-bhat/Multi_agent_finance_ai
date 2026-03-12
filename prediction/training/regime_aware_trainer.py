"""
Regime-Aware Trainer
━━━━━━━━━━━━━━━━━━━
Trains SEPARATE model weights per HMM regime (Bull/Sideways/Bear).
This is the advanced path — use after standard trainer.py works.

Blueprint: "Separate model weights per HMM regime" → regime_aware_trainer.py

Key insight: A model tuned on Bull markets underperforms in Bear markets.
Separate regime models + HMM gating gives 3-5% accuracy uplift in backtests.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import structlog
from pathlib import Path
from typing import Optional

from prediction.models.xgboost_predictor import XGBoostPredictor
from prediction.models.lightgbm_predictor import LightGBMPredictor
from prediction.models.catboost_predictor import CatBoostPredictor
from prediction.models.hmm_regime import HMMRegimeDetector, REGIME_NAMES
from prediction.training.india_walk_forward import IndiaWalkForwardValidator

logger = structlog.get_logger(__name__)

# Minimum samples required per regime to train a separate model
MIN_REGIME_SAMPLES = 100


class RegimeAwareTrainer:
    """
    Trains regime-specific model sets.
    Falls back to pooled model if a regime has < MIN_REGIME_SAMPLES rows.
    """

    def __init__(self, ticker: str, horizon: int = 5):
        self.ticker  = ticker
        self.horizon = horizon

        # 3 sets: {0: Bear, 1: Sideways, 2: Bull}
        self.regime_xgb:  dict[int, XGBoostPredictor]  = {}
        self.regime_lgbm: dict[int, LightGBMPredictor] = {}
        self.regime_cb:   dict[int, CatBoostPredictor] = {}
        self._is_fitted = False

    def fit(
        self,
        feature_df:    pd.DataFrame,
        labels:        pd.Series,
        regime_series: pd.Series,   # output of HMMRegimeDetector.predict_series()
        pooled_xgb:    XGBoostPredictor,   # fallback for sparse regimes
        pooled_lgbm:   LightGBMPredictor,
        pooled_cb:     CatBoostPredictor,
    ) -> None:
        """
        Train one model set per regime.

        Args:
            feature_df:    Full 70-feature DataFrame
            labels:        5-class directional labels
            regime_series: Integer regime labels (0/1/2) aligned with feature_df
            pooled_*:      Already-trained pooled models (used as fallback)
        """
        wfv = IndiaWalkForwardValidator()

        for regime_id in [0, 1, 2]:
            regime_name = REGIME_NAMES[regime_id]
            regime_mask = regime_series == regime_id
            regime_df   = feature_df.loc[regime_mask]
            regime_lbl  = labels.loc[regime_mask]

            n_samples = regime_mask.sum()
            logger.info(
                "regime_trainer.regime_data",
                regime=regime_name,
                n_samples=int(n_samples),
            )

            if n_samples < MIN_REGIME_SAMPLES:
                logger.warning(
                    "regime_trainer.insufficient_samples",
                    regime=regime_name,
                    n_samples=int(n_samples),
                    action="using_pooled_fallback",
                )
                self.regime_xgb[regime_id]  = pooled_xgb
                self.regime_lgbm[regime_id] = pooled_lgbm
                self.regime_cb[regime_id]   = pooled_cb
                continue

            # Split: 80% train, 20% val within this regime
            split_idx = int(len(regime_df) * 0.8)
            X_tr = regime_df.iloc[:split_idx]
            y_tr = regime_lbl.iloc[:split_idx]
            X_vl = regime_df.iloc[split_idx:]
            y_vl = regime_lbl.iloc[split_idx:]

            # XGBoost
            xgb = XGBoostPredictor(horizon=self.horizon)
            xgb.fit(X_tr, y_tr, X_vl, y_vl)
            self.regime_xgb[regime_id] = xgb

            # LightGBM
            lgbm = LightGBMPredictor(horizon=self.horizon)
            lgbm.fit(X_tr, y_tr, X_vl, y_vl)
            self.regime_lgbm[regime_id] = lgbm

            # CatBoost
            cb = CatBoostPredictor(horizon=self.horizon)
            cb.fit(X_tr, y_tr, X_vl, y_vl)
            self.regime_cb[regime_id] = cb

            logger.info(
                "regime_trainer.regime_fitted",
                regime=regime_name,
                n_train=split_idx,
            )

        self._is_fitted = True
        logger.info("regime_trainer.all_regimes_fitted")

    def get_models_for_regime(
        self, regime_id: int
    ) -> tuple[XGBoostPredictor, LightGBMPredictor, CatBoostPredictor]:
        """Return the correct model set for the current market regime."""
        if not self._is_fitted:
            raise RuntimeError("RegimeAwareTrainer not fitted.")
        return (
            self.regime_xgb[regime_id],
            self.regime_lgbm[regime_id],
            self.regime_cb[regime_id],
        )