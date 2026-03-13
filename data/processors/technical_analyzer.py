"""
Technical Analyzer — Primary TA wrapper
Uses pandas-ta-classic==0.3.78 (NOT pandas_ta)

Import convention (from CHANGE_LIST.txt):
    import pandas_ta_classic as ta  ← correct
    import pandas_ta as ta          ← WRONG (no Python 3.11 wheel)

All df.ta.xxx() calls work identically — zero API changes.
"""
import pandas as pd
import numpy as np
import structlog

# CHANGE_LIST.txt Section 3 — correct import
import pandas_ta_classic as ta  # noqa: F401  (registers df.ta accessor)

logger = structlog.get_logger(__name__)


def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute 30 core TA indicators on OHLCV DataFrame.
    All features use .shift(1) — anti-lookahead enforced.

    Args:
        df: DataFrame with columns [open, high, low, close, volume]
            Index: DatetimeIndex in Asia/Kolkata timezone
    Returns:
        DataFrame with all TA columns appended (shifted by 1 day)
    """
    if df.empty:
        raise ValueError("Empty DataFrame passed to compute_all_indicators")

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    # Normalise column names to lowercase
    df = df.copy()
    df.columns = df.columns.str.lower()

    # ── Trend indicators ────────────────────────��────────────────────────────
    df["rsi_14"]       = df.ta.rsi(length=14)
    df["rsi_9"]        = df.ta.rsi(length=9)

    macd = df.ta.macd(fast=12, slow=26, signal=9)
    if macd is not None:
        df["macd_line"]   = macd.get("MACD_12_26_9")
        df["macd_signal"] = macd.get("MACDs_12_26_9")
        df["macd_hist"]   = macd.get("MACDh_12_26_9")

    def _assign_ta(df_series, name):
        if df_series is None:
            return pd.Series(np.nan, index=df.index)
        if isinstance(df_series, pd.DataFrame):
            if not df_series.empty:
                return df_series.iloc[:, 0]
            else:
                return pd.Series(np.nan, index=df.index)
        return df_series

    df["ema_9"]        = _assign_ta(df.ta.ema(length=9), "ema_9")
    df["ema_21"]       = _assign_ta(df.ta.ema(length=21), "ema_21")
    df["ema_50"]       = _assign_ta(df.ta.ema(length=50), "ema_50")
    df["ema_200"]      = _assign_ta(df.ta.ema(length=200), "ema_200")
    df["sma_20"]       = _assign_ta(df.ta.sma(length=20), "sma_20")
    df["sma_50"]       = _assign_ta(df.ta.sma(length=50), "sma_50")

    # ── Volatility indicators ─────────────────────────────────────────────────
    bb = df.ta.bbands(length=20, std=2)
    if bb is not None:
        df["bb_upper"]  = bb.get("BBU_20_2.0")
        df["bb_mid"]    = bb.get("BBM_20_2.0")
        df["bb_lower"]  = bb.get("BBL_20_2.0")
        df["bb_width"]  = (df["bb_upper"] - df["bb_lower"]) / df["bb_mid"]
        df["bb_pct"]    = (df["close"] - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"])

    df["atr_14"]       = df.ta.atr(length=14)
    df["atr_pct"]      = df["atr_14"] / df["close"] * 100  # normalised ATR %

    # ── Momentum indicators ───────────────────────────────────────────────────
    stoch = df.ta.stoch(k=14, d=3, smooth_k=3)
    if stoch is not None:
        df["stoch_k"]   = stoch.get("STOCHk_14_3_3")
        df["stoch_d"]   = stoch.get("STOCHd_14_3_3")

    df["cci_20"]       = df.ta.cci(length=20)
    df["adx_14"]       = df.ta.adx(length=14).get("ADX_14", None)
    df["willr_14"]     = df.ta.willr(length=14)

    # ── Volume indicators ─────────────────────────────────────────────────────
    df["obv"]          = df.ta.obv()
    df["obv_ema"]      = df["obv"].ewm(span=21).mean()
    df["mfi_14"]       = df.ta.mfi(length=14)
    df["volume_sma20"] = df["volume"].rolling(20).mean()
    df["volume_ratio"] = df["volume"] / df["volume_sma20"]  # relative volume

    # ── Trend strength ────────────────────────────────────────────────────────
    supertrend = df.ta.supertrend(length=10, multiplier=3)
    if supertrend is not None:
        # SuperTrend direction: 1 = bullish, -1 = bearish
        st_dir_col = [c for c in supertrend.columns if c.startswith("SUPERTd_")]
        if st_dir_col:
            df["supertrend_dir"] = supertrend[st_dir_col[0]]

    ichimoku = df.ta.ichimoku()
    if ichimoku is not None and len(ichimoku) > 0:
        ichi_df = ichimoku[0]  # returns tuple (span_df, other_df)
        if "ISA_9" in ichi_df.columns:
            df["ichi_span_a"] = ichi_df["ISA_9"]
        if "ISB_26" in ichi_df.columns:
            df["ichi_span_b"] = ichi_df["ISB_26"]

    # ── Price features (no indicator needed) ─────────────────────────────────
    df["pct_change_1d"]  = df["close"].pct_change(1)
    df["pct_change_5d"]  = df["close"].pct_change(5)
    df["pct_change_20d"] = df["close"].pct_change(20)
    df["gap_pct"]        = (df["open"] - df["close"].shift(1)) / df["close"].shift(1)
    df["hl_range_pct"]   = (df["high"] - df["low"]) / df["close"] * 100

    # ── ANTI-LOOKAHEAD: shift all TA features by 1 day ───────────────────────
    # This is the most critical step — no same-day data enters the model
    ta_cols = [c for c in df.columns if c not in
               ["open", "high", "low", "close", "volume"]]
    for col in ta_cols:
        df[col] = df[col].shift(1)

    logger.info(
        "technical_analyzer.computed",
        n_features=len(ta_cols),
        n_rows=len(df),
    )
    return df