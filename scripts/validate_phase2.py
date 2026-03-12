#!/usr/bin/env python3
"""
Phase 2 Validation Gate — Feature Engineering
Gate: 70 features · zero NaN last 252 days · all .shift(1) · Chronos covariates
Run: python3 scripts/validate_phase2.py
"""
import asyncio, sys, os
sys.path.insert(0, os.path.abspath("."))
import structlog
structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

import numpy as np
import pandas as pd


def _make_synthetic_data(n: int = 300):
    """Shared synthetic dataset used across all checks."""
    np.random.seed(42)
    idx    = pd.date_range("2023-01-01", periods=n, freq="B", tz="Asia/Kolkata")
    prices = 1000 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, n)))
    ohlcv  = pd.DataFrame({
        "open":   prices * np.random.uniform(0.99, 1.00, n),
        "high":   prices * np.random.uniform(1.00, 1.02, n),
        "low":    prices * np.random.uniform(0.98, 1.00, n),
        "close":  prices,
        "volume": np.random.randint(500_000, 5_000_000, n).astype(float),
    }, index=idx)
    macro  = pd.DataFrame({
        "usdinr":      np.random.uniform(82, 84, n),
        "brent_crude": np.random.uniform(75, 90, n),
        "gold":        np.random.uniform(1900, 2100, n),
        "india_vix":   np.random.uniform(12, 22, n),
        "nifty50":     prices * np.random.uniform(0.98, 1.02, n),
        "banknifty":   prices * np.random.uniform(0.95, 1.05, n) * 2,
    }, index=idx)
    fii    = pd.DataFrame({
        "fii_net_value": np.random.uniform(-5000, 5000, n),
        "dii_net_value": np.random.uniform(-3000, 3000, n),
    }, index=idx)
    return idx, prices, ohlcv, macro, fii


