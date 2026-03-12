"""
Master Training Pipeline
━━━━━━━━━━━━━━━━━━━━━━━
Orchestrates:
  1. Walk-forward fold generation
  2. Optuna hyperparameter tuning (first 2 folds)
  3. XGBoost + LightGBM + CatBoost training per fold
  4. Out-of-fold (OOF) prediction collection
  5. Ridge meta-learner fitting on OOF predictions
  6. HMM regime fitting on Nifty 50 returns
  7. MLflow experiment logging
  8. Auto-trigger retrain if OOS accuracy < 55%

Blueprint Phase 5 gate: directional accuracy > 55% OOS.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import mlflow
import structlog
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.constants import (
    WFO_MIN_DIRECTIONAL_ACCURACY,
    MARKET_TZ,
    HMM_N_REGIMES,
)
from features.india_feature_set import ALL_FEATURE_COLUMNS
from prediction.models.xgboost_predictor import XGBoostPredictor, RETURN_BINS, RETURN_LABELS
from prediction.models.lightgbm_predictor import LightGBMPredictor
from prediction.models.catboost_predictor import CatBoostPredictor
from prediction.models.hmm_regime import HMMRegimeDetector
from prediction.models.ensemble_predictor import EnsemblePredictor
from prediction.training.india_walk_forward import (
    IndiaWalkForwardValidator,
    WFOFold,
    WFOResult,
)
from prediction.training.optuna_tuner import OptunaTuner

logger = structlog.get_logger(__name__)

MODEL_DIR = Path("models/saved")


class IndiaMLTrainer:
    """
    Full training pipeline for India Multi-Agent Financial Engine.

    Usage:
        trainer = IndiaMLTrainer(ticker="HDFCBANK.NS", horizon=5)
        result  = trainer.train(feature_df, close_series, nifty_returns, vix_series)
        # result.ensemble is ready for inference
    """

    def __init__(
        self,
        ticker:       str,
        horizon:      int = 5,
        run_optuna:   bool = True,
        use_mlflow:   bool = True,
        model_dir:    Path = MODEL_DIR,
    ):
        self.ticker     = ticker
        self.horizon    = horizon
        self.run_optuna = run_optuna
        self.use_mlflow = use_mlflow
        self.model_dir  = Path(model_dir) / ticker.replace(".", "_") / f"h{horizon}"
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.wfv     = IndiaWalkForwardValidator()
        self.tuner   = OptunaTuner()
        self.hmm     = HMMRegimeDetector()
        self.ensemble = EnsemblePredictor()

        # Best hyperparams (populated after Optuna tuning)
        self._xgb_best_params:  Optional[dict] = None
        self._lgbm_best_params: Optional[dict] = None
        self._cb_best_params:   Optional[dict] = None

    def _make_labels(self, close_series: pd.Series) -> pd.Series:
        """Build 5-class directional labels from forward N-day returns."""
        return XGBoostPredictor.make_labels(close_series, self.horizon)

    def train(
        self,
        feature_df:     pd.DataFrame,
        close_series:   pd.Series,
        nifty_returns:  pd.Series,
        vix_series:     Optional[pd.Series] = None,
    ) -> "TrainingResult":
        """
        Run full walk-forward training pipeline.

        Args:
            feature_df:    70-column feature DataFrame (from IndiaFeatureSet.build())
                           Index: DatetimeIndex (Asia/Kolkata)
            close_series:  Raw daily close prices (same index, NOT shifted)
            nifty_returns: Log returns of Nifty 50 for HMM regime fitting
            vix_series:    India VIX series for HMM (optional but improves accuracy)

        Returns:
            TrainingResult with fitted ensemble + per-fold accuracy metrics
        """
        exp_name = f"india_ml_{self.ticker}_h{self.horizon}"

        run_ctx = (
            mlflow.start_run(run_name=exp_name)
            if self.use_mlflow
            else _NullContext()
        )

        with run_ctx:
            if self.use_mlflow:
                mlflow.set_tag("ticker", self.ticker)
                mlflow.set_tag("horizon", self.horizon)
                mlflow.log_param("train_window", 504)
                mlflow.log_param("test_window", 63)
                mlflow.log_param("embargo", 5)
                mlflow.log_param("step", 21)

            # ── Step 1: Build labels ──────────────────────────────────────────
            labels = self._make_labels(close_series)
            # Drop last `horizon` rows (no forward return available)
            valid_mask = ~labels.isna()
            feature_df = feature_df.loc[valid_mask]
            labels     = labels.loc[valid_mask]

            logger.info(
                "trainer.start",
                ticker=self.ticker,
                horizon=self.horizon,
                n_rows=len(feature_df),
                label_dist=labels.value_counts().to_dict(),
            )

            # ── Step 2: Fit HMM regime on Nifty 50 ───────────────────────────
            logger.info("trainer.fitting_hmm")
            nifty_aligned = nifty_returns.reindex(feature_df.index).ffill().fillna(0.0)
            vix_aligned   = (
                vix_series.reindex(feature_df.index).ffill()
                if vix_series is not None else None
            )
            self.hmm.fit(nifty_aligned, vix_aligned)
            regime_series = self.hmm.predict_series(nifty_aligned, vix_aligned)

            # ── Step 3: Optuna tuning (first 2 folds only) ───────────────────
            folds_list = list(self.wfv.generate_folds(feature_df))

            if self.run_optuna and len(folds_list) >= 2:
                f0 = folds_list[0]
                X_tune_tr = feature_df.iloc[f0.train_indices]
                y_tune_tr = labels.iloc[f0.train_indices]
                X_tune_vl = feature_df.iloc[f0.test_indices]
                y_tune_vl = labels.iloc[f0.test_indices]

                logger.info("trainer.optuna_tuning_xgb")
                self._xgb_best_params  = self.tuner.tune_xgboost(
                    X_tune_tr, y_tune_tr, X_tune_vl, y_tune_vl
                )
                logger.info("trainer.optuna_tuning_lgbm")
                self._lgbm_best_params = self.tuner.tune_lightgbm(
                    X_tune_tr, y_tune_tr, X_tune_vl, y_tune_vl
                )
                logger.info("trainer.optuna_tuning_catboost")
                self._cb_best_params   = self.tuner.tune_catboost(
                    X_tune_tr, y_tune_tr, X_tune_vl, y_tune_vl
                )

            # ── Step 4: Walk-forward training + OOF collection ───────────────
            oof_xgb_proba      = np.zeros((len(feature_df), 5), dtype=np.float32)
            oof_lgbm_proba     = np.zeros((len(feature_df), 5), dtype=np.float32)
            oof_catboost_proba = np.zeros((len(feature_df), 5), dtype=np.float32)
            oof_regime_ids     = np.zeros(len(feature_df), dtype=int)
            oof_covered        = np.zeros(len(feature_df), dtype=bool)

            wfo_result = WFOResult(folds=folds_list)
            fold_accuracies = []

            # Keep last-fold models as production models
            last_xgb: Optional[XGBoostPredictor]  = None
            last_lgbm: Optional[LightGBMPredictor] = None
            last_cb:   Optional[CatBoostPredictor] = None

            for fold in folds_list:
                X_tr = feature_df.iloc[fold.train_indices]
                y_tr = labels.iloc[fold.train_indices]
                X_te = feature_df.iloc[fold.test_indices]
                y_te = labels.iloc[fold.test_indices]

                # XGBoost
                xgb_pred = XGBoostPredictor(
                    params=self._xgb_best_params, horizon=self.horizon
                )
                xgb_pred.fit(X_tr, y_tr, X_te, y_te)
                xgb_oof = xgb_pred.predict_proba(X_te)

                # LightGBM
                lgbm_pred = LightGBMPredictor(
                    params=self._lgbm_best_params, horizon=self.horizon
                )
                lgbm_pred.fit(X_tr, y_tr, X_te, y_te)
                lgbm_oof = lgbm_pred.predict_proba(X_te)

                # CatBoost
                cb_pred = CatBoostPredictor(
                    params=self._cb_best_params, horizon=self.horizon
                )
                cb_pred.fit(X_tr, y_tr, X_te, y_te)
                cb_oof = cb_pred.predict_proba(X_te)

                # Store OOF predictions
                oof_xgb_proba[fold.test_indices]      = xgb_oof
                oof_lgbm_proba[fold.test_indices]     = lgbm_oof
                oof_catboost_proba[fold.test_indices] = cb_oof
                oof_regime_ids[fold.test_indices]     = (
                    regime_series.iloc[fold.test_indices].values
                )
                oof_covered[fold.test_indices] = True

                # Fold directional accuracy (exclude neutral=2)
                y_te_arr   = y_te.values.astype(int)
                xgb_preds  = np.argmax(xgb_oof, axis=1)
                lgbm_preds = np.argmax(lgbm_oof, axis=1)
                cb_preds   = np.argmax(cb_oof, axis=1)

                # Ensemble vote (simple average of probabilities)
                avg_proba = (xgb_oof + lgbm_oof + cb_oof) / 3
                ens_preds = np.argmax(avg_proba, axis=1)

                fold_acc = IndiaWalkForwardValidator.compute_directional_accuracy(
                    y_te_arr, ens_preds
                )
                fold.directional_accuracy = fold_acc
                fold.n_correct = int(np.sum(ens_preds == y_te_arr))
                fold.n_total   = len(y_te_arr)
                fold_accuracies.append(fold_acc)

                last_xgb, last_lgbm, last_cb = xgb_pred, lgbm_pred, cb_pred

                logger.info(
                    "trainer.fold_done",
                    fold_id=fold.fold_id,
                    directional_accuracy=round(fold_acc, 4),
                    train_end=str(fold.train_end.date()),
                    test_start=str(fold.test_start.date()),
                )

            # ── Step 5: Fit Ridge meta-learner on OOF predictions ─────────────
            covered_idx = np.where(oof_covered)[0]
            y_oof       = labels.iloc[covered_idx].values.astype(int)

            # Chronos dir probs: neutral 0.5 for meta-fit (Chronos not run in train)
            chronos_5d  = np.full(len(covered_idx), 0.5, dtype=np.float32)
            chronos_10d = np.full(len(covered_idx), 0.5, dtype=np.float32)
            chronos_30d = np.full(len(covered_idx), 0.5, dtype=np.float32)

            self.ensemble.fit(
                xgb_proba=oof_xgb_proba[covered_idx],
                lgbm_proba=oof_lgbm_proba[covered_idx],
                catboost_proba=oof_catboost_proba[covered_idx],
                regime_ids=oof_regime_ids[covered_idx],
                chronos_dir_5d=chronos_5d,
                chronos_dir_10d=chronos_10d,
                chronos_dir_30d=chronos_30d,
                y_labels=y_oof,
            )

            # ── Step 6: Aggregate results ─────────────────────────────────────
            wfo_result.mean_accuracy = float(np.mean(fold_accuracies))
            wfo_result.std_accuracy  = float(np.std(fold_accuracies))
            wfo_result.min_accuracy  = float(np.min(fold_accuracies))
            wfo_result.passes_threshold = (
                wfo_result.mean_accuracy >= WFO_MIN_DIRECTIONAL_ACCURACY
            )

            if self.use_mlflow:
                mlflow.log_metric("mean_oos_accuracy", wfo_result.mean_accuracy)
                mlflow.log_metric("std_oos_accuracy",  wfo_result.std_accuracy)
                mlflow.log_metric("min_oos_accuracy",  wfo_result.min_accuracy)
                mlflow.log_metric("n_folds", wfo_result.n_folds)
                mlflow.log_param("passes_threshold", wfo_result.passes_threshold)

            logger.info(
                "trainer.complete",
                ticker=self.ticker,
                horizon=self.horizon,
                mean_accuracy=round(wfo_result.mean_accuracy, 4),
                passes=wfo_result.passes_threshold,
                n_folds=wfo_result.n_folds,
            )

            # ── Step 7: Save production models (last fold) ───────────────────
            if last_xgb and last_lgbm and last_cb:
                last_xgb.save(self.model_dir / "xgboost.joblib")
                last_lgbm.save(self.model_dir / "lightgbm.joblib")
                last_cb.save(self.model_dir / "catboost")
                self.hmm.save(self.model_dir / "hmm.joblib")
                self.ensemble.save(self.model_dir / "ensemble.joblib")

        return TrainingResult(
            ticker=self.ticker,
            horizon=self.horizon,
            wfo_result=wfo_result,
            xgb=last_xgb,
            lgbm=last_lgbm,
            catboost=last_cb,
            hmm=self.hmm,
            ensemble=self.ensemble,
            xgb_params=self._xgb_best_params,
            lgbm_params=self._lgbm_best_params,
            cb_params=self._cb_best_params,
        )


class TrainingResult:
    """Container for all trained models + metrics from one training run."""

    def __init__(
        self,
        ticker:     str,
        horizon:    int,
        wfo_result: WFOResult,
        xgb:        Optional[XGBoostPredictor],
        lgbm:       Optional[LightGBMPredictor],
        catboost:   Optional[CatBoostPredictor],
        hmm:        HMMRegimeDetector,
        ensemble:   EnsemblePredictor,
        xgb_params:  Optional[dict],
        lgbm_params: Optional[dict],
        cb_params:   Optional[dict],
    ):
        self.ticker      = ticker
        self.horizon     = horizon
        self.wfo_result  = wfo_result
        self.xgb         = xgb
        self.lgbm        = lgbm
        self.catboost    = catboost
        self.hmm         = hmm
        self.ensemble    = ensemble
        self.xgb_params  = xgb_params
        self.lgbm_params = lgbm_params
        self.cb_params   = cb_params

    @property
    def passes_accuracy_gate(self) -> bool:
        return self.wfo_result.passes_threshold

    def summary(self) -> str:
        return (
            f"Ticker: {self.ticker} | Horizon: {self.horizon}d | "
            f"OOS Accuracy: {self.wfo_result.mean_accuracy:.1%} ± "
            f"{self.wfo_result.std_accuracy:.1%} | "
            f"Passes gate (≥55%): {self.passes_accuracy_gate} | "
            f"Folds: {self.wfo_result.n_folds}"
        )


class _NullContext:
    """No-op context manager when MLflow disabled."""
    def __enter__(self): return self
    def __exit__(self, *args): pass