"""
TimesFM Predictor — PyPI v1.3.0 (torch-only path)
Google Research TimesFM: decoder-only foundation model for time series.

RESEARCH NOTE (March 2026):
  timesfm 2.0.0 exists only in google-research/timesfm GitHub repo.
  It was NEVER published to PyPI. PyPI latest = 1.3.0.
  This module uses the v1.3.0 torch API which is stable on Python 3.11.
  When v2.x is published to PyPI, update the import adapter below.

Role in ensemble:
  - Alternative TSFM to Chronos-2 for fine-tuned tasks
  - Outperforms GARCH/GAS on VaR tasks when fine-tuned (blueprint §3)
  - Routes via model_router.py: TimesFM for fine-tuned, Chronos-2 for zero-shot

Blueprint: prediction/models/timesfm_predictor.py
"""
from __future__ import annotations

import importlib.metadata
import warnings
from typing import Optional

import numpy as np
import pandas as pd
import structlog
import torch

logger = structlog.get_logger(__name__)

# ── Version-aware import ──────────────────────────────────────────────────────
_TIMESFM_VERSION = importlib.metadata.version("timesfm")
_TIMESFM_MAJOR = int(_TIMESFM_VERSION.split(".")[0])

try:
    import timesfm  # noqa
    _TIMESFM_AVAILABLE = True
except ImportError:
    _TIMESFM_AVAILABLE = False
    logger.warning("timesfm.not_available",
                   note="Install: pip install timesfm==1.3.0 --no-deps")


class TimesFMPredictor:
    """
    TimesFM wrapper for India stock price forecasting.

    Supports v1.3.0 (current PyPI) torch-only path.
    Architecture: decoder-only transformer, continuous quantile output.

    Key difference from Chronos-2:
      - TimesFM: better when fine-tuned on domain data (Indian equities)
      - Chronos-2: better for zero-shot with covariates
      Use model_router.py to select per task.
    """

    # TimesFM v1.3.0 model identifiers (HuggingFace)
    MODEL_SMALL = "google/timesfm-1.0-200m"        # 200M params
    MODEL_DEFAULT = "google/timesfm-1.0-200m-pytorch"

    def __init__(
        self,
        model_id: str = MODEL_DEFAULT,
        context_len: int = 512,        # v1.3.0 max context
        horizon_len: int = 30,
        num_samples: int = 20,
        device: str = "cpu",           # CPU default — no CUDA required for dev
    ):
        if not _TIMESFM_AVAILABLE:
            raise ImportError(
                "timesfm not installed. "
                "Run: pip install timesfm==1.3.0 --no-deps && "
                "pip install einshape utilsforecast safetensors absl-py"
            )

        self.model_id = model_id
        self.context_len = context_len
        self.horizon_len = horizon_len
        self.num_samples = num_samples
        self.device = device
        self._model = None

        logger.info(
            "timesfm.init",
            version=_TIMESFM_VERSION,
            model=model_id,
            context_len=context_len,
            horizon_len=horizon_len,
            device=device,
        )

    def _load_model(self):
        """Lazy-load model on first call (avoids startup delay)."""
        if self._model is not None:
            return

        logger.info("timesfm.loading", model=self.model_id)
        try:
            # v1.3.0 torch API
            from timesfm import TimesFm, TimesFmHparams, TimesFmCheckpoint  # noqa
            hparams = TimesFmHparams(
                context_len=self.context_len,
                horizon_len=self.horizon_len,
                backend="pytorch",
            )
            self._model = TimesFm(
                hparams=hparams,
                checkpoint=TimesFmCheckpoint(huggingface_repo_id=self.model_id),
            )
            logger.info("timesfm.loaded", model=self.model_id)
        except Exception as e:
            logger.error("timesfm.load_error", error=str(e))
            raise

    def predict(
        self,
        close_prices: pd.Series,
        horizon_days: int = 5,
    ) -> dict:
        """
        Generate probabilistic price forecast using TimesFM.

        Args:
            close_prices: pd.Series of historical close prices
                          Index: DatetimeIndex (Asia/Kolkata)
                          Minimum length: context_len (512 days)
            horizon_days: Forecast horizon in trading days (5, 10, or 30)

        Returns:
            dict with keys:
              'p10': 10th percentile price path (array of horizon_days)
              'p50': median price path
              'p90': 90th percentile price path
              'model': 'timesfm'
              'version': timesfm version string
        """
        self._load_model()

        # Validate input
        if len(close_prices) < 64:
            raise ValueError(
                f"TimesFM needs ≥64 data points, got {len(close_prices)}"
            )

        # Use last context_len points (or all if fewer available)
        series = close_prices.values[-self.context_len:]
        series = series.astype(np.float32)

        try:
            # v1.3.0 prediction API
            import timesfm as tfm
            forecast = self._model.forecast(
                inputs=[series],
                freq=[0],  # 0 = daily frequency
            )
            # forecast returns (point_forecast, quantile_forecast)
            point = forecast[0][0, :horizon_days]
            quantiles = forecast[1][0, :horizon_days, :]  # shape (horizon, n_quantiles)

            # Map quantile indices (v1.3.0 default quantiles: [0.1, 0.2, ..., 0.9])
            q10 = quantiles[:, 0]  # 10th percentile
            q50 = quantiles[:, 4]  # 50th percentile (median)
            q90 = quantiles[:, 8]  # 90th percentile

            result = {
                "p10": q10.tolist(),
                "p50": q50.tolist(),
                "p90": q90.tolist(),
                "model": "timesfm",
                "version": _TIMESFM_VERSION,
                "horizon_days": horizon_days,
            }
            logger.info(
                "timesfm.predicted",
                horizon_days=horizon_days,
                p50_final=float(q50[-1]),
            )
            return result

        except Exception as e:
            logger.error("timesfm.predict_error", error=str(e))
            raise

    @classmethod
    def is_available(cls) -> bool:
        """Check if TimesFM is installed and importable."""
        return _TIMESFM_AVAILABLE

    @classmethod
    def get_version(cls) -> str:
        """Return installed TimesFM version string."""
        return _TIMESFM_VERSION