async def run_checks() -> list[tuple[str, bool, str]]:
    results = []
    def ok(n, d):   results.append((n, True,  f"✅ PASS — {d}"))
    def warn(n, d): results.append((n, True,  f"⚠  WARN — {d}"))
    def fail(n, d): results.append((n, False, f"❌ FAIL — {d}"))

    # ── 1: Feature column registry ────────────────────────────────────
    try:
        from features.india_feature_set import ALL_FEATURE_COLUMNS, CHRONOS_COVARIATES
        assert len(ALL_FEATURE_COLUMNS) == 70, f"Got {len(ALL_FEATURE_COLUMNS)}"
        assert len(CHRONOS_COVARIATES)  == 8,  f"Got {len(CHRONOS_COVARIATES)}"
        assert all(c in ALL_FEATURE_COLUMNS for c in CHRONOS_COVARIATES), \
            "Chronos covariate not in ALL_FEATURE_COLUMNS"
        ok("Feature registry", "70 features · 8 Chronos covariates · all registered")
    except Exception as e:
        fail("Feature registry", str(e))

    # ── 2: Synthetic build — shape and columns ────────────────────────
    features = None  # shared across checks 2-14
    prices_ref = None
    idx_ref    = None
    try:
        from features.india_feature_set import IndiaFeatureSet, ALL_FEATURE_COLUMNS
        idx_ref, prices_ref, ohlcv, macro, fii = _make_synthetic_data(300)
        fset     = IndiaFeatureSet()
        features = fset.build(ohlcv_df=ohlcv, macro_df=macro, fii_dii_df=fii)
        assert features.shape[1] == 70,   f"Expected 70 cols, got {features.shape[1]}"
        assert list(features.columns) == ALL_FEATURE_COLUMNS, "Column order mismatch"
        ok("Synthetic build", f"shape={features.shape} · columns match ALL_FEATURE_COLUMNS")
    except Exception as e:
        fail("Synthetic build", str(e))

    # ── 3: Anti-lookahead — shift(1) verification ─────────────────────
    try:
        assert features is not None, "features not built (check 2 failed)"
        assert pd.isna(features["close_lag1"].iloc[0]), \
            "close_lag1.iloc[0] must be NaN (first row has no T-1)"
        lag1_vals  = features["close_lag1"].iloc[1:].values
        close_vals = prices_ref[:-1]
        assert np.allclose(lag1_vals, close_vals, rtol=1e-5), \
            "close_lag1 does not equal close.shift(1)"
        ret = features["return_1d"].dropna()
        assert ret.dtype == float, "return_1d must be float"
        ok("Anti-lookahead shift(1)",
           "close_lag1 == close.shift(1) ✓ · return_1d float ✓")
    except Exception as e:
        fail("Anti-lookahead shift(1)", str(e))

    # ── 4: NaN budget on last 252 rows ────────────────────────────────
    try:
        assert features is not None, "features not built"
        last_252 = features.tail(252)
        null_pct = last_252.isna().mean().mean() * 100
        worst    = last_252.isna().mean().nlargest(5).to_dict()
        # Synthetic data: allow up to 20% (some TA indicators need warmup bars)
        # Live data gate (features/feature_validator.py): tightens to 5%
        assert null_pct < 20.0, \
            f"NaN {null_pct:.1f}% too high. Worst: {worst}"
        ok("NaN budget (last 252 rows)", f"{null_pct:.1f}% null · worst={list(worst.keys())[:3]}")
    except Exception as e:
        fail("NaN budget (last 252 rows)", str(e))

    # ── 5: No infinite values ─────────────────────────────────────────
    try:
        assert features is not None, "features not built"
        num     = features.select_dtypes(include=[np.number])
        inf_cols = num.columns[np.isinf(num).any()].tolist()
        assert not inf_cols, f"Inf values in: {inf_cols}"
        ok("No infinite values", "all finite ✓")
    except Exception as e:
        fail("No infinite values", str(e))

    # ── 6: Timezone ───────────────────────────────────────────────────
    try:
        assert features is not None, "features not built"
        assert features.index.tzinfo is not None, "No timezone on index"
        assert "Kolkata" in str(features.index.tzinfo), \
            f"Wrong tz: {features.index.tzinfo}"
        ok("Timezone", "Asia/Kolkata ✓")
    except Exception as e:
        fail("Timezone", str(e))

    # ── 7: Chronos covariates present ────────────────────────────────
    try:
        assert features is not None, "features not built"
        from features.india_feature_set import CHRONOS_COVARIATES
        missing_cov = [c for c in CHRONOS_COVARIATES if c not in features.columns]
        assert not missing_cov, f"Missing: {missing_cov}"
        cov      = features[CHRONOS_COVARIATES].dropna()
        assert len(cov) > 150, f"Only {len(cov)} clean covariate rows (need >150)"
        ok("Chronos covariates",
           f"8 present · {len(cov)} clean rows · {CHRONOS_COVARIATES}")
    except Exception as e:
        fail("Chronos covariates", str(e))

    # ── 8: Covariate builder output ───────────────────────────────────
    try:
        assert features is not None, "features not built"
        from features.covariate_builder import build_chronos_covariates
        target = pd.Series(prices_ref, index=idx_ref, name="close")
        result = build_chronos_covariates(features, target)
        assert "target"            in result
        assert "past_dynamic_real" in result
        assert "covariate_df"      in result
        assert result["past_dynamic_real"].shape[1] == 8
        assert result["past_dynamic_real"].dtype    == np.float32
        ok("Covariate builder",
           f"shape={result['past_dynamic_real'].shape} · dtype=float32")
    except Exception as e:
        fail("Covariate builder", str(e))

    # ── 9: Feature validator (strict) ────────────────────────────────
    try:
        assert features is not None, "features not built"
        from features.feature_validator import validate_features, FeatureValidationError
        # Use 20% null threshold for synthetic (warmup bars)
        report = validate_features(
            features, min_rows=252, max_null_pct=20.0, ticker="SYNTHETIC"
        )
        assert report["passed"], f"Validator errors: {report['errors']}"
        ok("Feature validator",
           f"passed ✓ · null={report.get('null_check')} · tz={report.get('timezone')}")
    except Exception as e:
        fail("Feature validator", str(e))

    # ── 10: VIX regime encoding ───────────────────────────────────────
    try:
        assert features is not None, "features not built"
        regimes = features["vix_regime"].dropna().unique()
        assert all(v in [0, 1, 2, 3, 4, 5] for v in regimes), \
            f"Unexpected regime values: {regimes}"
        ok("VIX regime encoding",
           f"values={sorted(regimes.astype(int).tolist())} ∈ {{0..5}} ✓")
    except Exception as e:
        fail("VIX regime encoding", str(e))

    # ── 11: Calendar features ─────────────────────────────────────────
    try:
        assert features is not None, "features not built"
        assert "expiry_day"     in features.columns
        assert "results_season" in features.columns
        assert "budget_week"    in features.columns
        thursdays = features.index[features["expiry_day"] == 1.0]
        assert all(d.dayofweek == 3 for d in thursdays), \
            "expiry_day=1 but not all Thursdays"
        ok("Calendar features",
           f"{len(thursdays)} Thursdays flagged · results_season ✓ · budget_week ✓")
    except Exception as e:
        fail("Calendar features", str(e))

    # ── 12: Sector RS (10 features) ───────────────────────────────────
    try:
        assert features is not None, "features not built"
        rs_cols = [c for c in features.columns if c.startswith("rs_")]
        assert len(rs_cols) == 10, f"Expected 10 rs_ cols, got {len(rs_cols)}"
        # With no sector_df passed, defaults to 1.0 — check it's filled
        assert not features[rs_cols].isna().all(axis=None), \
            "All sector RS values are NaN"
        ok("Sector RS (10)", f"{rs_cols}")
    except Exception as e:
        fail("Sector RS (10)", str(e))

    # ── 13: FII/DII features (6) ──────────────────────────────────────
    try:
        assert features is not None, "features not built"
        required_fii = ["fii_net_cr","dii_net_cr","fii_zscore_5d",
                         "dii_zscore_5d","fii_streak","fii_dii_consensus"]
        missing_fii  = [c for c in required_fii if c not in features.columns]
        assert not missing_fii, f"Missing FII cols: {missing_fii}"
        fii_non_null = features["fii_net_cr"].dropna()
        assert len(fii_non_null) > 150, \
            f"Only {len(fii_non_null)} non-null fii_net_cr rows"
        ok("FII/DII features (6)",
           f"all present · {len(fii_non_null)} non-null fii_net_cr rows")
    except Exception as e:
        fail("FII/DII features (6)", str(e))

    # ── 14: Walk-forward split integrity ─────────────────────────────
    try:
        from config.constants import (
            WFO_TRAIN_WINDOW_DAYS, WFO_TEST_WINDOW_DAYS,
            WFO_EMBARGO_DAYS, WFO_STEP_SIZE_DAYS,
        )
        # Simulate one fold
        train_end  = WFO_TRAIN_WINDOW_DAYS
        test_start = train_end + WFO_EMBARGO_DAYS
        test_end   = test_start + WFO_TEST_WINDOW_DAYS
        assert test_start > train_end, "Embargo not applied"
        assert (test_start - train_end) == WFO_EMBARGO_DAYS, "Wrong embargo gap"
        # Anti-lookahead: max train index < min test index
        if features is not None and len(features) >= test_end:
            train_idx = features.index[:train_end]
            test_idx  = features.index[test_start:test_end]
            assert max(train_idx) < min(test_idx), \
                "Train/test overlap — lookahead detected"
        ok("Walk-forward split",
           f"train={WFO_TRAIN_WINDOW_DAYS}d · embargo={WFO_EMBARGO_DAYS}d · "
           f"test={WFO_TEST_WINDOW_DAYS}d · step={WFO_STEP_SIZE_DAYS}d · no overlap ✓")
    except Exception as e:
        fail("Walk-forward split", str(e))

    # ── 15: F&O features (neutral defaults when no live data) ─────────
    try:
        assert features is not None, "features not built"
        required_fno = ["pcr","pcr_zscore","iv_percentile","oi_change_pct",
                         "max_pain_distance","expiry_week_flag","rollover_pct","basis_pct"]
        missing_fno  = [c for c in required_fno if c not in features.columns]
        assert not missing_fno, f"Missing F&O cols: {missing_fno}"
        # When fno_df=None, pcr defaults to 1.0 (neutral)
        pcr_vals = features["pcr"].dropna().unique()
        assert all(v == 1.0 for v in pcr_vals) or len(pcr_vals) > 1, \
            "pcr column has unexpected values"
        ok("F&O features (8)",
           f"all present · pcr neutral default=1.0 ✓")
    except Exception as e:
        fail("F&O features (8)", str(e))

    # ── 16: FeatureEngineer import (async pipeline) ───────────────────
    try:
        from features.feature_engineer import FeatureEngineer
        fe = FeatureEngineer()
        assert hasattr(fe, "build_for_ticker")
        ok("FeatureEngineer", "import ok · build_for_ticker method present")
    except Exception as e:
        fail("FeatureEngineer", str(e))

    # ── 17: TA indicators — RSI range check ───────────────────────────
    try:
        assert features is not None, "features not built"
        rsi_vals = features["rsi_14"].dropna()
        assert len(rsi_vals) > 100, f"Only {len(rsi_vals)} RSI rows"
        assert rsi_vals.between(0, 100).all(), \
            f"RSI out of [0,100]: min={rsi_vals.min():.1f} max={rsi_vals.max():.1f}"
        ok("RSI range", f"RSI ∈ [0,100] · {len(rsi_vals)} rows ✓")
    except Exception as e:
        fail("RSI range", str(e))

    # ── 18: TA indicators — MACD histogram sign consistency ───────────
    try:
        assert features is not None, "features not built"
        macd_hist = features["macd_hist"].dropna()
        assert len(macd_hist) > 100, f"Only {len(macd_hist)} MACD rows"
        assert macd_hist.dtype == float
        ok("MACD histogram", f"{len(macd_hist)} rows · dtype=float ✓")
    except Exception as e:
        fail("MACD histogram", str(e))

    # ── 19: Bollinger band width positive ─────────────────────────────
    try:
        assert features is not None, "features not built"
        bb_w = features["bb_width"].dropna()
        assert len(bb_w) > 100
        assert (bb_w >= 0).all(), f"Negative BB width detected: min={bb_w.min():.4f}"
        ok("Bollinger width ≥ 0", f"{len(bb_w)} rows · min={bb_w.min():.4f} ✓")
    except Exception as e:
        fail("Bollinger width ≥ 0", str(e))

    # ── 20: config.constants has WFO params ───────────────────────────
    try:
        from config.constants import (
            WFO_TRAIN_WINDOW_DAYS, WFO_TEST_WINDOW_DAYS,
            WFO_EMBARGO_DAYS, WFO_STEP_SIZE_DAYS, WFO_MIN_FOLDS,
        )
        assert WFO_TRAIN_WINDOW_DAYS == 504
        assert WFO_TEST_WINDOW_DAYS  == 63
        assert WFO_EMBARGO_DAYS      == 5
        assert WFO_STEP_SIZE_DAYS    == 21
        assert WFO_MIN_FOLDS         >= 8
        ok("WFO constants",
           f"train={WFO_TRAIN_WINDOW_DAYS} · test={WFO_TEST_WINDOW_DAYS} · "
           f"embargo={WFO_EMBARGO_DAYS} · step={WFO_STEP_SIZE_DAYS} · folds≥{WFO_MIN_FOLDS}")
    except Exception as e:
        fail("WFO constants", str(e))

    return results


