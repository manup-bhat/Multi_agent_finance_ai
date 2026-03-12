"""
prediction.training — Walk-forward training pipeline.

Available after Phase 3 files are committed:
  IndiaWalkForwardValidator  — 504/63/5/21 anti-lookahead WFO
  WFOFold, WFOResult         — fold dataclasses
  IndiaMLTrainer             — full training pipeline
  TrainingResult             — training output dataclass
  OptunaTuner                — Bayesian hyperparameter optimisation
  RegimeAwareTrainer         — separate weights per HMM regime
"""
from __future__ import annotations

__all__ = [
    "IndiaWalkForwardValidator",
    "WFOFold",
    "WFOResult",
    "IndiaMLTrainer",
    "TrainingResult",
    "OptunaTuner",
    "RegimeAwareTrainer",
]

try:
    from prediction.training.india_walk_forward import (
        IndiaWalkForwardValidator,
        WFOFold,
        WFOResult,
    )
except ImportError:
    IndiaWalkForwardValidator = None  # type: ignore[assignment,misc]
    WFOFold = None                    # type: ignore[assignment,misc]
    WFOResult = None                  # type: ignore[assignment,misc]

try:
    from prediction.training.trainer import IndiaMLTrainer, TrainingResult
except ImportError:
    IndiaMLTrainer = None   # type: ignore[assignment,misc]
    TrainingResult = None   # type: ignore[assignment,misc]

try:
    from prediction.training.optuna_tuner import OptunaTuner
except ImportError:
    OptunaTuner = None  # type: ignore[assignment,misc]

try:
    from prediction.training.regime_aware_trainer import RegimeAwareTrainer
except ImportError:
    RegimeAwareTrainer = None  # type: ignore[assignment,misc]