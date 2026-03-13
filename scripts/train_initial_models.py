"""
scripts/train_initial_models.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
First-time model training CLI for the India Multi-Agent Financial Engine.

Usage:
    # Offline test (no API keys needed):
    python scripts/train_initial_models.py --ticker HDFCBANK --horizon 5 \\
        --synthetic --no-optuna --no-mlflow

    # Production (requires NSE/yfinance data already downloaded):
    python scripts/train_initial_models.py --ticker HDFCBANK.NS --horizon 5

Exit codes:
    0 — training complete, directional accuracy gate passed (≥ 55%)
    1 — training complete, accuracy gate FAILED (auto-retrain recommended)
    2 — training FAILED with exception
"""
from __future__ import annotations

import argparse
import sys
import numpy as np
import pandas as pd
import structlog
from pathlib import Path

# Ensure project root is importable
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from prediction.training.trainer import IndiaMLTrainer
from features.india_feature_set import ALL_FEATURE_COLUMNS
from prediction.models.xgboost_predictor import XGBoostPredictor

logger = structlog.get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic data generator (--synthetic mode, no API keys needed)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_synthetic_data(
    n_rows: int = 1500,
    seed:   int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """
    Generate synthetic OHLCV-based features + Nifty returns + VIX series.
    Used ONLY for offline testing (--synthetic flag).
    NOT for production training.

    Returns:
        (feature_df, close_series, nifty_returns, vix_series)
    """
    rng = np.random.default_rng(seed)

    # Price series: geom. Brownian motion starting at ₹1,000
    log_returns = rng.normal(0.0004, 0.015, size=n_rows)
    prices      = 1000.0 * np.exp(np.cumsum(log_returns))
    idx = pd.date_range(
        start="2020-01-02", periods=n_rows, freq="B", tz="Asia/Kolkata"
    )
    close_series = pd.Series(prices, index=idx, name="close")

    # Nifty 50 returns (slightly correlated with stock)
    nifty_log_ret = log_returns * 0.6 + rng.normal(0.0002, 0.012, size=n_rows)
    nifty_prices  = 17000.0 * np.exp(np.cumsum(nifty_log_ret))
    nifty_prices_s = pd.Series(nifty_prices, index=idx, name="nifty50")
    nifty_returns   = np.log(nifty_prices_s / nifty_prices_s.shift(1)).dropna()

    # India VIX series (mean-reverting around 15)
    vix_series = pd.Series(
        np.clip(rng.normal(15.0, 3.0, size=n_rows), 8, 40),
        index=idx,
        name="india_vix",
    )

    # 70-column feature DataFrame (synthetic random, with proper structure)
    feature_data = rng.standard_normal((n_rows, len(ALL_FEATURE_COLUMNS)))
    feature_df   = pd.DataFrame(feature_data, columns=ALL_FEATURE_COLUMNS, index=idx)

    # Simulate integer calendar features (CatBoost needs these as int-encodings)
    feature_df["day_of_week"]    = np.tile([0, 1, 2, 3, 4], n_rows // 5 + 1)[:n_rows].astype(float)
    feature_df["expiry_day"]     = (feature_df["day_of_week"] == 3).astype(float)
    feature_df["vix_regime"]     = rng.integers(1, 5, size=n_rows).astype(float)
    feature_df["results_season"] = rng.integers(0, 2, size=n_rows).astype(float)
    feature_df["budget_week"]    = 0.0
    feature_df["month_end_flag"] = 0.0

    # Apply shift(1) on lagged price/volume/macro features (anti-lookahead)
    for col in ["close_lag1", "return_1d", "return_5d", "return_10d",
                "rsi_14", "macd_hist", "india_vix", "fii_net_cr", "brent_crude"]:
        if col in feature_df.columns:
            feature_df[col] = feature_df[col].shift(1)

    logger.info(
        "synthetic_data_generated",
        n_rows=n_rows,
        n_features=len(feature_df.columns),
        price_range=f"₹{prices.min():.0f}–₹{prices.max():.0f}",
    )
    return feature_df, close_series, nifty_returns, vix_series


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="First-time training pipeline for India ML Prediction Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--ticker",
        type=str,
        default="HDFCBANK.NS",
        help="NSE ticker symbol (default: HDFCBANK.NS)",
    )
    parser.add_argument(
        "--horizon",
        type=int,
        default=5,
        choices=[5, 10, 30],
        help="Forecast horizon in trading days: 5 / 10 / 30 (default: 5)",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        default=False,
        help="Use synthetic data (no API keys needed; for offline testing only)",
    )
    parser.add_argument(
        "--no-optuna",
        dest="run_optuna",
        action="store_false",
        default=True,
        help="Skip Optuna hyperparameter tuning (faster, less accurate)",
    )
    parser.add_argument(
        "--no-mlflow",
        dest="use_mlflow",
        action="store_false",
        default=True,
        help="Disable MLflow experiment logging",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("models/saved"),
        help="Directory to save trained models (default: models/saved/)",
    )
    parser.add_argument(
        "--n-rows",
        type=int,
        default=1500,
        help="Number of synthetic rows to generate when --synthetic is set (default: 1500)",
    )
    return parser.parse_args()


def _load_real_data(ticker: str, horizon: int) -> tuple:
    """
    Load real NSE data via yfinance and nselib adapters.
    This path requires API access — only used in production mode.

    Returns: (feature_df, close_series, nifty_returns, vix_series)
    """
    try:
        import yfinance as yf
    except ImportError:
        raise ImportError("yfinance not installed. Run: pip install yfinance")

    logger.info("loading_real_data", ticker=ticker)

    # Download 3 years of OHLCV
    raw = yf.download(ticker, period="3y", interval="1d", auto_adjust=True, progress=False)
    if raw.empty:
        raise ValueError(f"No data returned for ticker '{ticker}'. Check NSE symbol.")
    raw.columns = raw.columns.get_level_values(0).str.lower()
    if raw.index.tzinfo is None:
        raw.index = raw.index.tz_localize("Asia/Kolkata")
    else:
        raw.index = raw.index.tz_convert("Asia/Kolkata")

    close_series = raw["close"].dropna()

    # Nifty 50 for HMM regime
    nifty_raw   = yf.download("^NSEI", period="3y", interval="1d", auto_adjust=True, progress=False)
    nifty_raw.columns = nifty_raw.columns.get_level_values(0).str.lower()
    nifty_prices = nifty_raw["close"].dropna()
    if nifty_prices.index.tzinfo is None:
        nifty_prices.index = nifty_prices.index.tz_localize("Asia/Kolkata")
    nifty_returns = np.log(nifty_prices / nifty_prices.shift(1)).dropna()

    # India VIX
    vix_raw = yf.download("^INDIAVIX", period="3y", interval="1d", auto_adjust=True, progress=False)
    vix_raw.columns = vix_raw.columns.get_level_values(0).str.lower()
    vix_series = vix_raw["close"].dropna()
    if vix_series.index.tzinfo is None:
        vix_series.index = vix_series.index.tz_localize("Asia/Kolkata")

    # Build 70-column feature DataFrame using IndiaFeatureSet
    from features.india_feature_set import IndiaFeatureSet
    fs = IndiaFeatureSet()

    # Minimal macro_df from yfinance (enough for Group F features)
    macro_tickers = {
        "usdinr":      "USDINR=X",
        "brent_crude": "BZ=F",
        "gold_price":  "GC=F",
        "nifty50":     "^NSEI",
        "banknifty":   "^NSEBANK",
    }
    macro_data: dict[str, pd.Series] = {}
    for col, yticker in macro_tickers.items():
        try:
            d = yf.download(yticker, period="3y", interval="1d", auto_adjust=True, progress=False)
            d.columns = d.columns.get_level_values(0).str.lower()
            s = d["close"].dropna()
            if s.index.tzinfo is None:
                s.index = s.index.tz_localize("Asia/Kolkata")
            macro_data[col] = s
        except Exception as e:
            logger.warning("macro_download_failed", ticker=yticker, error=str(e))

    macro_data["india_vix"] = vix_series
    macro_df = pd.DataFrame(macro_data).reindex(raw.index).ffill()

    feature_df = fs.build(
        ohlcv_df=raw,
        macro_df=macro_df,
        fii_dii_df=None,   # requires nselib; use zero-fill fallback
        fno_df=None,       # requires nsefin  ; use neutral fallback
        sector_df=None,    # requires yfinance sector indices; use neutral RS
    )

    logger.info(
        "real_data_loaded",
        ticker=ticker,
        n_rows=len(feature_df),
        n_features=len(feature_df.columns),
    )
    return feature_df, close_series, nifty_returns, vix_series


def main() -> int:
    """
    Run the training pipeline. Returns exit code (0=pass, 1=fail, 2=error).
    """
    args = _parse_args()

    print(f"\n{'='*60}")
    print(f"  India ML Prediction Engine — Model Training")
    print(f"  Ticker  : {args.ticker}")
    print(f"  Horizon : {args.horizon}d")
    print(f"  Mode    : {'SYNTHETIC (offline)' if args.synthetic else 'PRODUCTION'}")
    print(f"  Optuna  : {'OFF' if not args.run_optuna else 'ON (50 trials)'}")
    print(f"  MLflow  : {'OFF' if not args.use_mlflow else 'ON'}")
    print(f"{'='*60}\n")

    # ── Load data ────────────────────────────────────────────────────────────
    try:
        if args.synthetic:
            print("📊 Generating synthetic data...")
            feature_df, close_series, nifty_returns, vix_series = (
                _generate_synthetic_data(n_rows=args.n_rows)
            )
        else:
            print(f"📥 Downloading real NSE data for {args.ticker}...")
            feature_df, close_series, nifty_returns, vix_series = (
                _load_real_data(args.ticker, args.horizon)
            )
    except Exception as e:
        logger.error("data_loading_failed", error=str(e))
        print(f"\n❌ DATA LOADING FAILED: {e}")
        return 2

    # ── Training ─────────────────────────────────────────────────────────────
    print(f"\n🚀 Starting walk-forward training pipeline...")
    print(f"   Rows      : {len(feature_df):,}")
    print(f"   Features  : {len(feature_df.columns)}")
    print(f"   WFO Folds : 8+ expected\n")

    try:
        trainer = IndiaMLTrainer(
            ticker=args.ticker,
            horizon=args.horizon,
            run_optuna=args.run_optuna,
            use_mlflow=args.use_mlflow,
            model_dir=args.model_dir,
        )
        result = trainer.train(
            feature_df=feature_df,
            close_series=close_series,
            nifty_returns=nifty_returns,
            vix_series=vix_series,
        )
    except Exception as e:
        logger.error("training_failed", error=str(e))
        print(f"\n❌ TRAINING FAILED: {e}")
        return 2

    # ── Results ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  TRAINING RESULTS")
    print("=" * 60)
    print(result.summary())
    print()

    wfo = result.wfo_result
    print(f"  Folds    : {wfo.n_folds}")
    print(f"  Accuracy : {wfo.mean_accuracy:.1%} ± {wfo.std_accuracy:.1%}")
    print(f"  Min fold : {wfo.min_accuracy:.1%}")
    print(f"  Gate (≥55%): {'✅ PASSED' if wfo.passes_threshold else '❌ FAILED'}")

    if wfo.passes_threshold:
        print(f"\n✅ Models saved to: {trainer.model_dir}")
        print("   Ready for PredictionService.load_models()")
    else:
        print(f"\n⚠️  Accuracy below 55% threshold ({wfo.mean_accuracy:.1%}).")
        print("   Recommendation: collect more data or re-tune hyperparameters.")

    print("=" * 60 + "\n")
    return 0 if wfo.passes_threshold else 1


if __name__ == "__main__":
    sys.exit(main())
