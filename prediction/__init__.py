"""
prediction/ — ML Prediction Engine for India Multi-Agent Finance AI.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Sub-packages:
  models/    — XGBoost, LightGBM, CatBoost, HMM, Ensemble, Chronos-2
  training/  — IndiaMLTrainer, IndiaWalkForwardValidator, OptunaTuner,
               RegimeAwareTrainer
  inference/ — PredictionService, ConfidenceCalculator, ModelRouter

Blueprint Phase 5 Validation Gate:
  Walk-forward directional accuracy > 55% OOS on 3yr Nifty 50 data.

Usage (all core classes importable directly from this package):
    from prediction import IndiaMLTrainer, PredictionService, PredictionResult
    from prediction import XGBoostPredictor, HMMRegimeDetector, EnsemblePredictor
    from prediction import ModelRouter, TaskType, TSFMRoute
"""
from __future__ import annotations

# ── Models ────────────────────────────────────────────────────────────────────
from prediction.models.xgboost_predictor import XGBoostPredictor
from prediction.models.lightgbm_predictor import LightGBMPredictor
from prediction.models.catboost_predictor import CatBoostPredictor
from prediction.models.hmm_regime import HMMRegimeDetector, REGIME_NAMES
from prediction.models.ensemble_predictor import EnsemblePredictor
from prediction.models.chronos2_predictor import Chronos2Predictor

# ── Training ──────────────────────────────────────────────────────────────────
from prediction.training.trainer import IndiaMLTrainer, TrainingResult
from prediction.training.india_walk_forward import (
    IndiaWalkForwardValidator,
    WFOFold,
    WFOResult,
)
from prediction.training.optuna_tuner import OptunaTuner
from prediction.training.regime_aware_trainer import RegimeAwareTrainer

# ── Inference ─────────────────────────────────────────────────────────────────
from prediction.inference.prediction_service import PredictionService, PredictionResult
from prediction.inference.confidence_calculator import ConfidenceCalculator
from prediction.inference.model_router import ModelRouter, TaskType, TSFMRoute

__all__ = [
    # Models
    "XGBoostPredictor",
    "LightGBMPredictor",
    "CatBoostPredictor",
    "HMMRegimeDetector",
    "REGIME_NAMES",
    "EnsemblePredictor",
    "Chronos2Predictor",
    # Training
    "IndiaMLTrainer",
    "TrainingResult",
    "IndiaWalkForwardValidator",
    "WFOFold",
    "WFOResult",
    "OptunaTuner",
    "RegimeAwareTrainer",
    # Inference
    "PredictionService",
    "PredictionResult",
    "ConfidenceCalculator",
    "ModelRouter",
    "TaskType",
    "TSFMRoute",
]
