"""
Optuna Bayesian Hyperparameter Tuner
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tunes XGBoost, LightGBM, and CatBoost hyperparameters using
Bayesian optimisation via Optuna.

Blueprint: 8-15% ensemble accuracy gain over single model
when XGB+LGBM+CatBoost are properly stacked and tuned.

Config:
  OPTUNA_N_TRIALS   = 50  (from constants.py)
  OPTUNA_TIMEOUT_S  = 300 (5 minutes max per model)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import optuna
import structlog
from typing import Callable, Optional

import xgboost as xgb
import lightgbm as lgb
from catboost import CatBoostClassifier, Pool

from config.constants import (
    XGBOOST_N_CLASSES,
    OPTUNA_N_TRIALS,
    OPTUNA_TIMEOUT_SECONDS,
)
from features.india_feature_set import ALL_FEATURE_COLUMNS
from prediction.models.catboost_predictor import CATBOOST_CATEGORICAL_FEATURES
from prediction.models.lightgbm_predictor import LGBM_CATEGORICAL_COLS
from prediction.training.india_walk_forward import (
    IndiaWalkForwardValidator,
    WFOFold,
)

logger = structlog.get_logger(__name__)

# Suppress Optuna logs (use structlog instead)
optuna.logging.set_verbosity(optuna.logging.WARNING)


class OptunaTuner:
    """
    Bayesian hyperparameter optimisation for all three gradient boosters.
    Uses a single walk-forward fold (first 2 folds of WFO) for fast tuning.
    Production training uses ALL folds after tuning.
    """

    def __init__(
        self,
        n_trials:        int = OPTUNA_N_TRIALS,
        timeout_seconds: int = OPTUNA_TIMEOUT_SECONDS,
        random_state:    int = 42,
    ):
        self.n_trials        = n_trials
        self.timeout_seconds = timeout_seconds
        self.random_state    = random_state

    # ── XGBoost Tuning ────────────────────────────────────────────────────────
    def tune_xgboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val:   pd.DataFrame,
        y_val:   pd.Series,
    ) -> dict:
        """
        Bayesian search over XGBoost hyperparameter space.
        Returns best params dict ready to pass to XGBoostPredictor.
        """
        def objective(trial: optuna.Trial) -> float:
            params = {
                "objective":        "multi:softprob",
                "num_class":        XGBOOST_N_CLASSES,
                "eval_metric":      "mlogloss",
                "n_estimators":     trial.suggest_int("n_estimators", 200, 800),
                "max_depth":        trial.suggest_int("max_depth", 4, 8),
                "learning_rate":    trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                "subsample":        trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 3, 15),
                "gamma":            trial.suggest_float("gamma", 0.0, 0.5),
                "reg_alpha":        trial.suggest_float("reg_alpha", 1e-4, 1.0, log=True),
                "reg_lambda":       trial.suggest_float("reg_lambda", 0.5, 3.0),
                "tree_method":      "hist",
                "random_state":     self.random_state,
                "n_jobs":           -1,
                "verbosity":        0,
            }
            X_tr = X_train[ALL_FEATURE_COLUMNS].fillna(0)
            y_tr = y_train.dropna().astype(int)
            X_vl = X_val[ALL_FEATURE_COLUMNS].fillna(0)
            y_vl = y_val.dropna().astype(int)

            model = xgb.XGBClassifier(**params)
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_vl, y_vl)],
                verbose=False,
            )
            preds   = model.predict(X_vl)
            correct = (preds == y_vl.values).mean()
            return correct

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=self.random_state),
        )
        study.optimize(
            objective,
            n_trials=self.n_trials,
            timeout=self.timeout_seconds,
            show_progress_bar=False,
        )

        best = study.best_params
        best.update({
            "objective": "multi:softprob",
            "num_class": XGBOOST_N_CLASSES,
            "eval_metric": "mlogloss",
            "tree_method": "hist",
            "random_state": self.random_state,
            "n_jobs": -1,
            "verbosity": 0,
        })

        logger.info(
            "optuna.xgboost_best",
            best_val_accuracy=round(study.best_value, 4),
            n_trials=len(study.trials),
            params=best,
        )
        return best

    # ── LightGBM Tuning ───────────────────────────────────────────────────────
    def tune_lightgbm(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val:   pd.DataFrame,
        y_val:   pd.Series,
    ) -> dict:
        """Bayesian search over LightGBM hyperparameter space."""
        cat_cols = [c for c in LGBM_CATEGORICAL_COLS if c in X_train.columns]

        def objective(trial: optuna.Trial) -> float:
            params = {
                "objective":         "multiclass",
                "num_class":         XGBOOST_N_CLASSES,
                "metric":            "multi_logloss",
                "n_estimators":      trial.suggest_int("n_estimators", 200, 800),
                "max_depth":         trial.suggest_int("max_depth", 4, 9),
                "num_leaves":        trial.suggest_int("num_leaves", 31, 127),
                "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
                "reg_alpha":         trial.suggest_float("reg_alpha", 1e-4, 1.0, log=True),
                "reg_lambda":        trial.suggest_float("reg_lambda", 0.5, 3.0),
                "random_state":      self.random_state,
                "n_jobs":            -1,
                "verbose":           -1,
            }
            X_tr = X_train[ALL_FEATURE_COLUMNS].fillna(0)
            y_tr = y_train.dropna().astype(int)
            X_vl = X_val[ALL_FEATURE_COLUMNS].fillna(0)
            y_vl = y_val.dropna().astype(int)

            model = lgb.LGBMClassifier(**params)
            model.fit(
                X_tr, y_tr,
                eval_set=[(X_vl, y_vl)],
                categorical_feature=cat_cols,
                callbacks=[lgb.early_stopping(30, verbose=False), lgb.log_evaluation(-1)],
            )
            preds   = model.predict(X_vl)
            correct = (preds == y_vl.values).mean()
            return correct

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=self.random_state),
        )
        study.optimize(objective, n_trials=self.n_trials, timeout=self.timeout_seconds)

        best = study.best_params
        best.update({
            "objective": "multiclass",
            "num_class": XGBOOST_N_CLASSES,
            "metric": "multi_logloss",
            "random_state": self.random_state,
            "n_jobs": -1,
            "verbose": -1,
        })

        logger.info(
            "optuna.lightgbm_best",
            best_val_accuracy=round(study.best_value, 4),
            n_trials=len(study.trials),
        )
        return best

    # ── CatBoost Tuning ───────────────────────────────────────────────────────
    def tune_catboost(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val:   pd.DataFrame,
        y_val:   pd.Series,
    ) -> dict:
        """Bayesian search over CatBoost hyperparameter space."""
        feat_names = ALL_FEATURE_COLUMNS
        cat_idx = [
            feat_names.index(c)
            for c in CATBOOST_CATEGORICAL_FEATURES
            if c in feat_names
        ]

        def objective(trial: optuna.Trial) -> float:
            params = {
                "loss_function":       "MultiClass",
                "eval_metric":         "Accuracy",
                "classes_count":       XGBOOST_N_CLASSES,
                "iterations":          trial.suggest_int("iterations", 200, 800),
                "depth":               trial.suggest_int("depth", 4, 8),
                "learning_rate":       trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                "l2_leaf_reg":         trial.suggest_float("l2_leaf_reg", 1.0, 10.0),
                "bagging_temperature": trial.suggest_float("bagging_temperature", 0.0, 1.0),
                "random_strength":     trial.suggest_float("random_strength", 0.1, 3.0),
                "min_data_in_leaf":    trial.suggest_int("min_data_in_leaf", 5, 50),
                "random_seed":         self.random_state,
                "thread_count":        -1,
                "verbose":             False,
                "allow_writing_files": False,
            }

            X_tr = X_train[feat_names].copy()
            y_tr = y_train.dropna().astype(int)
            X_vl = X_val[feat_names].copy()
            y_vl = y_val.dropna().astype(int)

            for col in CATBOOST_CATEGORICAL_FEATURES:
                if col in X_tr.columns:
                    X_tr[col] = X_tr[col].fillna(0).astype(int)
                    X_vl[col] = X_vl[col].fillna(0).astype(int)

            train_pool = Pool(data=X_tr.fillna(0), label=y_tr, cat_features=cat_idx)
            val_pool   = Pool(data=X_vl.fillna(0), label=y_vl, cat_features=cat_idx)

            model = CatBoostClassifier(**params)
            model.fit(train_pool, eval_set=val_pool, use_best_model=True)

            preds   = model.predict(val_pool).flatten().astype(int)
            correct = (preds == y_vl.values).mean()
            return correct

        study = optuna.create_study(
            direction="maximize",
            sampler=optuna.samplers.TPESampler(seed=self.random_state),
        )
        study.optimize(objective, n_trials=self.n_trials, timeout=self.timeout_seconds)

        best = study.best_params
        best.update({
            "loss_function": "MultiClass",
            "eval_metric": "Accuracy",
            "classes_count": XGBOOST_N_CLASSES,
            "random_seed": self.random_state,
            "thread_count": -1,
            "verbose": False,
            "allow_writing_files": False,
        })

        logger.info(
            "optuna.catboost_best",
            best_val_accuracy=round(study.best_value, 4),
            n_trials=len(study.trials),
        )
        return best