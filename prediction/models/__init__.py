"""
prediction.models — ML model classes for India Financial Engine.

Available after Phase 3 files are committed:
  Chronos2Predictor   — Amazon Chronos-2 multivariate TSFM
  XGBoostPredictor    — 5-class directional classifier
  LightGBMPredictor   — 5-class stacking classifier
  CatBoostPredictor   — 5-class with native India categoricals
  HMMRegimeDetector   — GaussianHMM Bull/Sideways/Bear regime
  EnsemblePredictor   — Ridge meta-learner stacking all models

Import guard: each class is imported inside a try/except so that the
package is importable even when individual model files are not yet present.
This lets `python -c "from prediction.models import ..."` pass the
Phase 3 smoke test as files are added incrementally.
"""
from __future__ import annotations

__all__ = [
    "Chronos2Predictor",
    "XGBoostPredictor",
    "LightGBMPredictor",
    "CatBoostPredictor",
    "HMMRegimeDetector",
    "EnsemblePredictor",
]

try:
    from prediction.models.chronos2_predictor import Chronos2Predictor
except ImportError:
    Chronos2Predictor = None  # type: ignore[assignment,misc]

try:
    from prediction.models.xgboost_predictor import XGBoostPredictor
except ImportError:
    XGBoostPredictor = None  # type: ignore[assignment,misc]

try:
    from prediction.models.lightgbm_predictor import LightGBMPredictor
except ImportError:
    LightGBMPredictor = None  # type: ignore[assignment,misc]

try:
    from prediction.models.catboost_predictor import CatBoostPredictor
except ImportError:
    CatBoostPredictor = None  # type: ignore[assignment,misc]

try:
    from prediction.models.hmm_regime import HMMRegimeDetector
except ImportError:
    HMMRegimeDetector = None  # type: ignore[assignment,misc]

try:
    from prediction.models.ensemble_predictor import EnsemblePredictor
except ImportError:
    EnsemblePredictor = None  # type: ignore[assignment,misc]