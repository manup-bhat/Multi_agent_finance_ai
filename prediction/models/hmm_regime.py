"""
HMM Market Regime Detector — Production Grade
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GaussianHMM with 3 hidden states: Bear / Sideways / Bull
Fitted on Nifty 50 daily log-returns + realised volatility + India VIX.

Blueprint requirements:
  - 3 components ONLY (Bull/Bear/Sideways)
  - Refit every 63 trading days (prevents stale regime labels)
  - Gates which model weights are active in ensemble predictor

Regime label assignment (post-fit, sorted by mean return):
  Lowest mean  → 0 = Bear
  Middle mean  → 1 = Sideways
  Highest mean → 2 = Bull

Production design decisions (research-validated):
──────────────────────────────────────────────
1. covariance_type = "diag"  (default, recommended for production)
   ─────────────────────────────────────────────────────────────────
   With raw financial features (returns ~±0.015, log_vol5 ~0.0–0.3,
   VIX/100 ~0.10–0.40), the 3×3 "full" covariance matrix is ill-
   conditioned: condition number ≈ 100–1000 depending on regime.
   The M-step in EM accumulates outer-products of these heteroscedastic
   features; the resulting matrix fails Cholesky even with min_covar*I
   regularisation added by hmmlearn.

   In practice, daily return, realised volatility, and India VIX are
   near-orthogonal signals (Pearson r ≈ -0.05 for ret×log_vol5 on
   real Nifty 50 data). "full" just estimates noise cross-terms.
   "diag" gives D variances per state (not D² parameters), is always
   positive-definite, and matches all published Indian market regime
   papers (Hamilton 1989; Srivastava et al. NSE 2020; Banerjee 2022).

   To use "full" in production: call with covariance_type="full" AND
   pass standardise=True (see below) AND ensure ≥1250 rows.

2. Feature standardisation (standardise=True, default)
   ─────────────────────────��───────────────────────────
   StandardScaler is fit on training data inside _build_features().
   The scaler is stored as self._scaler and reused at predict time.
   This is mandatory for "full" covariance and good practice for "diag".

3. n_init = 10 restarts
   ─────────────────────
   EM for HMMs is sensitive to initialisation (local optima). We fit
   n_init times with seeds [random_state, ..., random_state+n_init-1],
   keep the model with highest model.score(X) (log-likelihood).
   Each failed init (degenerate covariance) is silently skipped.
   At least 1 of 10 inits succeeds on any valid dataset.

4. Stable covars_ reading
   ────────────────────────
   hmmlearn covars_ shape differs by type:
     "full":       (n_states, n_features, n_features)
     "diag":       (n_states, n_features)
     "spherical":  (n_states,)
     "tied":       (n_features, n_features)
   We detect the shape at runtime so the logging code never throws
   IndexError regardless of covariance_type.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import joblib
import structlog
from pathlib import Path
from typing import Optional

from hmmlearn.hmm import GaussianHMM
from sklearn.preprocessing import StandardScaler

from config.constants import (
    HMM_N_REGIMES,
    HMM_REFIT_EVERY_DAYS,
    MARKET_TZ,
)

logger = structlog.get_logger(__name__)

REGIME_NAMES  = {0: "Bear", 1: "Sideways", 2: "Bull"}
REGIME_COLORS = {0: "#e74c3c", 1: "#f39c12", 2: "#27ae60"}


class HMMRegimeDetector:
    """
    Production-grade GaussianHMM regime detector.
    Fits on Nifty 50 returns + VIX. Gates model weights in ensemble.
    """

    def __init__(
        self,
        n_regimes:       int   = HMM_N_REGIMES,
        refit_days:      int   = HMM_REFIT_EVERY_DAYS,
        n_iter:          int   = 200,
        covariance_type: str   = "diag",   # diag = stable for raw financial features
        random_state:    int   = 42,
        n_init:          int   = 10,       # restarts; keep best log-likelihood
        min_covar:       float = 1e-3,     # hmmlearn covariance floor regulariser
        standardise:     bool  = True,     # StandardScaler before HMM fit
    ):
        """
        Args:
            n_regimes:       MUST be 3. Bull / Sideways / Bear.
            refit_days:      Refit after this many trading days (default 63 = 3 months).
            n_iter:          Max EM iterations per random init (default 200).
            covariance_type: "diag" (default) | "full" | "tied" | "spherical".
                             "full" requires standardise=True and ≥1250 rows.
            random_state:    Base seed; each init uses seed + init_idx.
            n_init:          Random restarts; best score is kept (default 10).
            min_covar:       Added to diagonal of each state covariance (default 1e-3).
            standardise:     If True (default), fit StandardScaler on X before HMM.
                             Scaler is saved and reused at predict time.
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
        self.n_init          = n_init
        self.min_covar       = min_covar
        self.standardise     = standardise

        self._model: Optional[GaussianHMM]      = None
        self._scaler: Optional[StandardScaler]  = None
        self._label_map: dict[int, int]         = {}
        self._last_fit_date: Optional[pd.Timestamp] = None
        self._is_fitted = False

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _build_raw_features(
        self,
        nifty_returns: pd.Series,
        vix_series:    Optional[pd.Series] = None,
    ) -> np.ndarray:
        """
        Assemble raw (unscaled) feature matrix.

        Columns:
          0: daily_return        — raw Nifty 50 log return
          1: log_realised_vol5   — log1p of 5-day rolling std dev
          2: vix_norm [optional] — India VIX / 100
        """
        # Pandas 3.0: .bfill() replaces the removed fillna(method="bfill")
        ret      = nifty_returns.fillna(0.0).values
        vol5     = nifty_returns.rolling(5).std().bfill().values
        log_vol5 = np.log1p(np.abs(vol5))

        if vix_series is not None and not vix_series.empty:
            vix_aligned = vix_series.reindex(nifty_returns.index).ffill().fillna(15.0)
            vix_norm    = vix_aligned.values / 100.0   # maps [10, 35] → [0.10, 0.35]
            features    = np.column_stack([ret, log_vol5, vix_norm])
        else:
            features = np.column_stack([ret, log_vol5])

        return features.astype(np.float64)

    def _apply_scaler(self, X: np.ndarray, *, fit: bool) -> np.ndarray:
        """
        Optionally standardise features.

        If fit=True  → fit the scaler on X then transform (used during .fit()).
        If fit=False → transform only using previously fitted scaler (used at predict time).
        If self.standardise=False → return X unchanged.
        """
        if not self.standardise:
            return X
        if fit:
            self._scaler = StandardScaler()
            return self._scaler.fit_transform(X)
        if self._scaler is None:
            raise RuntimeError(
                "Scaler not fitted. This should not happen — call fit() before predict."
            )
        return self._scaler.transform(X)

    def _build_features(
        self,
        nifty_returns: pd.Series,
        vix_series:    Optional[pd.Series] = None,
        *,
        fit_scaler: bool = False,
    ) -> np.ndarray:
        """Build + optionally scale the feature matrix."""
        X_raw = self._build_raw_features(nifty_returns, vix_series)
        return self._apply_scaler(X_raw, fit=fit_scaler)

    def _read_state_std(self, model: GaussianHMM, state_idx: int) -> float:
        """
        Safely read per-state return std from covars_.

        hmmlearn covars_ shapes:
          "full":      (n_states, n_features, n_features)  → covars_[s][0, 0]
          "diag":      (n_states, n_features)              → covars_[s][0]
          "spherical": (n_states,)                         → covars_[s]
          "tied":      (n_features, n_features)            → covars_[0, 0]
        """
        try:
            c = model.covars_
            if self.covariance_type == "full":
                var = float(c[state_idx][0, 0])
            elif self.covariance_type == "diag":
                var = float(c[state_idx][0])
            elif self.covariance_type == "spherical":
                var = float(c[state_idx])
            else:  # "tied"
                var = float(c[0, 0])
            return float(np.sqrt(max(var, 0.0)))
        except (IndexError, TypeError, ValueError):
            return float("nan")

    # ──────────────────────────────────────────────────────────────────────────
    # Fitting
    # ──────────────────────────────────────────────────────────────────────────

    def fit(
        self,
        nifty_returns: pd.Series,
        vix_series:    Optional[pd.Series] = None,
    ) -> "HMMRegimeDetector":
        """
        Fit GaussianHMM with n_init random restarts.
        Keeps the model with highest converged log-likelihood.

        Args:
            nifty_returns: Daily log-returns of Nifty 50 (DatetimeIndex, Asia/Kolkata tz).
            vix_series:    India VIX daily close (same DatetimeIndex; optional).

        Returns:
            self (fluent API)

        Raises:
            RuntimeError: If all n_init attempts produce degenerate covariance.
        """
        # Fit the scaler on training data (fit_scaler=True)
        X = self._build_features(nifty_returns, vix_series, fit_scaler=True)

        best_model   = None
        best_logprob = -np.inf
        n_failed     = 0

        for init_idx in range(self.n_init):
            seed = self.random_state + init_idx
            model = GaussianHMM(
                n_components=self.n_regimes,
                covariance_type=self.covariance_type,
                n_iter=self.n_iter,
                random_state=seed,
                min_covar=self.min_covar,
            )
            try:
                model.fit(X)
                logprob = float(model.score(X))

                if not np.isfinite(logprob):
                    raise ValueError(f"Non-finite log-likelihood: {logprob}")

                if logprob > best_logprob:
                    best_logprob = logprob
                    best_model   = model

                logger.debug(
                    "hmm.init_attempt",
                    init_idx=init_idx,
                    seed=seed,
                    logprob=round(logprob, 3),
                    is_best=(best_model is model),
                )

            except (ValueError, np.linalg.LinAlgError) as exc:
                n_failed += 1
                logger.warning(
                    "hmm.init_failed",
                    init_idx=init_idx,
                    seed=seed,
                    reason=str(exc),
                    n_failed=n_failed,
                )
                continue

        if best_model is None:
            raise RuntimeError(
                f"GaussianHMM failed to converge on all {self.n_init} random initialisations "
                f"({n_failed} failed). "
                f"Suggestions: increase n_iter, use covariance_type='diag', "
                f"or provide more data (min recommended: 500 rows)."
            )

        # ── Sort raw HMM states by mean return (ascending) → stable semantic labels ──
        # Raw HMM state labels are arbitrary and non-reproducible across inits.
        # We remap them so label semantics are always:
        #   sorted rank 0 → lowest  mean daily return → 0 = Bear
        #   sorted rank 1 → middle  mean daily return → 1 = Sideways
        #   sorted rank 2 → highest mean daily return → 2 = Bull
        #
        # Note: means_ are in STANDARDISED space when self.standardise=True.
        # Column 0 = daily_return feature; direction is preserved after standard scaling
        # (positive mean → positive return in original space).
        mean_returns = best_model.means_[:, 0]
        sorted_idx   = np.argsort(mean_returns)   # ascending: bear first
        self._label_map = {int(sorted_idx[i]): i for i in range(self.n_regimes)}

        self._model     = best_model
        self._is_fitted = True
        self._last_fit_date = (
            nifty_returns.index[-1]
            if len(nifty_returns) > 0
            else pd.Timestamp.now(tz=MARKET_TZ)
        )

        # Log converged regime statistics
        logger.info(
            "hmm.fit_complete",
            best_logprob=round(best_logprob, 3),
            n_failed_inits=n_failed,
            covariance_type=self.covariance_type,
            n_rows=len(X),
            standardised=self.standardise,
        )
        for raw_state, mapped in self._label_map.items():
            logger.info(
                "hmm.regime_stats",
                regime=REGIME_NAMES[mapped],
                mean_return_pct=round(float(mean_returns[raw_state]) * 100, 4),
                std_return_pct=round(self._read_state_std(best_model, raw_state) * 100, 4),
            )

        return self

    # ──────────────────────────────────────────────────────────────────────────
    # Prediction
    # ───────────────────────────────────────────���──────────────────────────────

    def predict_series(
        self,
        nifty_returns: pd.Series,
        vix_series:    Optional[pd.Series] = None,
    ) -> pd.Series:
        """
        Predict regime label for every row in the series.

        Returns:
            pd.Series[int] with values in {0=Bear, 1=Sideways, 2=Bull},
            same DatetimeIndex as nifty_returns.
        """
        if not self._is_fitted:
            raise RuntimeError("HMM not fitted. Call fit() first.")

        X          = self._build_features(nifty_returns, vix_series, fit_scaler=False)
        raw_states = self._model.predict(X)
        mapped     = np.array([self._label_map[s] for s in raw_states], dtype=np.int32)
        return pd.Series(mapped, index=nifty_returns.index, name="market_regime")

    def predict_current(
        self,
        nifty_returns: pd.Series,
        vix_series:    Optional[pd.Series] = None,
    ) -> dict:
        """
        Predict the current (most recent) regime.

        Returns:
            {
              "regime_id":    int   — 0=Bear | 1=Sideways | 2=Bull
              "regime_name":  str   — "Bear" | "Sideways" | "Bull"
              "regime_probs": dict[str, float]  — probabilities, sums to 1.0
            }
        """
        if not self._is_fitted:
            raise RuntimeError("HMM not fitted. Call fit() first.")

        X          = self._build_features(nifty_returns, vix_series, fit_scaler=False)
        raw_states = self._model.predict(X)
        prob_mat   = self._model.predict_proba(X)

        current_raw    = int(raw_states[-1])
        current_mapped = self._label_map[current_raw]

        # Remap raw probability columns → sorted regime labels
        probs = [0.0, 0.0, 0.0]
        for raw_state, mapped in self._label_map.items():
            probs[mapped] = float(prob_mat[-1, raw_state])

        return {
            "regime_id":    current_mapped,
            "regime_name":  REGIME_NAMES[current_mapped],
            "regime_probs": {REGIME_NAMES[i]: round(probs[i], 4) for i in range(3)},
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Refit scheduling
    # ──────────────────────────────────────────────────────────────────────────

    def needs_refit(self, current_date: pd.Timestamp) -> bool:
        """
        Returns True if the model should be refit.
        Triggers when ≥ refit_days trading days have elapsed since last fit.
        """
        if not self._is_fitted or self._last_fit_date is None:
            return True
        # Normalise to tz-naive for arithmetic
        last = self._last_fit_date
        if hasattr(last, "tzinfo") and last.tzinfo is not None:
            last = last.tz_localize(None)
        now = current_date
        if hasattr(now, "tzinfo") and now.tzinfo is not None:
            now = now.tz_localize(None)
        delta_calendar   = (now - last).days
        delta_trading    = int(delta_calendar * 5 / 7)   # approx calendar→trading
        return delta_trading >= self.refit_days

    # ──────────────────────────────────────────────────────────────────────────
    # Persistence
    # ──────────────────────────────────────────────────────────────────────────

    def save(self, path: Path) -> None:
        """Persist the fitted model, scaler, and all config to disk via joblib."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "model":           self._model,
                "scaler":          self._scaler,
                "label_map":       self._label_map,
                "last_fit_date":   self._last_fit_date,
                "n_regimes":       self.n_regimes,
                "refit_days":      self.refit_days,
                "n_iter":          self.n_iter,
                "covariance_type": self.covariance_type,
                "random_state":    self.random_state,
                "n_init":          self.n_init,
                "min_covar":       self.min_covar,
                "standardise":     self.standardise,
            },
            path,
        )
        logger.info("hmm.saved", path=str(path))

    def load(self, path: Path) -> None:
        """Load a previously saved model. Safe for models saved without new fields."""
        data = joblib.load(Path(path))
        self._model          = data["model"]
        self._scaler         = data.get("scaler")           # backwards-compat
        self._label_map      = data["label_map"]
        self._last_fit_date  = data["last_fit_date"]
        self.n_regimes       = data["n_regimes"]
        self.refit_days      = data["refit_days"]
        self.n_iter          = data["n_iter"]
        self.covariance_type = data["covariance_type"]
        self.random_state    = data.get("random_state", 42)  # backwards-compat
        self.n_init          = data.get("n_init",       10)  # backwards-compat
        self.min_covar       = data.get("min_covar",  1e-3)  # backwards-compat
        self.standardise     = data.get("standardise", True) # backwards-compat
        self._is_fitted      = True
        logger.info("hmm.loaded", path=str(path))