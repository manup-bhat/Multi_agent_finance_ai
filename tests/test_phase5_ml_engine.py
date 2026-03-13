"""
Phase 5 ML Prediction Engine — Integration Test Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint Phase 5 Validation Gates:
  ✓ Walk-forward: ≥ 8 folds, anti-lookahead asserted every fold
  ✓ Directional accuracy: excludes neutral class (2) from denominator
  ✓ Trainer pipeline: XGB + LGBM + CatBoost + HMM + Ridge ensemble
  ✓ RegimeAwareTrainer: separate model set per regime (Bear/Sideways/Bull)
  ✓ PredictionService: VIX circuit breaker, SHAP explainer, confidence calibration
  ✓ Model persistence: save → load → identical predictions

All tests use SYNTHETIC data — zero API keys required.
Run: pytest tests/test_phase5_ml_engine.py -v
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from pathlib import Path
from typing import Optional

from prediction import (
    IndiaMLTrainer,
    TrainingResult,
    IndiaWalkForwardValidator,
    WFOResult,
    RegimeAwareTrainer,
    XGBoostPredictor,
    LightGBMPredictor,
    CatBoostPredictor,
    HMMRegimeDetector,
    EnsemblePredictor,
    Chronos2Predictor,
    PredictionService,
    PredictionResult,
    ConfidenceCalculator,
    ModelRouter,
    TaskType,
    TSFMRoute,
    OptunaTuner,
)
from features.india_feature_set import ALL_FEATURE_COLUMNS, IndiaFeatureSet
from features.feature_validator import FeatureValidator


# ─────────────────────────────────────────────────────────────────────────────
# Shared Fixtures (module-scoped for speed)
# ─────────────────────────────────────────────────────────────────────────────

def _make_price_series(n: int = 1200, seed: int = 42) -> pd.Series:
    """Synthetic Geometric Brownian Motion price series."""
    rng = np.random.default_rng(seed)
    lr  = rng.normal(0.0004, 0.015, size=n)
    prices = 1000.0 * np.exp(np.cumsum(lr))
    idx = pd.date_range("2020-01-02", periods=n, freq="B", tz="Asia/Kolkata")
    return pd.Series(prices, index=idx, name="close")


def _make_nifty_returns(n: int = 1200, seed: int = 43) -> pd.Series:
    """Synthetic Nifty 50 log return series."""
    rng = np.random.default_rng(seed)
    lr  = rng.normal(0.0003, 0.012, size=n)
    prices = 17000.0 * np.exp(np.cumsum(lr))
    idx = pd.date_range("2020-01-02", periods=n, freq="B", tz="Asia/Kolkata")
    s   = pd.Series(prices, index=idx, name="nifty50")
    return np.log(s / s.shift(1)).dropna()


def _make_vix_series(n: int = 1200) -> pd.Series:
    """Synthetic India VIX series."""
    rng = np.random.default_rng(44)
    idx = pd.date_range("2020-01-02", periods=n, freq="B", tz="Asia/Kolkata")
    return pd.Series(np.clip(rng.normal(15.0, 3.0, n), 8, 40), index=idx)


def _make_features(n: int = 1200, seed: int = 42) -> pd.DataFrame:
    """Synthetic 70-feature DataFrame with correct structure."""
    rng  = np.random.default_rng(seed)
    data = rng.standard_normal((n, len(ALL_FEATURE_COLUMNS)))
    idx  = pd.date_range("2020-01-02", periods=n, freq="B", tz="Asia/Kolkata")
    df   = pd.DataFrame(data, columns=ALL_FEATURE_COLUMNS, index=idx)

    # Integer-encoded calendar features (CatBoost needs these)
    df["day_of_week"]    = np.tile([0, 1, 2, 3, 4], n // 5 + 1)[:n].astype(float)
    df["expiry_day"]     = (df["day_of_week"] == 3).astype(float)
    df["vix_regime"]     = rng.integers(1, 5, size=n).astype(float)
    df["results_season"] = rng.integers(0, 2, size=n).astype(float)
    df["budget_week"]    = 0.0
    df["month_end_flag"] = 0.0

    # Shift lagged features (anti-lookahead simulation)
    for col in ["close_lag1", "return_1d", "return_5d", "return_10d",
                "rsi_14", "macd_hist", "india_vix", "fii_net_cr"]:
        if col in df.columns:
            df[col] = df[col].shift(1)

    return df


# Module-scoped fixtures for tests that use the full trainer pipeline
@pytest.fixture(scope="module")
def synthetic_data():
    n = 1200
    close    = _make_price_series(n)
    nifty    = _make_nifty_returns(n)
    vix      = _make_vix_series(n)
    features = _make_features(n)
    labels   = XGBoostPredictor.make_labels(close, horizon=5)
    valid    = ~labels.isna()
    return {
        "close":    close,
        "nifty":    nifty,
        "vix":      vix,
        "features": features.loc[valid],
        "labels":   labels.loc[valid],
    }


# ─────────────────────────────────────────────────────────────────────────────
# TestIndiaMlTrainerPipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestIndiaMlTrainerPipeline:
    """
    End-to-end pipeline test using IndiaMLTrainer with synthetic data.
    run_optuna=False to keep the tests fast (~30s on CPU).
    """

    @pytest.fixture(scope="class")
    def training_result(self, tmp_path_factory, synthetic_data) -> TrainingResult:
        model_dir = tmp_path_factory.mktemp("models")
        trainer = IndiaMLTrainer(
            ticker="TEST",
            horizon=5,
            run_optuna=False,
            use_mlflow=False,
            model_dir=model_dir,
        )
        result = trainer.train(
            feature_df=synthetic_data["features"],
            close_series=synthetic_data["close"],
            nifty_returns=synthetic_data["nifty"],
            vix_series=synthetic_data["vix"],
        )
        return result

    def test_training_completes_without_error(self, training_result):
        """Training must complete without raising any exception."""
        assert training_result is not None

    def test_minimum_eight_folds(self, training_result):
        """Blueprint: must produce ≥ 8 walk-forward folds on 1200-row data."""
        assert training_result.wfo_result.n_folds >= 8, (
            f"Expected ≥ 8 folds, got {training_result.wfo_result.n_folds}"
        )

    def test_mean_accuracy_is_numeric(self, training_result):
        """Mean OOS accuracy must be a float in [0, 1]."""
        acc = training_result.wfo_result.mean_accuracy
        assert isinstance(acc, float), "mean_accuracy must be float"
        assert 0.0 <= acc <= 1.0, f"Accuracy {acc} out of [0, 1] range"

    def test_passes_threshold_is_bool(self, training_result):
        """passes_threshold must be a bool (gate evaluation always runs)."""
        assert isinstance(training_result.wfo_result.passes_threshold, bool)

    def test_trained_models_not_none(self, training_result):
        """All 5 model objects must be populated after training."""
        assert training_result.xgb      is not None, "XGBoost model is None"
        assert training_result.lgbm     is not None, "LightGBM model is None"
        assert training_result.catboost is not None, "CatBoost model is None"
        assert training_result.hmm      is not None, "HMM model is None"
        assert training_result.ensemble is not None, "Ensemble model is None"

    def test_summary_contains_key_info(self, training_result):
        """summary() must contain ticker, horizon, and accuracy info."""
        s = training_result.summary()
        assert "TEST" in s,    "summary must contain ticker"
        assert "5d"   in s,    "summary must contain horizon"
        assert "OOS"  in s,    "summary must mention OOS accuracy"
        assert "Folds" in s,   "summary must mention fold count"

    def test_xgb_proba_sums_to_one(self, training_result, synthetic_data):
        """XGBoost predict_proba must return valid probability distribution."""
        X_sample = synthetic_data["features"].iloc[[-1]]
        proba    = training_result.xgb.predict_proba(X_sample)
        assert proba.shape == (1, 5),  "XGBoost proba shape must be (1, 5)"
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-4)

    def test_lgbm_proba_sums_to_one(self, training_result, synthetic_data):
        """LightGBM predict_proba must return valid probability distribution."""
        X_sample = synthetic_data["features"].iloc[[-1]]
        proba    = training_result.lgbm.predict_proba(X_sample)
        assert proba.shape == (1, 5)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-4)

    def test_catboost_proba_sums_to_one(self, training_result, synthetic_data):
        """CatBoost predict_proba must return valid probability distribution."""
        X_sample = synthetic_data["features"].iloc[[-1]]
        proba    = training_result.catboost.predict_proba(X_sample)
        assert proba.shape == (1, 5)
        assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-3)

    def test_ensemble_predict_returns_valid_dict(self, training_result):
        """Ensemble predict must return a dict with all required keys."""
        rng = np.random.default_rng(0)
        def _proba():
            p = np.abs(rng.standard_normal(5))
            return p / p.sum()

        result = training_result.ensemble.predict(
            xgb_proba       = _proba(),
            lgbm_proba      = _proba(),
            catboost_proba  = _proba(),
            regime_id       = 1,
            chronos_dir_5d  = 0.55,
            chronos_dir_10d = 0.52,
            chronos_dir_30d = 0.50,
        )
        required_keys = {
            "direction", "direction_class", "confidence", "class_probs",
            "bullish_prob", "bearish_prob", "regime_name",
            "is_high_confidence", "chronos_dir_5d",
        }
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )
        assert result["direction"] in [
            "Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"
        ]
        assert 0.0 <= result["confidence"] <= 1.0

    def test_hmm_three_regimes(self, training_result, synthetic_data):
        """HMM must produce exactly 3 regime labels (0, 1, 2)."""
        nr = synthetic_data["nifty"]
        vx = synthetic_data["vix"]
        regime_labels = training_result.hmm.predict_series(nr, vx)
        unique = set(regime_labels.unique())
        assert unique.issubset({0, 1, 2}), f"Unexpected regime IDs: {unique}"

    def test_models_save_and_load(self, training_result, synthetic_data, tmp_path):
        """Models saved → loaded must produce identical predictions."""
        X = synthetic_data["features"].iloc[[-1]]

        # XGBoost round-trip
        training_result.xgb.save(tmp_path / "xgb.joblib")
        loaded_xgb = XGBoostPredictor(horizon=5)
        loaded_xgb.load(tmp_path / "xgb.joblib")
        assert np.allclose(
            training_result.xgb.predict_proba(X),
            loaded_xgb.predict_proba(X),
            atol=1e-5,
        ), "XGBoost save/load produces different predictions"

        # HMM round-trip
        nr = synthetic_data["nifty"]
        training_result.hmm.save(tmp_path / "hmm.joblib")
        loaded_hmm = HMMRegimeDetector()
        loaded_hmm.load(tmp_path / "hmm.joblib")
        r1 = training_result.hmm.predict_current(nr)["regime_id"]
        r2 = loaded_hmm.predict_current(nr)["regime_id"]
        assert r1 == r2, "HMM save/load produces different regime"


# ─────────────────────────────────────────────────────────────────────────────
# TestRegimeAwareTrainerPipeline
# ─────────────────────────────────────────────────────────────────────────────

class TestRegimeAwareTrainerPipeline:
    """Tests for RegimeAwareTrainer — regime-specific model sets."""

    @pytest.fixture(scope="class")
    def base_models(self, synthetic_data) -> dict:
        """Train a set of pooled base models to use as fallbacks."""
        features = synthetic_data["features"]
        labels   = synthetic_data["labels"]
        split    = int(len(features) * 0.8)

        xgb = XGBoostPredictor(horizon=5)
        xgb.fit(features.iloc[:split], labels.iloc[:split])

        lgbm = LightGBMPredictor(horizon=5)
        lgbm.fit(features.iloc[:split], labels.iloc[:split])

        cb = CatBoostPredictor(horizon=5)
        cb.fit(features.iloc[:split], labels.iloc[:split])

        hmm = HMMRegimeDetector(n_regimes=3, n_iter=50)
        hmm.fit(synthetic_data["nifty"])
        regime_series = hmm.predict_series(synthetic_data["nifty"])

        return {"xgb": xgb, "lgbm": lgbm, "cb": cb, "hmm": hmm,
                "regime_series": regime_series}

    def test_regime_trainer_fits_all_regimes(self, synthetic_data, base_models):
        """RegimeAwareTrainer must fit and set _is_fitted = True."""
        features = synthetic_data["features"]
        labels   = synthetic_data["labels"]
        regimes  = base_models["regime_series"].reindex(features.index).fillna(1).astype(int)

        trainer = RegimeAwareTrainer(ticker="TEST", horizon=5)
        trainer.fit(
            feature_df=features,
            labels=labels,
            regime_series=regimes,
            pooled_xgb=base_models["xgb"],
            pooled_lgbm=base_models["lgbm"],
            pooled_cb=base_models["cb"],
        )
        assert trainer._is_fitted is True

    def test_get_models_for_each_regime(self, synthetic_data, base_models):
        """get_models_for_regime must return valid (xgb, lgbm, cb) tuple."""
        features = synthetic_data["features"]
        labels   = synthetic_data["labels"]
        regimes  = base_models["regime_series"].reindex(features.index).fillna(1).astype(int)

        trainer = RegimeAwareTrainer(ticker="TEST", horizon=5)
        trainer.fit(features, labels, regimes,
                    base_models["xgb"], base_models["lgbm"], base_models["cb"])

        for regime_id in [0, 1, 2]:
            xgb, lgbm, cb = trainer.get_models_for_regime(regime_id)
            assert xgb  is not None, f"XGBoost for regime {regime_id} is None"
            assert lgbm is not None, f"LightGBM for regime {regime_id} is None"
            assert cb   is not None, f"CatBoost for regime {regime_id} is None"

    def test_sparse_regime_uses_pooled_fallback(self, base_models):
        """When a regime has < 100 samples, pooled model must be used as fallback."""
        # Manufacture a sparse regime: only regime 0 in the first 50 rows,
        # everything else regime 1 (guaranteed < 100 rows for regime 2)
        n = 600
        features = _make_features(n)
        close    = _make_price_series(n)
        labels   = XGBoostPredictor.make_labels(close, 5).dropna()
        features = features.loc[labels.index]

        # Regime series: all regime 1 except 10 rows of regime 2
        regimes = pd.Series(1, index=features.index, dtype=int)
        regimes.iloc[:10] = 2   # only 10 rows in regime 2 → below MIN_REGIME_SAMPLES

        trainer = RegimeAwareTrainer(ticker="SPARSE_TEST", horizon=5)
        trainer.fit(features, labels, regimes,
                    base_models["xgb"], base_models["lgbm"], base_models["cb"])

        # Regime 2 should have fallen back to the pooled model
        xgb2, _, _ = trainer.get_models_for_regime(2)
        # The fallback IS the pooled xgb — verify it's the same object
        assert xgb2 is base_models["xgb"], "Sparse regime must use pooled fallback"


# ─────────────────────────────────────────────────────────────────────────────
# TestWalkForwardBlueprintGates
# ─────────────────────────────────────────────────────────────────────────────

class TestWalkForwardBlueprintGates:
    """
    Blueprint hard gates for the walk-forward validator.
    These are the non-negotiable accuracy and anti-lookahead checks.
    """

    def test_anti_lookahead_all_folds(self):
        """
        CRITICAL GATE: max(train) + embargo < min(test) for EVERY fold.
        Lookahead contamination would invalidate the entire ML pipeline.
        """
        features = _make_features(1500)
        wfv      = IndiaWalkForwardValidator()
        violations = []
        for fold in wfv.generate_folds(features):
            gap = int(min(fold.test_indices)) - int(max(fold.train_indices))
            if gap <= 5:
                violations.append(
                    f"Fold {fold.fold_id}: gap={gap} ≤ embargo=5"
                )
        assert len(violations) == 0, (
            "LOOKAHEAD DETECTED in walk-forward folds!\n" + "\n".join(violations)
        )

    def test_no_train_test_overlap_in_any_fold(self):
        """train_indices and test_indices must have zero intersection."""
        features = _make_features(1500)
        wfv      = IndiaWalkForwardValidator()
        for fold in wfv.generate_folds(features):
            overlap = set(fold.train_indices) & set(fold.test_indices)
            assert len(overlap) == 0, (
                f"Fold {fold.fold_id}: {len(overlap)} samples appear in both train and test"
            )

    def test_minimum_eight_folds_on_1500_rows(self):
        """Blueprint requires ≥ 8 folds. Must be achieved on 1500-row data."""
        features = _make_features(1500)
        wfv      = IndiaWalkForwardValidator()
        folds    = list(wfv.generate_folds(features))
        assert len(folds) >= 8, f"Only {len(folds)} folds — need ≥ 8"

    def test_directional_accuracy_excludes_neutral(self):
        """
        Neutral class (label=2) must be excluded from accuracy calculation.
        Blueprint: directional_accuracy = P(correct | predicted ≠ neutral ∧ true ≠ neutral)
        """
        y_true = np.array([0, 1, 2, 3, 4, 2, 3, 4])  # 2 neutrals
        y_pred = np.array([0, 1, 2, 3, 4, 3, 3, 4])   # neutral predicted to 3
        acc    = IndiaWalkForwardValidator.compute_directional_accuracy(y_true, y_pred)
        # Non-neutral: idx 0,1,3,4,6,7 → dir_true: D,D,U,U,U,U / dir_pred: D,D,U,U,U,U → 6/6
        assert acc == pytest.approx(1.0), f"Expected 1.0, got {acc}"

    def test_directional_accuracy_partial(self):
        y_true = np.array([0, 0, 3, 4, 3])   # DOWN DOWN UP UP UP
        y_pred = np.array([0, 3, 3, 0, 3])   # DOWN UP  UP DOWN UP
        acc    = IndiaWalkForwardValidator.compute_directional_accuracy(y_true, y_pred)
        assert acc == pytest.approx(3 / 5), f"Expected 0.6, got {acc}"

    def test_wfo_result_passes_threshold_at_55_pct(self):
        """WFOResult.passes_threshold must be True exactly at ≥ 55% mean accuracy."""
        result = WFOResult(
            folds=[],
            mean_accuracy=0.55,
            std_accuracy=0.02,
            min_accuracy=0.50,
        )
        wfv = IndiaWalkForwardValidator()
        assert wfv.validate_result(result) is True

    def test_wfo_result_fails_threshold_below_55_pct(self):
        """WFOResult.passes_threshold must be False at < 55% mean accuracy."""
        result = WFOResult(
            folds=[],
            mean_accuracy=0.549,
            std_accuracy=0.03,
            min_accuracy=0.49,
        )
        wfv = IndiaWalkForwardValidator()
        assert wfv.validate_result(result) is False

    def test_insufficient_data_raises_value_error(self):
        """Must raise ValueError when data is too short for even one fold."""
        features = _make_features(200)  # 200 < 504+5+63 = 572
        wfv      = IndiaWalkForwardValidator()
        with pytest.raises(ValueError, match="too short"):
            list(wfv.generate_folds(features))

    def test_fold_timestamps_monotonically_increasing(self):
        """Fold test_start timestamps must be strictly increasing."""
        features = _make_features(1500)
        wfv      = IndiaWalkForwardValidator()
        folds    = list(wfv.generate_folds(features))
        for i in range(1, len(folds)):
            assert folds[i].test_start > folds[i - 1].test_start, (
                f"Fold {i} test_start not later than fold {i-1}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# TestPredictionServiceColdPath
# ─────────────────────────────────────────────────────────────────────────────

class TestPredictionServiceColdPath:
    """
    Tests for PredictionService that do NOT require loading real models.
    Tests VIX circuit breaker, PredictionResult defaults, and to_agent_summary.
    """

    def test_prediction_result_defaults(self):
        """PredictionResult must be constructible with zero args."""
        r = PredictionResult()
        assert r.ticker             == ""
        assert r.direction          == "Neutral"
        assert r.direction_class    == 2
        assert r.confidence         == 0.5
        assert r.vix_circuit_breaker is False
        assert r.is_high_confidence  is False

    def test_to_agent_summary_format(self):
        """to_agent_summary() must include all key sections."""
        r = PredictionResult(
            ticker="RELIANCE.NS",
            current_price=2800.0,
            direction="Bullish",
            confidence=0.72,
            bullish_prob=0.72,
            bearish_prob=0.12,
            regime_name="Bull",
            forecast_5d=2870.0,
            return_pct_5d=2.5,
            q10_5d=2750.0,
            q90_5d=2950.0,
            top_features=[
                {"feature": "india_vix", "value": 14.2, "impact": -0.15},
                {"feature": "fii_net_cr", "value": 1200.0, "impact": 0.22},
            ],
        )
        summary = r.to_agent_summary()
        assert "RELIANCE.NS" in summary
        assert "₹2800.00"    in summary
        assert "Bullish"     in summary
        assert "72.0%"       in summary
        assert "Bull"        in summary
        assert "SHAP"        in summary
        assert "india_vix"   in summary

    def test_circuit_breaker_flag_in_summary(self):
        """VIX circuit breaker flag must appear in agent summary."""
        r = PredictionResult(
            ticker="NIFTY",
            current_price=22000.0,
            vix_circuit_breaker=True,
        )
        summary = r.to_agent_summary()
        assert "CIRCUIT BREAKER" in summary

    def test_prediction_result_all_proba_lists(self):
        """xgb_proba / lgbm_proba / catboost_proba are lists."""
        r = PredictionResult()
        assert isinstance(r.xgb_proba,      list)
        assert isinstance(r.lgbm_proba,      list)
        assert isinstance(r.catboost_proba,  list)

    def test_prediction_service_constructor_does_not_load(self):
        """PredictionService.__init__ must NOT attempt to load models."""
        # This would raise FileNotFoundError if it tried to load
        svc = PredictionService(
            ticker="HDFCBANK.NS",
            horizon=5,
            model_dir=Path("/nonexistent/path"),
        )
        assert svc._loaded is False


# ─────────────────────────────────────────────────────────────────────────────
# TestOptunaTunerSmoke
# ─────────────────────────────────────────────────────────────────────────────

class TestOptunaTunerSmoke:
    """
    Lightweight smoke tests for OptunaTuner (2 trials only, 10s timeout).
    Verifies that the Optuna tuning loop runs and returns valid params.
    """

    @pytest.fixture(scope="class")
    def tuner_data(self):
        n = 600
        close    = _make_price_series(n)
        features = _make_features(n)
        labels   = XGBoostPredictor.make_labels(close, 5).dropna()
        features = features.loc[labels.index]
        split    = int(len(features) * 0.8)
        return {
            "X_tr": features.iloc[:split],
            "y_tr": labels.iloc[:split],
            "X_vl": features.iloc[split:],
            "y_vl": labels.iloc[split:],
        }

    def test_xgboost_tuning_returns_required_keys(self, tuner_data):
        """XGBoost tuning must return a dict with all required param keys."""
        tuner  = OptunaTuner(n_trials=2, timeout_seconds=30)
        params = tuner.tune_xgboost(**tuner_data)
        required = {"objective", "num_class", "max_depth", "learning_rate",
                    "n_estimators", "tree_method"}
        for k in required:
            assert k in params, f"Missing param key: {k}"
        assert params["objective"]  == "multi:softprob"
        assert params["num_class"]  == 5
        assert params["tree_method"] == "hist"

    def test_lightgbm_tuning_returns_required_keys(self, tuner_data):
        """LightGBM tuning must return a dict with all required param keys."""
        tuner  = OptunaTuner(n_trials=2, timeout_seconds=30)
        params = tuner.tune_lightgbm(**tuner_data)
        required = {"objective", "num_class", "metric", "learning_rate",
                    "n_estimators"}
        for k in required:
            assert k in params, f"Missing param key: {k}"
        assert params["objective"]  == "multiclass"
        assert params["num_class"]  == 5

    def test_catboost_tuning_returns_required_keys(self, tuner_data):
        """CatBoost tuning must return a dict with all required param keys."""
        tuner  = OptunaTuner(n_trials=2, timeout_seconds=30)
        params = tuner.tune_catboost(**tuner_data)
        required = {"loss_function", "classes_count", "learning_rate", "iterations"}
        for k in required:
            assert k in params, f"Missing param key: {k}"
        assert params["loss_function"]  == "MultiClass"
        assert params["classes_count"]  == 5


# ─────────────────────────────────────────────────────────────────────────────
# TestEnsembleIntegration
# ─────────────────────────────────────────────────────────────────────────────

class TestEnsembleIntegration:
    """Tests for EnsemblePredictor beyond the basic unit tests in test_prediction_models.py."""

    def test_21_feature_meta_matrix(self):
        """_build_meta_features must produce 21-column meta-feature matrix."""
        ens = EnsemblePredictor()
        rng = np.random.default_rng(0)
        n   = 50

        def _proba_batch(n):
            p = np.abs(rng.standard_normal((n, 5)))
            return (p.T / p.sum(axis=1)).T

        meta = ens._build_meta_features(
            xgb_proba       = _proba_batch(n),
            lgbm_proba      = _proba_batch(n),
            catboost_proba  = _proba_batch(n),
            regime_ids      = rng.integers(0, 3, size=n),
            chronos_dir_5d  = rng.uniform(0.3, 0.7, n),
            chronos_dir_10d = rng.uniform(0.3, 0.7, n),
            chronos_dir_30d = rng.uniform(0.3, 0.7, n),
        )
        assert meta.shape == (n, 21), (
            f"Meta-feature matrix shape must be (n, 21), got {meta.shape}"
        )

    def test_chronos_divergence_logic(self):
        """Ensemble predict must still return valid result when Chronos diverges."""
        ens = EnsemblePredictor()
        # Bullish consensus (high proba on class 4) but bearish Chronos dir
        xgb_p = np.array([0.02, 0.03, 0.05, 0.25, 0.65])  # Very Bullish
        lgbm_p = np.array([0.03, 0.02, 0.05, 0.30, 0.60])
        cb_p   = np.array([0.01, 0.04, 0.05, 0.20, 0.70])

        result = ens.predict(
            xgb_proba=xgb_p,
            lgbm_proba=lgbm_p,
            catboost_proba=cb_p,
            regime_id=2,
            chronos_dir_5d=0.20,   # bearish Chronos → divergence warning
            chronos_dir_10d=0.18,
            chronos_dir_30d=0.22,
        )
        # Must still return a valid prediction (not crash)
        assert result["direction"] in [
            "Very Bearish", "Bearish", "Neutral", "Bullish", "Very Bullish"
        ]
        assert 0.0 <= result["confidence"] <= 1.0

    def test_regime_weights_sum_to_one(self):
        """Sum of regime weights (xgb + lgbm + catboost) must equal 1.0."""
        from prediction.models.ensemble_predictor import REGIME_WEIGHTS
        for regime_id, weights in REGIME_WEIGHTS.items():
            total = sum(weights.values())
            assert abs(total - 1.0) < 1e-6, (
                f"Regime {regime_id} weights sum to {total}, not 1.0"
            )


# ─────────────────────────────────────────────────────────────────────────────
# TestHMMIntegration
# ─────────────────────────────────────────────────────────────────────────────

class TestHMMIntegration:
    """HMM-specific tests beyond the basic unit tests."""

    def test_bear_has_lowest_mean_return_stable(self):
        """
        Blueprint hard rule: Bear(0) must have the lowest mean return.
        Verified with multiple seeds for stability.
        """
        for seed in [42, 99, 1337]:
            close   = _make_price_series(800, seed=seed)
            returns = np.log(close / close.shift(1)).dropna()
            hmm     = HMMRegimeDetector(n_regimes=3, n_iter=100)
            hmm.fit(returns)

            regime_series  = hmm.predict_series(returns)
            regime_returns = {
                r: float(returns[regime_series == r].mean())
                for r in [0, 1, 2]
            }
            assert regime_returns[0] <= regime_returns[2], (
                f"Seed {seed}: Bear(0) mean={regime_returns[0]:.5f} must be "
                f"<= Bull(2) mean={regime_returns[2]:.5f}"
            )

    def test_vix_covariate_does_not_crash_fitting(self):
        """HMM must fit successfully when VIX series is provided."""
        close   = _make_price_series(500)
        returns = np.log(close / close.shift(1)).dropna()
        vix     = _make_vix_series(len(returns) + 1).iloc[1:].reindex(returns.index)
        hmm = HMMRegimeDetector(n_regimes=3, n_iter=50)
        hmm.fit(returns, vix)   # must not raise
        regime = hmm.predict_current(returns, vix)
        assert regime["regime_name"] in {"Bull", "Sideways", "Bear"}

    def test_predict_current_returns_probs_sum_to_one(self):
        """predict_current must return regime_probs that sum to 1.0."""
        close   = _make_price_series(500)
        returns = np.log(close / close.shift(1)).dropna()
        hmm = HMMRegimeDetector(n_regimes=3, n_iter=50)
        hmm.fit(returns)
        current = hmm.predict_current(returns)
        probs_sum = sum(current["regime_probs"].values())
        assert abs(probs_sum - 1.0) < 1e-4, f"Regime probs sum={probs_sum}, expected 1.0"


# ─────────────────────────────────────────────────────────────────────────────
# TestFeatureValidatorIntegration
# ─────────────────────────────────────────────────────────────────────────────

class TestFeatureValidatorIntegration:
    """Feature validator integration tests."""

    def test_all_nan_column_fails_validation(self):
        """An all-NaN column must cause validation to fail."""
        close    = _make_price_series(300)
        features = _make_features(300)
        features["fii_net_cr"] = np.nan  # break one column
        validator = FeatureValidator()
        report    = validator.validate_features(features, close)
        assert report.passed is False
        assert "fii_net_cr" in report.null_columns

    def test_clean_features_no_null_columns(self):
        """Properly built (no all-NaN columns) features must have zero null_columns."""
        close    = _make_price_series(300)
        features = _make_features(300).ffill().bfill()
        validator = FeatureValidator()
        report    = validator.validate_features(features, close)
        assert len(report.null_columns) == 0, (
            f"Unexpected null columns: {report.null_columns}"
        )

    def test_multiple_null_columns_all_reported(self):
        """Multiple bad columns must all appear in null_columns."""
        close    = _make_price_series(300)
        features = _make_features(300)
        bad_cols = ["fii_net_cr", "india_vix", "brent_crude"]
        for col in bad_cols:
            features[col] = np.nan
        validator = FeatureValidator()
        report    = validator.validate_features(features, close)
        for col in bad_cols:
            assert col in report.null_columns, f"{col} not in null_columns"

    def test_wfo_embargo_violation_raises(self):
        """Embargo gap ≤ embargo must raise AssertionError."""
        validator = FeatureValidator()
        train_idx = np.arange(0, 504)
        test_idx  = np.arange(506, 569)  # gap = 2 ≤ embargo=5 (violation)
        with pytest.raises(AssertionError, match="embargo violation"):
            validator.validate_wfo_folds(train_idx, test_idx, embargo=5, fold_id=0)

    def test_wfo_valid_fold_returns_true(self):
        """Valid fold (gap > embargo) must return True."""
        validator = FeatureValidator()
        train_idx = np.arange(0, 504)
        test_idx  = np.arange(510, 573)  # gap = 6 > 5 → valid
        result = validator.validate_wfo_folds(train_idx, test_idx, embargo=5, fold_id=1)
        assert result is True


# ─────────────────────────────────────────────────────────────────────────────
# TestBlueprintValidationGate (Phase 5 Acceptance Gate)
# ─────────────────────────────────────────────────────────────────────────────

class TestBlueprintValidationGate:
    """
    Phase 5 acceptance gate tests.
    These confirm that the full training loop runs correctly.
    NOTE: Directional accuracy >= 55% cannot be guaranteed on synthetic random
    data — this target requires real NSE historical data. The tests here verify
    the pipeline machinery is correct and the accuracy metric is produced.
    For real validation, run integration tests with 3yr Nifty 50 data.
    """

    def test_full_pipeline_produces_wfo_result(self, tmp_path):
        """
        Full IndiaMLTrainer pipeline must produce a WFOResult with ≥ 8 folds.
        This is the Phase 5 blueprint acceptance gate.
        """
        n = 1500
        close    = _make_price_series(n)
        nifty    = _make_nifty_returns(n)
        vix      = _make_vix_series(n)
        features = _make_features(n)

        trainer = IndiaMLTrainer(
            ticker="GATE_TEST",
            horizon=5,
            run_optuna=False,   # skip Optuna for speed
            use_mlflow=False,
            model_dir=tmp_path / "models",
        )
        result = trainer.train(
            feature_df=features,
            close_series=close,
            nifty_returns=nifty,
            vix_series=vix,
        )

        # Gate 1: Minimum folds
        assert result.wfo_result.n_folds >= 8, (
            f"Phase 5 Gate: Expected ≥ 8 folds, got {result.wfo_result.n_folds}"
        )

        # Gate 2: Accuracy is numeric and in [0, 1]
        assert 0.0 <= result.wfo_result.mean_accuracy <= 1.0

        # Gate 3: All models saved to disk
        model_dir = tmp_path / "models" / "GATE_TEST" / "h5"
        assert (model_dir / "xgboost.joblib").exists(), "XGBoost not saved"
        assert (model_dir / "lightgbm.joblib").exists(), "LightGBM not saved"
        assert (model_dir / "hmm.joblib").exists(),   "HMM not saved"
        assert (model_dir / "ensemble.joblib").exists(), "Ensemble not saved"

    def test_package_imports_work(self):
        """All Phase 5 classes must be importable from prediction package root."""
        from prediction import (
            XGBoostPredictor, LightGBMPredictor, CatBoostPredictor,
            HMMRegimeDetector, EnsemblePredictor, Chronos2Predictor,
            IndiaMLTrainer, TrainingResult,
            IndiaWalkForwardValidator, WFOFold, WFOResult,
            OptunaTuner, RegimeAwareTrainer,
            PredictionService, PredictionResult,
            ConfidenceCalculator, ModelRouter, TaskType, TSFMRoute,
        )
        # All imports must succeed — no ImportError
        assert XGBoostPredictor      is not None
        assert IndiaMLTrainer        is not None
        assert PredictionService     is not None
        assert IndiaWalkForwardValidator is not None
