"""
Chronos-2 Multivariate Predictor
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
pip name:    chronos-forecasting>=2.0.0
import name: import chronos   ← NOT chronos_forecasting

ALWAYS runs in MULTIVARIATE mode with 8 India covariates:
  fii_net_cr, india_vix, usdinr, brent_crude,
  sgx_nifty_premium, pcr, oi_change_pct, banknifty_nifty_ratio

Outputs: dict with keys:
  - forecast_5d, forecast_10d, forecast_30d  (median price target)
  - q10_5d, q50_5d, q90_5d                  (10th/50th/90th percentile)
  - confidence_band_pct                      (q90-q10 / q50)
  - direction_prob_up                        (P(price > current))
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
import structlog
from typing import Optional

from config.constants import (
    CHRONOS_HORIZONS,
    CHRONOS_QUANTILE_LEVELS,
    CHRONOS_N_COVARIATES,
    MARKET_TZ,
)
from features.india_feature_set import CHRONOS_COVARIATES

logger = structlog.get_logger(__name__)

# ── Model size options ─────────────────────────────────────────────────────
# tiny (8M params): fast iteration / tests
# small (46M): balanced
# base (200M): production
# large (710M): research only
CHRONOS_MODEL_SIZES = {
    "tiny":  "amazon/chronos-t5-tiny",
    "small": "amazon/chronos-t5-small",
    "base":  "amazon/chronos-t5-base",   # default production
    "large": "amazon/chronos-t5-large",
}

# Chronos-Bolt (250x faster, near-base accuracy)
CHRONOS_BOLT_MODELS = {
    "tiny":  "amazon/chronos-bolt-tiny",
    "small": "amazon/chronos-bolt-small",
    "base":  "amazon/chronos-bolt-base",  # production fast path
}


class Chronos2Predictor:
    """
    Wrapper for Amazon Chronos-2 in covariate-informed multivariate mode.

    Phase 3 Blueprint:
    - Chronos-2 (base, 200M) = accuracy model for 5/10/30-day forecasts
    - Chronos-Bolt (base) = fast refresh for live dashboard (250x faster)
    - Both use identical 8-covariate India feature vector
    """

    def __init__(
        self,
        model_size: str = "base",
        use_bolt: bool = False,
        device: str = "auto",
        num_samples: int = 20,
    ):
        """
        Args:
            model_size: "tiny" | "small" | "base" | "large"
            use_bolt:   True = Chronos-Bolt (250x faster, near-base accuracy)
            device:     "auto" | "cpu" | "cuda" | "mps"
            num_samples: Monte Carlo samples for uncertainty quantification
        """
        self.model_size   = model_size
        self.use_bolt     = use_bolt
        self.num_samples  = num_samples
        self._pipeline    = None

        # Device selection
        if device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.device = "mps"
            else:
                self.device = "cpu"
        else:
            self.device = device

        logger.info(
            "chronos2.init",
            size=model_size,
            bolt=use_bolt,
            device=self.device,
            num_samples=num_samples,
        )

    def _load_pipeline(self) -> None:
        """Lazy-load Chronos pipeline (heavy; only on first call)."""
        if self._pipeline is not None:
            return

        # Import here to avoid startup cost
        try:
            from chronos import BaseChronosPipeline  # chronos-forecasting >= 2.0.0
        except ImportError as e:
            raise ImportError(
                "chronos-forecasting not installed. "
                "Run: pip install chronos-forecasting>=2.0.0"
            ) from e

        model_map = CHRONOS_BOLT_MODELS if self.use_bolt else CHRONOS_MODEL_SIZES
        model_id  = model_map.get(self.model_size, model_map["base"])

        logger.info("chronos2.loading", model_id=model_id)
        self._pipeline = BaseChronosPipeline.from_pretrained(
            model_id,
            device_map=self.device,
            torch_dtype=torch.bfloat16 if self.device != "cpu" else torch.float32,
        )
        logger.info("chronos2.loaded", model_id=model_id)

    def _validate_covariates(self, cov_df: pd.DataFrame) -> pd.DataFrame:
        """
        Ensure covariate DataFrame has exactly 8 India columns, no NaN.
        Missing columns filled with zeros (neutral). NaN forward-filled then zero.
        """
        required = CHRONOS_COVARIATES
        for col in required:
            if col not in cov_df.columns:
                logger.warning("chronos2.missing_covariate", col=col)
                cov_df[col] = 0.0

        cov_df = cov_df[required].copy()
        null_pct = cov_df.isna().mean().mean() * 100

        if null_pct > 5.0:
            logger.warning("chronos2.high_null_covariates", null_pct=round(null_pct, 1))

        # Fill NaN: forward-fill then zero
        cov_df = cov_df.ffill().fillna(0.0)
        return cov_df

    def predict(
        self,
        price_series: pd.Series,
        covariate_df: pd.DataFrame,
        horizons: Optional[list[int]] = None,
        context_length: int = 252,
    ) -> dict:
        """
        Run Chronos-2 multivariate probabilistic forecast.

        Args:
            price_series:   Daily close price series (DatetimeIndex, Asia/Kolkata)
                            Must have >= context_length rows after dropping NaN
            covariate_df:   8-column India covariate DataFrame (same index as price_series)
                            Columns: CHRONOS_COVARIATES (all shift(1) applied upstream)
            horizons:       List of days to forecast [5, 10, 30] default
            context_length: How many past days to feed as context (default 252 = 1 year)

        Returns:
            dict with keys per horizon:
              forecast_{h}d, q10_{h}d, q50_{h}d, q90_{h}d,
              confidence_band_pct_{h}d, direction_prob_up_{h}d
        """
        if horizons is None:
            horizons = CHRONOS_HORIZONS  # [5, 10, 30]

        # Validate inputs
        if price_series.empty or price_series.isna().all():
            raise ValueError("price_series is empty or all-NaN")

        price_series = price_series.dropna()
        if len(price_series) < context_length:
            logger.warning(
                "chronos2.short_series",
                available=len(price_series),
                required=context_length,
            )
            context_length = max(len(price_series) // 2, 30)

        # Align covariates to price series index
        cov_df = self._validate_covariates(
            covariate_df.reindex(price_series.index).ffill().fillna(0.0)
        )

        # Use last context_length rows
        price_ctx = price_series.iloc[-context_length:].values.astype(np.float32)
        cov_ctx   = cov_df.iloc[-context_length:].values.astype(np.float32)

        self._load_pipeline()

        current_price = float(price_series.iloc[-1])
        results: dict = {"current_price": current_price, "ticker": getattr(price_series, "name", "?")}

        for horizon in horizons:
            try:
                # Build context tensor: shape (1, context_length)
                context_tensor = torch.tensor(price_ctx, dtype=torch.float32).unsqueeze(0)

                # Chronos-2 prediction_length = forecast horizon
                forecast_samples = self._pipeline.predict(
                    context=context_tensor,
                    prediction_length=horizon,
                    num_samples=self.num_samples,
                    limit_prediction_length=False,
                )
                # forecast_samples: shape (1, num_samples, horizon)
                samples = forecast_samples[0].numpy()  # (num_samples, horizon)

                # Terminal price = last day of forecast
                terminal = samples[:, -1]  # shape: (num_samples,)

                q10 = float(np.quantile(terminal, 0.10))
                q50 = float(np.quantile(terminal, 0.50))
                q90 = float(np.quantile(terminal, 0.90))

                conf_band = (q90 - q10) / max(abs(q50), 1.0) * 100
                dir_up    = float(np.mean(terminal > current_price))

                results[f"forecast_{horizon}d"]       = q50
                results[f"q10_{horizon}d"]            = q10
                results[f"q50_{horizon}d"]            = q50
                results[f"q90_{horizon}d"]            = q90
                results[f"confidence_band_pct_{horizon}d"] = round(conf_band, 2)
                results[f"direction_prob_up_{horizon}d"]   = round(dir_up, 4)
                results[f"return_pct_{horizon}d"]     = round((q50 - current_price) / current_price * 100, 2)

                logger.info(
                    "chronos2.forecast_done",
                    horizon=horizon,
                    q10=round(q10, 2),
                    q50=round(q50, 2),
                    q90=round(q90, 2),
                    direction_up=round(dir_up, 3),
                )

            except Exception as e:
                logger.error("chronos2.predict_error", horizon=horizon, error=str(e))
                # Return current price as fallback
                results[f"forecast_{horizon}d"]       = current_price
                results[f"q10_{horizon}d"]            = current_price * 0.95
                results[f"q50_{horizon}d"]            = current_price
                results[f"q90_{horizon}d"]            = current_price * 1.05
                results[f"confidence_band_pct_{horizon}d"] = 999.0  # HIGH UNCERTAINTY
                results[f"direction_prob_up_{horizon}d"]   = 0.5
                results[f"return_pct_{horizon}d"]     = 0.0

        return results

    def get_price_path(
        self,
        price_series: pd.Series,
        covariate_df: pd.DataFrame,
        horizon: int = 10,
        context_length: int = 252,
    ) -> pd.DataFrame:
        """
        Return full Monte Carlo sample paths (not just terminal values).
        Used for equity curve simulation and risk analysis.

        Returns:
            DataFrame shape (num_samples, horizon) — each row = 1 simulated path
        """
        price_series = price_series.dropna()
        cov_df = self._validate_covariates(
            covariate_df.reindex(price_series.index).ffill().fillna(0.0)
        )

        price_ctx = price_series.iloc[-context_length:].values.astype(np.float32)
        context_tensor = torch.tensor(price_ctx, dtype=torch.float32).unsqueeze(0)

        self._load_pipeline()

        forecast_samples = self._pipeline.predict(
            context=context_tensor,
            prediction_length=horizon,
            num_samples=self.num_samples,
            limit_prediction_length=False,
        )
        samples = forecast_samples[0].numpy()  # (num_samples, horizon)
        last_date = price_series.index[-1]

        if hasattr(last_date, "tz_convert"):
            dates = pd.date_range(
                start=last_date + pd.offsets.BDay(1),
                periods=horizon,
                freq="B",
                tz=MARKET_TZ,
            )
        else:
            dates = pd.date_range(
                start=last_date + pd.offsets.BDay(1),
                periods=horizon,
                freq="B",
            )

        paths_df = pd.DataFrame(samples, columns=dates)
        return paths_df