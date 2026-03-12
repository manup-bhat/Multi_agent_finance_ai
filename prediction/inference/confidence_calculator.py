"""
Confidence Calculator
━━━━━━━━━━━━━━━━━━━━
Calibrates raw model confidence with India-specific adjustments:
  - VIX dampening: high VIX → reduce confidence (market is unpredictable)
  - Regime penalty: Bear regime → reduce confidence 10%
  - Model agreement boost: all 3 models agree → +5% confidence
  - Crisis floor: if VIX > CRISIS_THRESHOLD, confidence capped at 40%

HARD RULE: This is deterministic Python. No LLM involved.
"""
from __future__ import annotations

from config.constants import (
    VIX_NORMAL_MAX,
    VIX_ELEVATED_MAX,
    VIX_CIRCUIT_BREAKER,
    VIX_CRISIS_THRESHOLD,
    PREDICTION_CONFIDENCE_THRESHOLD,
)

import structlog

logger = structlog.get_logger(__name__)


class ConfidenceCalculator:
    """
    Calibrates confidence score using India market context.

    Calibration factors applied sequentially:
      1. VIX dampening   — high VIX reduces model reliability
      2. Regime penalty  — Bear markets reduce directional predictability
      3. Agreement boost — 3-model consensus increases confidence
      4. Hard caps       — crisis floor + maximum cap at 0.95
    """

    # VIX calibration multipliers
    VIX_MULTIPLIERS = {
        "complacency": 1.05,   # VIX < 13: markets calm, models more reliable
        "normal":      1.00,   # VIX 13-18: baseline
        "elevated":    0.90,   # VIX 18-25: reduce 10%
        "high":        0.75,   # VIX 25-30: reduce 25%
        "crisis":      0.50,   # VIX > 30: reduce 50%
    }

    # Regime multipliers
    REGIME_MULTIPLIERS = {
        2: 1.03,   # Bull: slight boost
        1: 1.00,   # Sideways: neutral
        0: 0.90,   # Bear: reduce 10% (harder to predict)
    }

    # Model agreement bonuses
    AGREEMENT_BONUS = {3: 0.05, 2: 0.02, 1: -0.03}  # 3=all agree, 1=all disagree

    # Hard caps
    CRISIS_CONFIDENCE_CAP = 0.40   # VIX > 30: never show > 40% confidence
    MAX_CONFIDENCE        = 0.95   # absolute ceiling

    def calibrate(
        self,
        raw_confidence:      float,
        vix_level:           float,
        regime_id:           int,
        n_models_agreeing:   int,
    ) -> float:
        """
        Apply India-context calibration to raw model confidence.

        Args:
            raw_confidence:    Softmax confidence from Ridge meta-learner [0-1]
            vix_level:         Current India VIX value
            regime_id:         HMM regime {0=Bear, 1=Sideways, 2=Bull}
            n_models_agreeing: How many of XGB/LGBM/CatBoost agree (1-3)

        Returns:
            Calibrated confidence [0.0, 0.95]
        """
        # ── VIX dampening ─────────────────────────────────────────────────────
        if vix_level < 13.0:
            vix_mult = self.VIX_MULTIPLIERS["complacency"]
        elif vix_level < VIX_NORMAL_MAX:
            vix_mult = self.VIX_MULTIPLIERS["normal"]
        elif vix_level < VIX_ELEVATED_MAX:
            vix_mult = self.VIX_MULTIPLIERS["elevated"]
        elif vix_level < VIX_CRISIS_THRESHOLD:
            vix_mult = self.VIX_MULTIPLIERS["high"]
        else:
            vix_mult = self.VIX_MULTIPLIERS["crisis"]

        # ── Regime adjustment ─────────────────────────────────────────────────
        regime_mult = self.REGIME_MULTIPLIERS.get(regime_id, 1.0)

        # ── Model agreement adjustment ────────────────────────────────────────
        agreement_adj = self.AGREEMENT_BONUS.get(n_models_agreeing, 0.0)

        # ── Apply all adjustments ─────────────────────────────────────────────
        calibrated = raw_confidence * vix_mult * regime_mult + agreement_adj

        # ── Hard caps ─────────────────────────────────────────────────────────
        if vix_level >= VIX_CRISIS_THRESHOLD:
            calibrated = min(calibrated, self.CRISIS_CONFIDENCE_CAP)

        calibrated = max(0.01, min(calibrated, self.MAX_CONFIDENCE))

        logger.debug(
            "confidence.calibrated",
            raw=round(raw_confidence, 4),
            calibrated=round(calibrated, 4),
            vix=vix_level,
            vix_mult=vix_mult,
            regime_id=regime_id,
            agreement=n_models_agreeing,
        )
        return round(calibrated, 4)