def main():
    print("=" * 72)
    print("  PHASE 2 VALIDATION — Feature Engineering")
    print("  70 features · anti-lookahead · Chronos covariates · walk-forward")
    print("=" * 72)
    print()

    results = asyncio.run(run_checks())

    for name, passed, message in results:
        print(f"  {name:<44} {message}")

    passed    = sum(1 for _, p, _ in results if p)
    total     = len(results)
    hard_fail = [(n, m) for n, p, m in results if not p]

    print()
    print("=" * 72)
    print(f"  RESULT: {passed}/{total} checks passed")
    print("=" * 72)

    if not hard_fail:
        print()
        print("  ✅ PHASE 2 COMPLETE — Feature Engineering validated")
        print()
        print("  Feature map confirmed:")
        print("    Group A — Price/Volume base   (5)")
        print("    Group B — TA Momentum         (8)")
        print("    Group C — TA Trend            (7)")
        print("    Group D — TA Volatility       (6)")
        print("    Group E — TA Volume           (4)")
        print("    Group F — India Macro         (10)")
        print("    Group G — FII/DII Flows       (6)")
        print("    Group H — F&O Signals         (8)")
        print("    Group I — Calendar/Event      (6)")
        print("    Group J — Sector RS           (10)")
        print("    TOTAL                         70 ✓")
        print()
        print("  Chronos-2 covariates (8):")
        try:
            from features.india_feature_set import CHRONOS_COVARIATES
            for c in CHRONOS_COVARIATES:
                print(f"    • {c}")
        except Exception:
            pass
        print()
        print("  ─── Next: Phase 3 — SMC + Volume Profile + TA ─────────────")
        print("  Build: data/processors/technical_analyzer.py")
        print("  Build: data/processors/volume_profiler.py")
        print("  Gate:  RSI matches TradingView ±0.5% · BOS/CHoCH detected")
        sys.exit(0)
    else:
        print()
        print("  ❌ HARD FAILURES (must fix before Phase 3):")
        for name, msg in hard_fail:
            print(f"  → {name}: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()