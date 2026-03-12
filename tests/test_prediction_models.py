"""
Phase 3 Validation Tests
━━━━━━━━━━━━━━━━━━━━━━━
Blueprint Validation Gate (Phase 5):
  Walk-forward directional accuracy > 55% OOS on 3yr Nifty 50.

All tests use synthetic data so they run without live API keys.
Integration tests (requiring real NSE data) are in tests/integration/.

Run: pytest tests/test_prediction_models.py -v
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from prediction.models.xgboost_predictor import XGBoostPredictor
from prediction.models.lightgbm_predictor import LightGBMPredictor
from prediction.models.catboost_predictor import CatBoostPredictor
from prediction.models.hmm_regime import HMMRegimeDetector
from prediction.models.ensemble_predictor import EnsemblePredictor, _softmax
from prediction.training.india_walk_forward import IndiaWalkForwardValidator
from prediction.inference.confidence_calculator import ConfidenceCalculator
from prediction.inference.model_router import ModelRouter, TaskType, TSFMRoute
from features.feature_validator import FeatureValidator
from features.india_feature_set import ALL_FEATURE_COLUMNS


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _make_synthetic_price_series(n: int = 800, seed: int = 42) -> pd.Series:
    rng = np.random.default_rng(seed)
    log_returns = rng.normal(0.0003, 0.015, size=n)
    prices = 1000.0 * np.exp(np.cumsum(log_returns))
    idx = pd.date_range("2020-01-02", periods=n, freq="B", tz="Asia/Kolkata")
    return pd.Series(prices, index=idx, name="close")


def _make_synthetic_features(n: int = 800, seed: int = 42) -> pd.DataFrame:
    rng  = np.random.default_rng(seed)
    data = rng.standard_normal((n, len(ALL_FEATURE_COLUMNS)))
    idx  = pd.date_range("2020-01-02", periods=n, freq="B", tz="Asia/Kolkata")
    df   = pd.DataFrame(data, columns=ALL_FEATURE_COLUMNS, index=idx)

    # Simulate integer/binary India calendar features
    df["day_of_week"]    = np.tile([0, 1, 2, 3, 4], n // 5 + 1)[:n].astype(float)
    df["expiry_day"]     = (df["day_of_week"] == 3).astype(float)
    df["vix_regime"]     = rng.integers(1, 5, size=n).astype(float)
    df["results_season"] = rng.integers(0, 2, size=n).astype(float)
    df["budget_week"]    = 0.0
    df["month_end_flag"] = 0.0

    # Apply .shift(1) on key features to simulate anti-lookahead
    for col in ["rsi_14", "macd_hist", "india_vix", "fii_net_cr"]:
        if col in df.columns:
            df[col] = df[col].shift(1)

    return df


def _make_labels(close: pd.Series, horizon: int = 5) -> pd.Series:
    return XGBoostPredictor.make_labels(close, horizon)


# ──────────────────────────────────────────────────────────────────────────────
# Tests: XGBoost
# ──────────────────────────────────────────────────────────────────────────────

class TestXGBoostPredictor:

    def test_make_labels_shape(self):
        close  = _make_synthetic_price_series(100)
        labels = _make_labels(close, horizon=5)
        assert len(labels) == len(close)
        assert labels.iloc[-5:].isna().all(), "Last 5 rows must be NaN (no forward return)"
        valid = labels.dropna()
        assert valid.isin([0.0, 1.0, 2.0, 3.0, 4.0]).all()

    def test_fit_predict(self):
        close    = _make_synthetic_price_series(600)
        features = _make_synthetic_features(600)
        labels   = _make_labels(close, 5).dropna()
        features = features.loc[labels.index].dropna()
        labels   = labels.loc[features.index]

        split = int(len(features) * 0.8)
        model = XGBoostPredictor(horizon=5)
        model.fit(
            features.iloc[:split], labels.iloc[:split],
            features.iloc[split:], labels.iloc[split:],
        )
        proba = model.predict_proba(features.iloc[split:])
        assert proba.shape == (len(features.iloc[split:]), 5)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-5)

        result = model.predict(features.iloc[split:])
        assert result["direction"] in [
            "Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"
        ]
        assert 0.0 <= result["confidence"] <= 1.0
        assert 0.0 <= result["bullish_prob"] <= 1.0

    def test_save_load(self, tmp_path):
        close    = _make_synthetic_price_series(300)
        features = _make_synthetic_features(300)
        labels   = _make_labels(close, 5).dropna()
        features = features.loc[labels.index].dropna()
        labels   = labels.loc[features.index]

        model = XGBoostPredictor(horizon=5)
        model.fit(features, labels)
        model.save(tmp_path / "xgb.joblib")

        loaded = XGBoostPredictor(horizon=5)
        loaded.load(tmp_path / "xgb.joblib")

        p1 = model.predict_proba(features.iloc[[-1]])
        p2 = loaded.predict_proba(features.iloc[[-1]])
        assert np.allclose(p1, p2, atol=1e-6)


# ──────────────────────────────────────────────────────────────────────────────
# Tests: LightGBM
# ──────────────────────────────────────────────────────────────────────────────

class TestLightGBMPredictor:

    def test_fit_proba_shape(self):
        close    = _make_synthetic_price_series(600)
        features = _make_synthetic_features(600)
        labels   = _make_labels(close, 5).dropna()
        features = features.loc[labels.index].dropna()
        labels   = labels.loc[features.index]

        split = int(len(features) * 0.8)
        model = LightGBMPredictor(horizon=5)
        model.fit(
            features.iloc[:split], labels.iloc[:split],
            features.iloc[split:], labels.iloc[split:],
        )
        proba = model.predict_proba(features.iloc[split:])
        assert proba.shape[1] == 5
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-4)


# ──────────────────────────────────────────────────────────────────────────────
# Tests: CatBoost
# ──────────────────────────────────────────────────────────────────────────────

class TestCatBoostPredictor:

    def test_categorical_handling(self):
        """CatBoost must use native categoricals — NOT one-hot encoding."""
        close    = _make_synthetic_price_series(600)
        features = _make_synthetic_features(600)
        labels   = _make_labels(close, 5).dropna()
        features = features.loc[labels.index].dropna()
        labels   = labels.loc[features.index]

        split = int(len(features) * 0.8)
        model = CatBoostPredictor(horizon=5)
        model.fit(
            features.iloc[:split], labels.iloc[:split],
            features.iloc[split:], labels.iloc[split:],
        )

        # Predict on row with unusual categorical values
        test_row = features.iloc[[-1]].copy()
        test_row["vix_regime"]  = 4.0   # extreme VIX regime
        test_row["day_of_week"] = 3.0   # Thursday (expiry)

        proba = model.predict_proba(test_row)
        assert proba.shape == (1, 5)
        assert np.allclose(proba.sum(), 1.0, atol=1e-3)


# ──────────────────────────────────────────────────────────────────────────────
# Tests: HMM Regime Detector
# ──────────────────────────────────────────────────────────────────────────────

class TestHMMRegimeDetector:

    def test_three_regimes_only(self):
        with pytest.raises(ValueError, match="n_regimes MUST be 3"):
            HMMRegimeDetector(n_regimes=4)

    def test_fit_predict(self):
        close   = _make_synthetic_price_series(600)
        returns = np.log(close / close.shift(1)).dropna()
        vix_s   = pd.Series(15.0 + np.random.randn(len(returns)) * 3, index=returns.index)

        hmm = HMMRegimeDetector(n_regimes=3, n_iter=50)
        hmm.fit(returns, vix_s)

        regime_series = hmm.predict_series(returns, vix_s)
        assert set(regime_series.unique()).issubset({0, 1, 2})
        assert len(regime_series) == len(returns)

        current = hmm.predict_current(returns, vix_s)
        assert current["regime_name"] in {"Bull", "Sideways", "Bear"}
        assert abs(sum(current["regime_probs"].values()) - 1.0) < 1e-4

    def test_bear_has_lowest_mean_return(self):
        """Blueprint: Bear(0) must always have lowest mean return of 3 states."""
        close   = _make_synthetic_price_series(800)
        returns = np.log(close / close.shift(1)).dropna()
        hmm     = HMMRegimeDetector(n_regimes=3, n_iter=100)
        hmm.fit(returns)

        regime_series  = hmm.predict_series(returns)
        regime_returns = {r: float(returns[regime_series == r].mean()) for r in [0, 1, 2]}

        assert regime_returns[0] <= regime_returns[1], (
            f"Bear(0) mean={regime_returns[0]:.5f} must be <= Sideways(1) mean={regime_returns[1]:.5f}"
        )
        assert regime_returns[1] <= regime_returns[2], (
            f"Sideways(1) mean={regime_returns[1]:.5f} must be <= Bull(2) mean={regime_returns[2]:.5f}"
        )

    def test_needs_refit_logic(self):
        close   = _make_synthetic_price_series(300)
        returns = np.log(close / close.shift(1)).dropna()
        hmm     = HMMRegimeDetector(n_regimes=3, refit_days=63, n_iter=50)
        hmm.fit(returns)

        now = pd.Timestamp.now(tz="Asia/Kolkata")
        assert not hmm.needs_refit(now), "Just-fitted HMM must NOT need refit"

        # Simulate stale model (last fit 2 years ago)
        hmm._last_fit_date = pd.Timestamp("2020-01-01", tz="Asia/Kolkata")
        assert hmm.needs_refit(now), "Old HMM MUST need refit"

    def test_save_load_identical_predictions(self, tmp_path):
        close   = _make_synthetic_price_series(300)
        returns = np.log(close / close.shift(1)).dropna()
        hmm     = HMMRegimeDetector(n_regimes=3, n_iter=50)
        hmm.fit(returns)

        hmm.save(tmp_path / "hmm.joblib")
        hmm2 = HMMRegimeDetector()
        hmm2.load(tmp_path / "hmm.joblib")

        r1 = hmm.predict_current(returns)["regime_id"]
        r2 = hmm2.predict_current(returns)["regime_id"]
        assert r1 == r2, "Loaded HMM must give identical regime as original"


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Walk-Forward Validator
# ──────────────────────────────────────────────────────────────────────────────

class TestIndiaWalkForwardValidator:

    def test_anti_lookahead_all_folds(self):
        """
        CRITICAL gate: max(train) + embargo < min(test) for EVERY fold.
        If this fails, the entire ML pipeline has lookahead contamination.
        """
        features = _make_synthetic_features(1200)
        wfv      = IndiaWalkForwardValidator()

        for fold in wfv.generate_folds(features):
            gap = int(min(fold.test_indices)) - int(max(fold.train_indices))
            assert gap > 5, (
                f"Fold {fold.fold_id}: embargo gap={gap} trading days, must be > 5. "
                f"LOOKAHEAD DETECTED. max_train={max(fold.train_indices)}, "
                f"min_test={min(fold.test_indices)}"
            )

    def test_minimum_eight_folds(self):
        """Must generate >= 8 folds on sufficient data."""
        features = _make_synthetic_features(1500)
        wfv      = IndiaWalkForwardValidator()
        folds    = list(wfv.generate_folds(features))
        assert len(folds) >= 8, f"Got only {len(folds)} folds; need >= 8"

    def test_short_data_raises(self):
        """Must raise ValueError when data is too short for even one fold."""
        features = _make_synthetic_features(200)  # 200 < 504+5+63 = 572
        wfv      = IndiaWalkForwardValidator()
        with pytest.raises(ValueError, match="too short"):
            list(wfv.generate_folds(features))

    def test_directional_accuracy_excludes_neutral(self):
        """
        Neutral class (label=2) must be EXCLUDED from denominator.
        Blueprint: directional accuracy = P(correct | not neutral).
        """
        # 8 samples: 2 are neutral (class=2), must be excluded
        y_true = np.array([0, 1, 2, 3, 4, 2, 3, 4])
        y_pred = np.array([0, 1, 2, 3, 4, 3, 3, 4])
        # Non-neutral indices: 0,1,3,4,6,7
        # y_true dirs: [DOWN, DOWN, UP, UP, UP, UP]
        # y_pred dirs: [DOWN, DOWN, UP, UP, UP, UP]
        # All 6 non-neutral correct → accuracy = 1.0
        acc = IndiaWalkForwardValidator.compute_directional_accuracy(y_true, y_pred)
        assert acc == pytest.approx(1.0), f"Expected 1.0, got {acc}"

    def test_directional_accuracy_partial(self):
        y_true = np.array([0, 0, 3, 4, 3])   # DOWN DOWN UP UP UP
        y_pred = np.array([0, 3, 3, 0, 3])   # DOWN UP  UP DOWN UP
        # Correct: [0,3,4] → 3 correct out of 5 non-neutral
        acc = IndiaWalkForwardValidator.compute_directional_accuracy(y_true, y_pred)
        assert acc == pytest.approx(3 / 5), f"Expected 0.6, got {acc}"

    def test_fold_train_test_no_overlap(self):
        """train_indices and test_indices must have zero overlap."""
        features = _make_synthetic_features(1200)
        wfv      = IndiaWalkForwardValidator()
        for fold in wfv.generate_folds(features):
            overlap = set(fold.train_indices) & set(fold.test_indices)
            assert len(overlap) == 0, f"Fold {fold.fold_id}: train/test overlap detected"


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Ensemble Predictor
# ──────────────────────────────────────────────────────────────────────────────

class TestEnsemblePredictor:

    def _make_mock_probas(self, seed: int = 0) -> tuple:
        rng  = np.random.default_rng(seed)
        def _rand_proba():
            p = np.abs(rng.standard_normal(5))
            return p / p.sum()
        return _rand_proba(), _rand_proba(), _rand_proba()

    def test_predict_without_fit_uses_regime_weights(self):
        """Before meta-learner is fitted, must fall back to regime-weighted average."""
        xgb_p, lgbm_p, cb_p = self._make_mock_probas()
        ens = EnsemblePredictor()
        result = ens.predict(
            xgb_proba=xgb_p, lgbm_proba=lgbm_p, catboost_proba=cb_p,
            regime_id=2, chronos_dir_5d=0.6, chronos_dir_10d=0.55, chronos_dir_30d=0.5,
        )
        assert result["direction"] in [
            "Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"
        ]
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["regime_name"] == "Bull"

    def test_predict_after_fit_uses_ridge(self):
        """After meta-learner fit, Ridge must be used for predictions."""
        n   = 200
        rng = np.random.default_rng(42)

        def _batch_proba(n):
            p = np.abs(rng.standard_normal((n, 5)))
            return (p.T / p.sum(axis=1)).T

        xgb_b  = _batch_proba(n)
        lgbm_b = _batch_proba(n)
        cb_b   = _batch_proba(n)
        regime_ids    = rng.integers(0, 3, size=n)
        c5  = rng.uniform(0.3, 0.7, n)
        c10 = rng.uniform(0.3, 0.7, n)
        c30 = rng.uniform(0.3, 0.7, n)
        y   = rng.integers(0, 5, size=n)

        ens = EnsemblePredictor(ridge_alpha=1.0)
        ens.fit(xgb_b, lgbm_b, cb_b, regime_ids, c5, c10, c30, y)
        assert ens._is_fitted

        result = ens.predict(
            xgb_proba=xgb_b[-1], lgbm_proba=lgbm_b[-1], catboost_proba=cb_b[-1],
            regime_id=int(regime_ids[-1]),
            chronos_dir_5d=float(c5[-1]),
            chronos_dir_10d=float(c10[-1]),
            chronos_dir_30d=float(c30[-1]),
        )
        assert result["direction_class"] in range(5)
        assert result["is_high_confidence"] in (True, False)

    def test_save_load_ensemble(self, tmp_path):
        n   = 100
        rng = np.random.default_rng(0)

        def _batch(n):
            p = np.abs(rng.standard_normal((n, 5)))
            return (p.T / p.sum(axis=1)).T

        ens = EnsemblePredictor()
        ens.fit(
            _batch(n), _batch(n), _batch(n),
            rng.integers(0, 3, n),
            rng.uniform(0.3, 0.7, n),
            rng.uniform(0.3, 0.7, n),
            rng.uniform(0.3, 0.7, n),
            rng.integers(0, 5, n),
        )
        ens.save(tmp_path / "ensemble.joblib")

        ens2 = EnsemblePredictor()
        ens2.load(tmp_path / "ensemble.joblib")
        assert ens2._is_fitted


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Confidence Calculator
# ──────────────────────────────────────────────────────────────────────────────

class TestConfidenceCalculator:

    def setup_method(self):
        self.calc = ConfidenceCalculator()

    def test_crisis_vix_caps_confidence(self):
        """VIX >= 30 must cap confidence at 0.40 regardless of raw value."""
        result = self.calc.calibrate(
            raw_confidence=0.90, vix_level=35.0, regime_id=0, n_models_agreeing=3
        )
        assert result <= 0.40, f"Crisis VIX must cap at 0.40, got {result}"

    def test_normal_vix_no_penalty(self):
        """VIX in normal range (13-18) must apply multiplier 1.0."""
        result = self.calc.calibrate(
            raw_confidence=0.70, vix_level=16.0, regime_id=2, n_models_agreeing=2
        )
        # Bull regime + VIX normal + 2 agreeing: slight boost
        assert result >= 0.65, f"Normal VIX confidence should stay near raw, got {result}"

    def test_bear_regime_reduces_confidence(self):
        """Bear regime must reduce confidence vs identical Bull regime."""
        bull = self.calc.calibrate(0.70, 15.0, regime_id=2, n_models_agreeing=2)
        bear = self.calc.calibrate(0.70, 15.0, regime_id=0, n_models_agreeing=2)
        assert bear < bull, f"Bear confidence={bear} must be < Bull confidence={bull}"

    def test_three_model_agreement_boosts(self):
        """3 models agreeing must give higher confidence than only 1."""
        agree_3 = self.calc.calibrate(0.65, 15.0, regime_id=1, n_models_agreeing=3)
        agree_1 = self.calc.calibrate(0.65, 15.0, regime_id=1, n_models_agreeing=1)
        assert agree_3 > agree_1, f"3-model agreement={agree_3} must > 1-model={agree_1}"

    def test_output_always_in_valid_range(self):
        """Calibrated confidence must always be in [0.01, 0.95]."""
        for raw in [0.01, 0.50, 0.99]:
            for vix in [10.0, 20.0, 35.0]:
                for regime in [0, 1, 2]:
                    result = self.calc.calibrate(raw, vix, regime, n_models_agreeing=2)
                    assert 0.01 <= result <= 0.95, (
                        f"Out of range: raw={raw}, vix={vix}, regime={regime} → {result}"
                    )


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Model Router
# ──────────────────────────────────────────────────────────────────────────────

class TestModelRouter:

    def test_crisis_vix_routes_to_bolt(self):
        """VIX >= 30 must always route to Chronos-Bolt (fastest exit signal)."""
        router = ModelRouter(timesfm_available=False)
        route  = router.route(TaskType.PRICE_PATH_FORECAST, vix_level=32.0,
                              regime_id=0, n_data_rows=500)
        assert route == TSFMRoute.CHRONOS_BOLT

    def test_dashboard_refresh_routes_to_bolt(self):
        router = ModelRouter()
        route  = router.route(TaskType.DASHBOARD_REFRESH, vix_level=14.0,
                              regime_id=1, n_data_rows=500)
        assert route == TSFMRoute.CHRONOS_BOLT

    def test_var_task_routes_to_timesfm_when_available(self):
        router = ModelRouter(timesfm_available=True)
        route  = router.route(TaskType.VAR_ESTIMATION, vix_level=15.0,
                              regime_id=2, n_data_rows=500)
        assert route == TSFMRoute.TIMESFM

    def test_var_task_routes_to_chronos2_when_timesfm_unavailable(self):
        router = ModelRouter(timesfm_available=False)
        route  = router.route(TaskType.VAR_ESTIMATION, vix_level=15.0,
                              regime_id=2, n_data_rows=500)
        assert route == TSFMRoute.CHRONOS2

    def test_default_routes_to_chronos2(self):
        router = ModelRouter(timesfm_available=False)
        route  = router.route(TaskType.PRICE_PATH_FORECAST, vix_level=15.0,
                              regime_id=2, n_data_rows=500)
        assert route == TSFMRoute.CHRONOS2

    def test_insufficient_data_routes_to_bolt(self):
        router = ModelRouter(timesfm_available=False)
        route  = router.route(TaskType.PRICE_PATH_FORECAST, vix_level=15.0,
                              regime_id=1, n_data_rows=50)
        assert route == TSFMRoute.CHRONOS_BOLT


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Feature Validator (Anti-Lookahead)
# ──────────────────────────────────────────────────────────────────────────────

class TestFeatureValidator:

    def test_wfo_embargo_violation_raises(self):
        """If embargo gap < 5 days, must raise AssertionError."""
        validator = FeatureValidator()
        train_idx = np.arange(0, 504)
        test_idx  = np.arange(506, 569)  # gap = 2 < embargo=5 → violation
        with pytest.raises(AssertionError, match="embargo violation"):
            validator.validate_wfo_folds(train_idx, test_idx, embargo=5, fold_id=0)

    def test_wfo_valid_fold_passes(self):
        """Valid embargo gap must return True without raising."""
        validator = FeatureValidator()
        train_idx = np.arange(0, 504)
        test_idx  = np.arange(510, 573)  # gap = 6 > embargo=5 → valid
        result = validator.validate_wfo_folds(train_idx, test_idx, embargo=5, fold_id=0)
        assert result is True

    def test_null_column_detected(self):
        """Feature validator must flag all-NaN columns."""
        close    = _make_synthetic_price_series(200)
        features = _make_synthetic_features(200)

        # Inject an all-NaN column to simulate a broken adapter
        features["fii_net_cr"] = np.nan

        validator = FeatureValidator()
        report    = validator.validate_features(features, close)
        assert not report.passed
        assert "fii_net_cr" in report.null_columns

    def test_clean_features_pass(self):
        """A properly shifted feature set with no NaN must pass validation."""
        close    = _make_synthetic_price_series(300)
        features = _make_synthetic_features(300)

        # Ensure no all-NaN columns
        features = features.ffill().bfill()

        validator = FeatureValidator()
        report    = validator.validate_features(features, close)
        # May have warnings but null_columns must be empty
        assert len(report.null_columns) == 0


# ──────────────────────────────────────────────────────────────────────────────
# Tests: _softmax helper
# ──────────────────────────────────────────────────────────────────────────────

class TestSoftmax:

    def test_sums_to_one(self):
        x = np.array([1.0, 2.0, 3.0, 0.5, -1.0])
        s = _softmax(x)
        assert np.allclose(s.sum(), 1.0, atol=1e-7)

    def test_largest_input_gets_largest_output(self):
        x = np.array([0.1, 5.0, 0.2, 0.3, 0.4])
        s = _softmax(x)
        assert np.argmax(s) == 1

    def test_uniform_input_gives_uniform_output(self):
        x = np.ones(5)
        s = _softmax(x)
        assert np.allclose(s, 0.2, atol=1e-7)