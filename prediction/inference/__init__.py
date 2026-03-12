"""
prediction.inference — Live inference service.

Available after Phase 3 files are committed:
  PredictionService    — orchestrates full prediction pipeline
  PredictionResult     — structured output dataclass
  ConfidenceCalculator — India-context VIX/regime calibration
  ModelRouter          — routes Chronos-2 vs Bolt vs TimesFM
  TSFMRoute            — route enum
  TaskType             — task type enum
"""
from __future__ import annotations

__all__ = [
    "PredictionService",
    "PredictionResult",
    "ConfidenceCalculator",
    "ModelRouter",
    "TSFMRoute",
    "TaskType",
]

try:
    from prediction.inference.prediction_service import PredictionService, PredictionResult
except ImportError:
    PredictionService = None   # type: ignore[assignment,misc]
    PredictionResult  = None   # type: ignore[assignment,misc]

try:
    from prediction.inference.confidence_calculator import ConfidenceCalculator
except ImportError:
    ConfidenceCalculator = None  # type: ignore[assignment,misc]

try:
    from prediction.inference.model_router import ModelRouter, TSFMRoute, TaskType
except ImportError:
    ModelRouter = None  # type: ignore[assignment,misc]
    TSFMRoute   = None  # type: ignore[assignment,misc]
    TaskType    = None  # type: ignore[assignment,misc]