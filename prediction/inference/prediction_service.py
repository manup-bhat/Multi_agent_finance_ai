"""
Prediction Service — Live Inference Entry Point
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Loads all trained models and orchestrates end-to-end prediction.
Called by: agents/prediction_agent.py

Returns a PredictionResult containing:
  - Chronos-2 probabilistic price path (5/10/30d)
  - XGB+LGBM+CatBoost directional probabilities (5-class)
  - Ridge ensemble final verdict
  - HMM regime label
  - SHAP top-5 feature drivers
  - Confidence + circuit breaker status
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shap
import structlog
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config.constants import (
    VIX_CIRCUIT_BREAKER,
    PREDICTION_CONFIDENCE_THRESHOLD,
    CHRONOS_HORIZONS,
    MARKET_TZ,
)
from features.india_feature_set import ALL_FEATURE_COLUMNS, CHRONOS_COVARIATES
from prediction.models.chronos2_predictor import Chronos2Predictor
from prediction.models.xgboost_predictor import XGBoostPredictor
from prediction.models.lightgbm_predictor import LightGBMPredictor
from prediction.models.catboost_predictor import CatBoostPredictor
from prediction.models.hmm_regime import HMMRegimeDetector, REGIME_NAMES
from prediction.models.ensemble_predictor import EnsemblePredictor
from prediction.inference.confidence_calculator import ConfidenceCalculator
from prediction.inference.model_router import ModelRouter

logger = structlog.get_logger(__name__)

MODEL_DIR = Path("models/saved")


@dataclass
class PredictionResult:
    """Structured output from the prediction service."""
    ticker:              str = ""
    current_price:       float = 0.0
    timestamp:           Optional[pd.Timestamp] = None

    # Chronos-2 price targets (INR)
    forecast_5d:         float = 0.0
    forecast_10d:        float = 0.0
    forecast_30d:        float = 0.0
    q10_5d:              float = 0.0
    q90_5d:              float = 0.0
    return_pct_5d:       float = 0.0

    # Directional ensemble
    direction:           str = "Neutral"
    direction_class:     int = 2
    bullish_prob:        float = 0.5
    bearish_prob:        float = 0.5
    confidence:          float = 0.5
    class_probs:         dict = field(default_factory=dict)

    # Regime
    regime_name:         str = "Sideways"
    regime_id:           int = 1

    # Risk gates
    is_high_confidence:  bool = False
    vix_circuit_breaker: bool = False
    vix_level:           float = 0.0

    # SHAP top drivers (list of {"feature": str, "value": float, "impact": float})
    top_features:        list[dict] = field(default_factory=list)

    # Raw model outputs (for Phoenix audit trail)
    xgb_proba:           list[float] = field(default_factory=list)
    lgbm_proba:          list[float] = field(default_factory=list)
    catboost_proba:      list[float] = field(default_factory=list)
    chronos_dir_5d:      float = 0.5
    chronos_dir_10d:     float = 0.5
    chronos_dir_30d:     float = 0.5

    def to_agent_summary(self) -> str:
        """
        Plain-text summary for LLM agent consumption.
        HARD RULE: No calculations here — data only.
        LLM reads this text; it never computes from it.
        """
        cb_flag = " ⚠️ VIX CIRCUIT BREAKER ACTIVE — OVERRIDE TO HOLD" if self.vix_circuit_breaker else ""
        conf_flag = " [LOW CONFIDENCE]" if not self.is_high_confidence else ""
        top_f = "\n".join(
            f"    {i+1}. {d['feature']}: {d['impact']:+.3f} (value={d['value']:.3f})"
            for i, d in enumerate(self.top_features[:5])
        )
        return (
            f"PREDICTION [{self.ticker}] @ ₹{self.current_price:.2f}{cb_flag}\n"
            f"Timestamp : {self.timestamp}\n"
            f"Regime    : {self.regime_name} (id={self.regime_id})\n"
            f"Direction : {self.direction}{conf_flag}\n"
            f"Confidence: {self.confidence:.1%}\n"
            f"Bullish P : {self.bullish_prob:.1%}  |  Bearish P: {self.bearish_prob:.1%}\n"
            f"\n5-day Price Forecast (Chronos-2):\n"
            f"  Median  : ₹{self.forecast_5d:.2f} ({self.return_pct_5d:+.2f}%)\n"
            f"  10th pct: ₹{self.q10_5d:.2f}\n"
            f"  90th pct: ₹{self.q90_5d:.2f}\n"
            f"\n10-day Forecast : ₹{self.forecast_10d:.2f}\n"
            f"30-day Forecast : ₹{self.forecast_30d:.2f}\n"
            f"\nChronos Direction P(up): 5d={self.chronos_dir_5d:.1%} | "
            f"10d={self.chronos_dir_10d:.1%} | 30d={self.chronos_dir_30d:.1%}\n"
            f"\nTop Feature Drivers (SHAP):\n{top_f}\n"
        )


class PredictionService:
    """
    Live inference service.

    Load once at startup; call predict() per ticker per request.
    Lazy-loads Chronos-2 (heavy) on first call.

    Blueprint hard gates enforced here (deterministic Python, not LLM):
      - VIX > 25 → vix_circuit_breaker = True (agents/risk_node.py acts on this)
      - confidence < 55% → is_high_confidence = False (Devil's Advocate weight amplified)
    """

    def __init__(
        self,
        ticker:        str,
        horizon:       int = 5,
        model_dir:     Path = MODEL_DIR,
        chronos_size:  str = "small",   # "tiny"/"small"/"base" — base is production
        use_bolt:      bool = False,
    ):
        self.ticker     = ticker
        self.horizon    = horizon
        self.model_dir  = Path(model_dir) / ticker.replace(".", "_") / f"h{horizon}"
        self._loaded    = False

        # Model instances (loaded lazily)
        self._xgb:       Optional[XGBoostPredictor]  = None
        self._lgbm:      Optional[LightGBMPredictor] = None
        self._cb:        Optional[CatBoostPredictor] = None
        self._hmm:       Optional[HMMRegimeDetector] = None
        self._ensemble:  Optional[EnsemblePredictor] = None
        self._chronos:   Optional[Chronos2Predictor] = None
        self._shap_xgb_explainer = None

        self._chronos_size = chronos_size
        self._use_bolt     = use_bolt
        self._conf_calc    = ConfidenceCalculator()
        self._router       = ModelRouter()

    def load_models(self) -> None:
        """Load all trained models from disk. Call once at startup."""
        if self._loaded:
            return

        logger.info("prediction_service.loading", ticker=self.ticker)

        # Gradient boosters
        self._xgb = XGBoostPredictor(horizon=self.horizon)
        self._xgb.load(self.model_dir / "xgboost.joblib")

        self._lgbm = LightGBMPredictor(horizon=self.horizon)
        self._lgbm.load(self.model_dir / "lightgbm.joblib")

        self._cb = CatBoostPredictor(horizon=self.horizon)
        self._cb.load(self.model_dir / "catboost")

        # HMM + Ensemble
        self._hmm = HMMRegimeDetector()
        self._hmm.load(self.model_dir / "hmm.joblib")

        self._ensemble = EnsemblePredictor()
        self._ensemble.load(self.model_dir / "ensemble.joblib")

        # SHAP explainer for XGBoost (fast tree explainer)
        self._shap_xgb_explainer = shap.TreeExplainer(self._xgb.model)

        # Chronos-2: lazy-loaded on first predict() call (heavy)
        self._chronos = Chronos2Predictor(
            model_size=self._chronos_size,
            use_bolt=self._use_bolt,
        )

        self._loaded = True
        logger.info("prediction_service.loaded", ticker=self.ticker, horizon=self.horizon)

    def predict(
        self,
        feature_df:     pd.DataFrame,
        price_series:   pd.Series,
        nifty_returns:  pd.Series,
        covariate_df:   pd.DataFrame,
        vix_current:    float,
        vix_series:     Optional[pd.Series] = None,
    ) -> PredictionResult:
        """
        Run full prediction pipeline for one ticker.

        Args:
            feature_df:    70-column feature DataFrame (output of IndiaFeatureSet.build())
                           Must have >= 252 rows. Last row = today's features.
            price_series:  Daily close prices (same index, raw/unshifted).
            nifty_returns: Log returns of Nifty 50 for HMM regime detection.
            covariate_df:  8-column Chronos-2 covariate DataFrame (shifted).
            vix_current:   India VIX level right now (from yfinance_client).
            vix_series:    Historical VIX series for HMM (optional).

        Returns:
            PredictionResult — fully populated, ready for agent consumption.
        """
        if not self._loaded:
            self.load_models()

        result = PredictionResult(
            ticker=self.ticker,
            current_price=float(price_series.iloc[-1]),
            timestamp=pd.Timestamp.now(tz=MARKET_TZ),
            vix_level=vix_current,
        )

        # ── Gate 1: VIX Circuit Breaker (deterministic — no LLM) ─────────────
        result.vix_circuit_breaker = vix_current >= VIX_CIRCUIT_BREAKER
        if result.vix_circuit_breaker:
            logger.warning(
                "prediction_service.vix_circuit_breaker",
                vix=vix_current,
                threshold=VIX_CIRCUIT_BREAKER,
            )
            # Return early with forced neutral/hold signal
            result.direction       = "Neutral"
            result.direction_class = 2
            result.confidence      = 0.5
            result.bullish_prob    = 0.5
            result.bearish_prob    = 0.5
            result.regime_name     = "Unknown"
            result.top_features    = [{"feature": "VIX_CIRCUIT_BREAKER", "value": vix_current, "impact": -1.0}]
            return result

        # ── Step 1: HMM Regime Detection ──────────────────────────────────────
        nifty_aligned = nifty_returns.reindex(feature_df.index).ffill().fillna(0.0)
        vix_aligned   = vix_series.reindex(feature_df.index).ffill() if vix_series is not None else None

        # Refit HMM if stale
        if self._hmm.needs_refit(pd.Timestamp.now(tz=MARKET_TZ)):
            logger.info("prediction_service.hmm_refit")
            self._hmm.fit(nifty_aligned, vix_aligned)

        regime_info         = self._hmm.predict_current(nifty_aligned, vix_aligned)
        result.regime_id    = regime_info["regime_id"]
        result.regime_name  = regime_info["regime_name"]

        # ── Step 2: Gradient Booster Predictions ──────────────────────────────
        X_latest = feature_df.iloc[[-1]]   # last row = today's features

        xgb_proba  = self._xgb.predict_proba(X_latest)[0]
        lgbm_proba = self._lgbm.predict_proba(X_latest)[0]
        cb_proba   = self._cb.predict_proba(X_latest)[0]

        result.xgb_proba      = [round(float(p), 4) for p in xgb_proba]
        result.lgbm_proba     = [round(float(p), 4) for p in lgbm_proba]
        result.catboost_proba = [round(float(p), 4) for p in cb_proba]

        # ── Step 3: Chronos-2 Probabilistic Forecast ──────────────────────────
        try:
            chronos_out = self._chronos.predict(
                price_series=price_series,
                covariate_df=covariate_df,
                horizons=CHRONOS_HORIZONS,
                context_length=252,
            )
            result.forecast_5d    = chronos_out.get("forecast_5d", result.current_price)
            result.forecast_10d   = chronos_out.get("forecast_10d", result.current_price)
            result.forecast_30d   = chronos_out.get("forecast_30d", result.current_price)
            result.q10_5d         = chronos_out.get("q10_5d", result.current_price * 0.95)
            result.q90_5d         = chronos_out.get("q90_5d", result.current_price * 1.05)
            result.return_pct_5d  = chronos_out.get("return_pct_5d", 0.0)
            result.chronos_dir_5d  = chronos_out.get("direction_prob_up_5d", 0.5)
            result.chronos_dir_10d = chronos_out.get("direction_prob_up_10d", 0.5)
            result.chronos_dir_30d = chronos_out.get("direction_prob_up_30d", 0.5)
        except Exception as e:
            logger.error("prediction_service.chronos_failed", error=str(e))
            # Chronos failure → neutral fallback; gradient boosters still valid
            result.chronos_dir_5d = result.chronos_dir_10d = result.chronos_dir_30d = 0.5

        # ── Step 4: Ridge Meta-Learner Ensemble ───────────────────────────────
        ens_out = self._ensemble.predict(
            xgb_proba=xgb_proba,
            lgbm_proba=lgbm_proba,
            catboost_proba=cb_proba,
            regime_id=result.regime_id,
            chronos_dir_5d=result.chronos_dir_5d,
            chronos_dir_10d=result.chronos_dir_10d,
            chronos_dir_30d=result.chronos_dir_30d,
        )
        result.direction       = ens_out["direction"]
        result.direction_class = ens_out["direction_class"]
        result.confidence      = ens_out["confidence"]
        result.class_probs     = ens_out["class_probs"]
        result.bullish_prob    = ens_out["bullish_prob"]
        result.bearish_prob    = ens_out["bearish_prob"]

        # ── Step 5: Calibrated Confidence ─────────────────────────────────────
        result.confidence = self._conf_calc.calibrate(
            raw_confidence=result.confidence,
            vix_level=vix_current,
            regime_id=result.regime_id,
            n_models_agreeing=self._count_model_agreement(xgb_proba, lgbm_proba, cb_proba),
        )
        result.is_high_confidence = result.confidence >= PREDICTION_CONFIDENCE_THRESHOLD

        # ── Step 6: SHAP Feature Importance (XGBoost — fast tree explainer) ───
        try:
            X_for_shap = feature_df.iloc[[-1]][ALL_FEATURE_COLUMNS].fillna(0)
            shap_values = self._shap_xgb_explainer.shap_values(X_for_shap)
            # shap_values: list of arrays, one per class
            # Use predicted class's SHAP values
            pred_class_shap = shap_values[result.direction_class][0]
            feat_names      = ALL_FEATURE_COLUMNS
            feat_values     = X_for_shap.values[0]

            top_idx = np.argsort(np.abs(pred_class_shap))[::-1][:5]
            result.top_features = [
                {
                    "feature": feat_names[i],
                    "value":   round(float(feat_values[i]), 4),
                    "impact":  round(float(pred_class_shap[i]), 4),
                }
                for i in top_idx
            ]
        except Exception as e:
            logger.warning("prediction_service.shap_failed", error=str(e))
            result.top_features = []

        logger.info(
            "prediction_service.prediction_complete",
            ticker=self.ticker,
            direction=result.direction,
            confidence=round(result.confidence, 4),
            regime=result.regime_name,
            vix=vix_current,
            chronos_5d=round(result.forecast_5d, 2),
        )
        return result

    @staticmethod
    def _count_model_agreement(
        xgb_proba:  np.ndarray,
        lgbm_proba: np.ndarray,
        cb_proba:   np.ndarray,
    ) -> int:
        """Returns how many of the 3 models agree on the top direction (1-3)."""
        preds = [
            int(np.argmax(xgb_proba)),
            int(np.argmax(lgbm_proba)),
            int(np.argmax(cb_proba)),
        ]
        # Map to binary: bullish (>=3) or bearish (<=1) or neutral (==2)
        dirs = [(1 if p >= 3 else (-1 if p <= 1 else 0)) for p in preds]
        if dirs[0] == dirs[1] == dirs[2]:
            return 3
        elif dirs[0] == dirs[1] or dirs[1] == dirs[2] or dirs[0] == dirs[2]:
            return 2
        return 1