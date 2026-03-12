"""
HMM Market Regime Detector
━━━━━━━━━━━━━━━━━━━━━━━━━
GaussianHMM with 3 components: Bull / Sideways / Bear
Fitted on Nifty 50 daily returns + India VIX.

Blueprint requirements:
  - 3 components ONLY (Bull/Bear/Sideways)
  - Refit every 63 trading days (prevents stale regime labels)
  - Gates which model weights are active in ensemble

Regime label assignment (post-fit, sorted by mean return):
  Lowest mean  → 0 = Bear
  Middle mean  → 1 = Sideways
  Highest mean → 2 = Bull
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import structlog
from pathlib import Path
from typing import Optional

from hmmlearn.hmm import GaussianHMM

from config.constants import (
    HMM_N_REGIMES,
    HMM_REFIT_EVERY_DAYS,
    MARKET_TZ,
)

logger = structlog.get_logger(__name__)

REGIME_NAMES = {0: "Bear", 1: "Sideways", 2: "Bull"}
REGIME_COLORS = {0: "#e74c3c", 1: "#f39c12", 2: "#27ae60"}


class HMMRegimeDetector:
    """
    GaussianHMM regime detector. Fits on Nifty 50 returns + VIX.
    Used to gate model weights in the ensemble predictor.
    """

    def __init__(
        self,
        n_regimes: int = HMM_N_REGIMES,
        refit_days: int = HMM_REFIT_EVERY_DAYS,
        n_iter: int = 200,
        covariance_type: str = "full",
        random_state: int = 42,
    ):
        """
        Args:
            n_regimes:       Number of hidden states (MUST be 3 per blueprint)
            refit_days:      Refit model after this many trading days
            n_iter:          EM iterations for HMM fitting
            covariance_type: "full" | "diag" | "tied" | "spherical"
            random_state:    Reproducibility
        """
        if n_regimes != 3:
            raise ValueError(
                f"n_regimes MUST be 3 (Bull/Sideways/Bear). Got {n_regimes}."
            )
        self.n_regimes       = n_regimes
        self.refit_days      = refit_days
        self.n_iter          = n_iter
        self.covariance_type = covariance_type
        self.random_state    = random_state

        self._model: Optional[GaussianHMM] = None
        self._label_map: dict[int, int] = {}  # raw HMM state → sorted regime
        self._last_fit_date: Optional[pd.Timestamp] = None
        self._is_fitted = False

    def _build_features(
        self,
        nifty_returns: pd.Series,
        vix_series: Optional[pd.Series] = None,
    ) -> np.ndarray:
        """
        Build feature matrix for HMM.
        Features: [daily_return, log_volatility (rolling 5-day), vix_level (optional)]
        """
        ret   = nifty_returns.fillna(0.0).values
        vol5  = nifty_returns.rolling(5).std().fillna(method="bfill").values
        log_vol5 = np.log1p(np.abs(vol5))

        if vix_series is not None and not vix_series.empty:
            vix_aligned = vix_series.reindex(nifty_returns.index).ffill().fillna(15.0)
            vix_norm    = vix_aligned.values / 100.0  # normalise VIX to ~[0.08, 0.4]
            features    = np.column_stack([ret, log_vol5, vix_norm])
        else:
            features = np.column_stack([ret, log_vol5])

        return features.astype(np.float64)

    def fit(
        self,
        nifty_returns: pd.Series,
        vix_series: Optional[pd.Series] = None,
    ) -> "HMMRegimeDetector":
        """
        Fit GaussianHMM on Nifty returns.

        Args:
            nifty_returns: Daily log returns of Nifty 50 (DatetimeIndex)
            vix_series:    India VIX daily series (same index; optional but recommended)
        """
        X = self._build_features(nifty_returns, vix_series)

        model = GaussianHMM(
            n_components=self.n_regimes,
            covariance_type=self.covariance_type,
            n_iter=self.n_iter,
            random_state=self.random_state,
        )
        model.fit(X)

        # ── Sort states by mean return (ascending) ─────────────────────────
        # HMM states are arbitrary; we sort to make labels reproducible:
        # State with lowest mean return → 0 (Bear)
        # State with middle mean return → 1 (Sideways)
        # State with highest mean return → 2 (Bull)
        mean_returns = model.means_[:, 0]  # column 0 = daily return
        sorted_idx   = np.argsort(mean_returns)  # ascending
        self._label_map = {int(sorted_idx[i]): i for i in range(self.n_regimes)}

        self._model         = model
        self._is_fitted     = True
        self._last_fit_date = nifty_returns.index[-1] if hasattr(nifty_returns.index, "__len__") else pd.Timestamp.now(tz=MARKET_TZ)

        # Log regime statistics
        for raw_state, mapped in self._label_map.items():
            logger.info(
                "hmm.regime_stats",
                regime=REGIME_NAMES[mapped],
                mean_return=round(float(mean_returns[raw_state]) * 100, 3),
                std_return=round(float(np.sqrt(model.covars_[raw_state][0, 0])) * 100, 3),
            )

        return self

    def predict_series(
        self,
        nifty_returns: pd.Series,
        vix_series: Optional[pd.Series] = None,
    ) -> pd.Series:
        """
        Predict regime labels for entire series.

        Returns:
            Series with integer labels {0=Bear, 1=Sideways, 2=Bull}
        """
        if not self._is_fitted:
            raise RuntimeError("HMM not fitted. Call fit() first.")

        X = self._build_features(nifty_returns, vix_series)
        raw_states = self._model.predict(X)
        mapped     = np.array([self._label_map[s] for s in raw_states])
        return pd.Series(mapped, index=nifty_returns.index, name="market_regime")

    def predict_current(
        self,
        nifty_returns: pd.Series,
        vix_series: Optional[pd.Series] = None,
    ) -> dict:
        """
        Predict current regime (last row).

        Returns:
            {
              "regime_id":   int  (0=Bear, 1=Sideways, 2=Bull)
              "regime_name": str  ("Bear" | "Sideways" | "Bull")
              "regime_probs": list[float] (probabilities for each regime)
            }
        """
        if not self._is_fitted:
            raise RuntimeError("HMM not fitted.")

        X          = self._build_features(nifty_returns, vix_series)
        raw_states = self._model.predict(X)
        log_probs  = self._model.predict_proba(X)

        current_raw   = raw_states[-1]
        current_mapped = self._label_map[current_raw]

        # Map probability columns to sorted regime labels
        probs = [0.0, 0.0, 0.0]
        for raw_state, mapped in self._label_map.items():
            probs[mapped] = float(log_probs[-1, raw_state])

        return {
            "regime_id":   current_mapped,
            "regime_name": REGIME_NAMES[current_mapped],
            "regime_probs": {REGIME_NAMES[i]: round(probs[i], 4) for i in range(3)},
        }

    def needs_refit(self, current_date: pd.Timestamp) -> bool:
        """Returns True if model should be refit (>= refit_days since last fit)."""
        if not self._is_fitted or self._last_fit_date is None:
            return True
        # Convert both to naive for comparison
        last = self._last_fit_date
        if hasattr(last, "tzinfo") and last.tzinfo is not None:
            last = last.tz_localize(None)
        now = current_date
        if hasattr(now, "tzinfo") and now.tzinfo is not None:
            now = now.tz_localize(None)
        delta_days = (now - last).days
        # Approximate trading days (multiply calendar days by ~5/7)
        trading_days_approx = int(delta_days * 5 / 7)
        return trading_days_approx >= self.refit_days

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump({
            "model":          self._model,
            "label_map":      self._label_map,
            "last_fit_date":  self._last_fit_date,
            "n_regimes":      self.n_regimes,
            "refit_days":     self.refit_days,
            "n_iter":         self.n_iter,
            "covariance_type": self.covariance_type,
        }, path)
        logger.info("hmm.saved", path=str(path))

    def load(self, path: Path) -> None:
        data = joblib.load(Path(path))
        self._model          = data["model"]
        self._label_map      = data["label_map"]
        self._last_fit_date  = data["last_fit_date"]
        self.n_regimes       = data["n_regimes"]
        self.refit_days      = data["refit_days"]
        self.n_iter          = data["n_iter"]
        self.covariance_type = data["covariance_type"]
        self._is_fitted      = True
        logger.info("hmm.loaded", path=str(path))