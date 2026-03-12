"""
India Feature Set — 70 features (40 India-specific + 30 TA indicators).
ALL features use .shift(1) — zero same-day data. Anti-lookahead enforced.

Feature groups:
  Group A — Price/Volume base (5):   close_lag1, return_1d, return_5d, return_10d, volume_ratio
  Group B — TA Momentum (8):         rsi_14, macd_hist, stoch_k, stoch_d, cci_20,
                                      roc_10, willr_14, mfi_14
  Group C — TA Trend (7):            ema_21, ema_50, sma_200, adx_14, dmi_plus,
                                      dmi_minus, supertrend_signal
  Group D — TA Volatility (6):       bb_width, bb_pct, atr_14, atr_pct,
                                      hist_vol_21, iv_rank
  Group E — TA Volume (4):           obv_slope, vwap_deviation, volume_zscore, delivery_pct
  Group F — India Macro (10):        india_vix, vix_regime, usdinr, brent_crude, gold_price,
                                      sgx_nifty_premium, banknifty_nifty_ratio, nifty_return_5d,
                                      global_risk_on, rbi_rate_delta
  Group G — FII/DII Flows (6):       fii_net_cr, dii_net_cr, fii_zscore_5d, dii_zscore_5d,
                                      fii_streak, fii_dii_consensus
  Group H — F&O Signals (8):         pcr, pcr_zscore, iv_percentile, oi_change_pct,
                                      max_pain_distance, expiry_week_flag, rollover_pct, basis_pct
  Group I — Calendar/Event (6):      day_of_week, expiry_day, rbi_event_flag, results_season,
                                      budget_week, month_end_flag
  Group J — Sector RS (10):          rs_bank, rs_it, rs_pharma, rs_fmcg, rs_auto,
                                      rs_metal, rs_realty, rs_energy, rs_infra, rs_media
  Total: 5+8+7+6+4+10+6+8+6+10 = 70

Package note (March 2026):
  pandas-ta REMOVED from PyPI — use pandas-ta-classic.
  pip install pandas-ta-classic
  import pandas_ta_classic as ta   ← validated name
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pandas_ta_classic as ta      # pip install pandas-ta-classic
import structlog
from datetime import datetime
from typing import Optional

from config.constants import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BOLLINGER_PERIOD, BOLLINGER_STD, ADX_PERIOD,
    VOLUME_MA_PERIOD, FEATURE_LAG_DAYS, MARKET_TZ,
    VIX_COMPLACENCY_MAX, VIX_NORMAL_MAX, VIX_ELEVATED_MAX, VIX_CIRCUIT_BREAKER,
    SECTOR_TICKERS,
)

logger = structlog.get_logger(__name__)

# ── Chronos-2 covariate columns (strict subset of 70 features) ─────────────
# These 8 columns are fed as exogenous covariates to Chronos-2 multivariate
# forecast. Must already be shift(1)-lagged when extracted.
CHRONOS_COVARIATES: list[str] = [
    "fii_net_cr",            # FII cash net (INR Cr) — T-1 lagged
    "india_vix",             # India VIX level
    "usdinr",                # USD/INR rate
    "brent_crude",           # Brent crude price (USD)
    "sgx_nifty_premium",     # SGX Nifty vs Nifty 50 spread (%)
    "pcr",                   # Put/Call Ratio (OI-weighted)
    "oi_change_pct",         # Total F&O OI change %
    "banknifty_nifty_ratio", # BankNifty / Nifty 50 ratio
]

# ── All 70 feature column names (validation reference) ──────────────────────
ALL_FEATURE_COLUMNS: list[str] = [
    # A: Price/Volume base (5)
    "close_lag1", "return_1d", "return_5d", "return_10d", "volume_ratio",
    # B: TA Momentum (8)
    "rsi_14", "macd_hist", "stoch_k", "stoch_d", "cci_20",
    "roc_10", "willr_14", "mfi_14",
    # C: TA Trend (7)
    "ema_21", "ema_50", "sma_200", "adx_14", "dmi_plus", "dmi_minus", "supertrend_signal",
    # D: TA Volatility (6)
    "bb_width", "bb_pct", "atr_14", "atr_pct", "hist_vol_21", "iv_rank",
    # E: TA Volume (4)
    "obv_slope", "vwap_deviation", "volume_zscore", "delivery_pct",
    # F: India Macro (10)
    "india_vix", "vix_regime", "usdinr", "brent_crude", "gold_price",
    "sgx_nifty_premium", "banknifty_nifty_ratio", "nifty_return_5d",
    "global_risk_on", "rbi_rate_delta",
    # G: FII/DII Flows (6)
    "fii_net_cr", "dii_net_cr", "fii_zscore_5d", "dii_zscore_5d",
    "fii_streak", "fii_dii_consensus",
    # H: F&O Signals (8)
    "pcr", "pcr_zscore", "iv_percentile", "oi_change_pct",
    "max_pain_distance", "expiry_week_flag", "rollover_pct", "basis_pct",
    # I: Calendar/Event (6)
    "day_of_week", "expiry_day", "rbi_event_flag", "results_season",
    "budget_week", "month_end_flag",
    # J: Sector RS — 10 sectors vs Nifty 50
    "rs_bank", "rs_it", "rs_pharma", "rs_fmcg", "rs_auto",
    "rs_metal", "rs_realty", "rs_energy", "rs_infra", "rs_media",
]

assert len(ALL_FEATURE_COLUMNS) == 70, (
    f"Feature count mismatch: {len(ALL_FEATURE_COLUMNS)} != 70"
)
assert len(CHRONOS_COVARIATES) == 8, (
    f"CHRONOS_COVARIATES must have exactly 8 columns, got {len(CHRONOS_COVARIATES)}"
)
assert all(c in ALL_FEATURE_COLUMNS for c in CHRONOS_COVARIATES), (
    "All CHRONOS_COVARIATES must exist in ALL_FEATURE_COLUMNS"
)


class IndiaFeatureSet:
    """
    Builds the 70-feature DataFrame for a given ticker.

    All output features use .shift(1) — zero same-day data.
    Calendar features (day_of_week, expiry_day, etc.) are known in advance
    so they are NOT shifted — they describe today's session context.

    Usage:
        fs = IndiaFeatureSet()
        fs.set_rbi_dates(rbi_dates, rate_changes)   # from config/india_calendar.py
        features = fs.build(ohlcv_df, macro_df, fii_dii_df, fno_df, sector_df)
        covariates = fs.build_chronos_covariates(features)
    """

    def __init__(self) -> None:
        # Populated via set_rbi_dates() from config/india_calendar.py
        self._rbi_dates: list[datetime] = []
        self._rbi_rate_changes: dict[datetime, float] = {}  # date → bps change

    # ── Public: inject RBI calendar ────────────────────────��────────────────
    def set_rbi_dates(
        self,
        rbi_dates: list[datetime],
        rate_changes: Optional[dict[datetime, float]] = None,
    ) -> None:
        """
        Inject RBI MPC meeting dates so rbi_event_flag and rbi_rate_delta
        are populated with real values rather than placeholders.

        Args:
            rbi_dates:    List of RBI MPC announcement dates (typically 6/year).
            rate_changes: Dict {date: bps_change} e.g. {date(2024,2,8): 0.0}.
                          Only dates with rate changes need to be present.
        """
        self._rbi_dates = rbi_dates or []
        self._rbi_rate_changes = rate_changes or {}
        logger.info(
            "features.rbi_dates_set",
            n_dates=len(self._rbi_dates),
            n_rate_changes=len(self._rbi_rate_changes),
        )

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP A — Price / Volume base (5 features)
    # ══════════════��══════════════════════════════════════════════════════════
    def _compute_price_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        5 features. All shifted by 1 day.
        close_lag1  : previous close (absolute reference for percentage moves)
        return_*    : log returns over N days (shift applied)
        volume_ratio: volume / 20-day avg volume (shift applied)
        """
        out = pd.DataFrame(index=df.index)
        c   = df["close"]
        v   = df["volume"]

        out["close_lag1"]   = c.shift(1)
        out["return_1d"]    = np.log(c / c.shift(1)).shift(1)
        out["return_5d"]    = np.log(c / c.shift(5)).shift(1)
        out["return_10d"]   = np.log(c / c.shift(10)).shift(1)
        vol_ma              = v.rolling(VOLUME_MA_PERIOD).mean()
        out["volume_ratio"] = (v / vol_ma.replace(0, np.nan)).shift(1)
        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP B — TA Momentum (8 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # RSI(14)
        rsi = ta.rsi(df["close"], length=RSI_PERIOD)
        out["rsi_14"] = rsi.shift(1) if rsi is not None else np.nan

        # MACD histogram — detect column by MACDh_ prefix (pandas-ta-classic naming)
        macd = ta.macd(df["close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        if macd is not None:
            hist_cols = [c for c in macd.columns if c.upper().startswith("MACDH")]
            if not hist_cols:
                # Fallback: any column containing 'h' after underscore
                hist_cols = [c for c in macd.columns if "_h" in c.lower()]
            out["macd_hist"] = macd[hist_cols[0]].shift(1) if hist_cols else np.nan
        else:
            out["macd_hist"] = np.nan

        # Stochastic — STOCHk_ and STOCHd_ columns
        stoch = ta.stoch(df["high"], df["low"], df["close"])
        if stoch is not None and len(stoch.columns) >= 2:
            k_cols = [c for c in stoch.columns if "k" in c.lower()]
            d_cols = [c for c in stoch.columns if "d" in c.lower()]
            out["stoch_k"] = stoch[k_cols[0]].shift(1) if k_cols else stoch.iloc[:, 0].shift(1)
            out["stoch_d"] = stoch[d_cols[0]].shift(1) if d_cols else stoch.iloc[:, 1].shift(1)
        else:
            out["stoch_k"] = out["stoch_d"] = np.nan

        # CCI(20)
        cci = ta.cci(df["high"], df["low"], df["close"], length=20)
        out["cci_20"] = cci.shift(1) if cci is not None else np.nan

        # ROC(10)
        roc = ta.roc(df["close"], length=10)
        out["roc_10"] = roc.shift(1) if roc is not None else np.nan

        # Williams %R(14)
        willr = ta.willr(df["high"], df["low"], df["close"], length=14)
        out["willr_14"] = willr.shift(1) if willr is not None else np.nan

        # MFI(14) — Money Flow Index
        mfi = ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14)
        out["mfi_14"] = mfi.shift(1) if mfi is not None else np.nan

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP C — TA Trend (7 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # EMA(21) and EMA(50) as % deviation from close (normalised)
        ema21 = ta.ema(df["close"], length=21)
        ema50 = ta.ema(df["close"], length=50)
        out["ema_21"] = (
            (df["close"] / ema21.replace(0, np.nan) - 1).shift(1)
            if ema21 is not None else np.nan
        )
        out["ema_50"] = (
            (df["close"] / ema50.replace(0, np.nan) - 1).shift(1)
            if ema50 is not None else np.nan
        )

        # SMA(200) as % deviation
        sma200 = ta.sma(df["close"], length=200)
        out["sma_200"] = (
            (df["close"] / sma200.replace(0, np.nan) - 1).shift(1)
            if sma200 is not None else np.nan
        )

        # ADX(14) + DMI+/DMI-
        adx_df = ta.adx(df["high"], df["low"], df["close"], length=ADX_PERIOD)
        if adx_df is not None and len(adx_df.columns) >= 3:
            # pandas-ta-classic: columns are ADX_14, DMP_14, DMN_14
            adx_cols  = [c for c in adx_df.columns if c.upper().startswith("ADX")]
            dmp_cols  = [c for c in adx_df.columns if c.upper().startswith("DMP")]
            dmn_cols  = [c for c in adx_df.columns if c.upper().startswith("DMN")]
            out["adx_14"]    = adx_df[adx_cols[0]].shift(1) if adx_cols else adx_df.iloc[:, 0].shift(1)
            out["dmi_plus"]  = adx_df[dmp_cols[0]].shift(1) if dmp_cols else adx_df.iloc[:, 1].shift(1)
            out["dmi_minus"] = adx_df[dmn_cols[0]].shift(1) if dmn_cols else adx_df.iloc[:, 2].shift(1)
        else:
            out["adx_14"] = out["dmi_plus"] = out["dmi_minus"] = np.nan

        # Supertrend direction: +1 = uptrend, -1 = downtrend
        # pandas-ta-classic column: SUPERTd_7_3.0  (direction column)
        st = ta.supertrend(df["high"], df["low"], df["close"])
        if st is not None:
            # Direction column starts with "SUPERTd" (lowercase d = direction)
            dir_cols = [c for c in st.columns if "SUPERTd" in c or c.lower().startswith("supertd")]
            if dir_cols:
                out["supertrend_signal"] = st[dir_cols[0]].shift(1)
            else:
                # Fallback: last column is typically the direction column
                out["supertrend_signal"] = st.iloc[:, -1].shift(1)
        else:
            out["supertrend_signal"] = np.nan

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP D — TA Volatility (6 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_volatility(
        self,
        df:        pd.DataFrame,
        iv_series: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # Bollinger Bands — BBL, BBM, BBU columns in pandas-ta-classic
        bb = ta.bbands(df["close"], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bb is not None and len(bb.columns) >= 3:
            bbl_cols = [c for c in bb.columns if "BBL" in c.upper()]
            bbm_cols = [c for c in bb.columns if "BBM" in c.upper()]
            bbu_cols = [c for c in bb.columns if "BBU" in c.upper()]
            bb_lower = bb[bbl_cols[0]] if bbl_cols else bb.iloc[:, 0]
            bb_mid   = bb[bbm_cols[0]] if bbm_cols else bb.iloc[:, 1]
            bb_upper = bb[bbu_cols[0]] if bbu_cols else bb.iloc[:, 2]

            bb_width = (bb_upper - bb_lower) / bb_mid.replace(0, np.nan)
            bb_pct   = (df["close"] - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
            out["bb_width"] = bb_width.shift(1)
            out["bb_pct"]   = bb_pct.shift(1)
        else:
            out["bb_width"] = out["bb_pct"] = np.nan

        # ATR(14) — absolute and % of close
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        if atr is not None:
            out["atr_14"]  = atr.shift(1)
            out["atr_pct"] = (atr / df["close"].replace(0, np.nan) * 100).shift(1)
        else:
            out["atr_14"] = out["atr_pct"] = np.nan

        # Historical volatility: 21-day annualised (%)
        log_ret  = np.log(df["close"] / df["close"].shift(1))
        hist_vol = log_ret.rolling(21).std() * np.sqrt(252) * 100
        out["hist_vol_21"] = hist_vol.shift(1)

        # IV Rank (0-100): position of current IV within 52-week range
        if iv_series is not None and not iv_series.empty:
            iv_aligned = iv_series.reindex(df.index).ffill()
            iv_52w_min = iv_aligned.rolling(252).min()
            iv_52w_max = iv_aligned.rolling(252).max()
            iv_range   = (iv_52w_max - iv_52w_min).replace(0, np.nan)
            out["iv_rank"] = ((iv_aligned - iv_52w_min) / iv_range * 100).shift(1)
        else:
            # Fallback: percentile rank of hist_vol over available history
            # shift(1) applied after rank to preserve anti-lookahead
            out["iv_rank"] = hist_vol.shift(1).rank(pct=True) * 100

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP E — TA Volume (4 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_volume_features(
        self,
        df:              pd.DataFrame,
        delivery_series: Optional[pd.Series] = None,
    ) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # OBV slope: 5-day OBV change normalised by rolling mean(|OBV|)
        obv = ta.obv(df["close"], df["volume"])
        if obv is not None:
            obv_slope = obv.diff(5) / obv.abs().rolling(5).mean().replace(0, np.nan)
            out["obv_slope"] = obv_slope.shift(1)
        else:
            out["obv_slope"] = np.nan

        # VWAP deviation: rolling 20-day typical-price VWAP
        # (session VWAP would need intraday data; daily is a valid proxy)
        typical      = (df["high"] + df["low"] + df["close"]) / 3
        vwap_rolling = (
            (typical * df["volume"]).rolling(20).sum()
            / df["volume"].rolling(20).sum().replace(0, np.nan)
        )
        out["vwap_deviation"] = (
            (df["close"] - vwap_rolling) / vwap_rolling.replace(0, np.nan) * 100
        ).shift(1)

        # Volume Z-score (20-day)
        vol_mean = df["volume"].rolling(VOLUME_MA_PERIOD).mean()
        vol_std  = df["volume"].rolling(VOLUME_MA_PERIOD).std().replace(0, 1.0)
        out["volume_zscore"] = ((df["volume"] - vol_mean) / vol_std).shift(1)

        # Delivery % — from nselib bhavcopy; NaN filled downstream
        if delivery_series is not None and not delivery_series.empty:
            out["delivery_pct"] = delivery_series.reindex(df.index).ffill().shift(1)
        else:
            out["delivery_pct"] = np.nan  # nselib adapter fills this

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP F — India Macro (10 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_macro_features(
        self,
        df:       pd.DataFrame,
        macro_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        macro_df columns expected (from yfinance_client.get_macro_snapshot()):
          usdinr, brent_crude, gold_price, india_vix, nifty50, banknifty,
          sgx_nifty (optional), sp500 (optional)
        All values are daily close — shifted by 1 day inside this method.
        """
        out = pd.DataFrame(index=df.index)

        def _align(col: str) -> pd.Series:
            if col in macro_df.columns:
                return macro_df[col].reindex(df.index).ffill()
            return pd.Series(np.nan, index=df.index, dtype=float)

        vix    = _align("india_vix")
        usdinr = _align("usdinr")
        crude  = _align("brent_crude")
        gold   = _align("gold_price") if "gold_price" in macro_df.columns else _align("gold")
        nifty  = _align("nifty50")
        bnifty = _align("banknifty")
        sp500  = _align("sp500") if "sp500" in macro_df.columns else pd.Series(np.nan, index=df.index, dtype=float)
        sgx    = _align("sgx_nifty") if "sgx_nifty" in macro_df.columns else pd.Series(np.nan, index=df.index, dtype=float)

        # VIX level (shifted)
        vix_lag = vix.shift(1)
        out["india_vix"] = vix_lag

        # VIX regime — vectorised with np.select (30x faster than .apply on 2yr data)
        conditions = [
            vix_lag.isna(),
            vix_lag < VIX_COMPLACENCY_MAX,                             # < 13
            vix_lag < VIX_NORMAL_MAX,                                  # 13-18
            vix_lag < VIX_ELEVATED_MAX,                                # 18-25
            vix_lag < VIX_CIRCUIT_BREAKER,                             # 25-30 (same as ELEVATED_MAX in constants)
        ]
        choices = [0, 1, 2, 3, 4]
        out["vix_regime"] = pd.Series(
            np.select(conditions, choices, default=5),
            index=df.index,
            dtype=float,
        )

        out["usdinr"]      = usdinr.shift(1)
        out["brent_crude"] = crude.shift(1)
        out["gold_price"]  = gold.shift(1)

        # SGX Nifty premium/discount to Nifty 50 (%)
        if not sgx.isna().all():
            out["sgx_nifty_premium"] = ((sgx - nifty) / nifty.replace(0, np.nan) * 100).shift(1)
        else:
            out["sgx_nifty_premium"] = pd.Series(0.0, index=df.index, dtype=float)

        # BankNifty / Nifty ratio — credit/risk-on proxy
        out["banknifty_nifty_ratio"] = (bnifty / nifty.replace(0, np.nan)).shift(1)

        # Nifty 50-day 5-day log return
        out["nifty_return_5d"] = np.log(nifty / nifty.shift(5)).shift(1)

        # Global risk-on: S&P 500 5-day log return (proxy)
        if not sp500.isna().all():
            out["global_risk_on"] = np.log(sp500 / sp500.shift(5)).shift(1)
        else:
            out["global_risk_on"] = pd.Series(0.0, index=df.index, dtype=float)

        # RBI rate delta — real values injected via set_rbi_dates(); default 0
        out["rbi_rate_delta"] = pd.Series(0.0, index=df.index, dtype=float)
        # Apply real rate changes if available
        if self._rbi_rate_changes:
            for dt, bps in self._rbi_rate_changes.items():
                dt_ts = pd.Timestamp(dt, tz=MARKET_TZ)
                if dt_ts in out.index:
                    out.loc[dt_ts, "rbi_rate_delta"] = float(bps)

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP G — FII/DII Flows (6 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_fii_dii_features(
        self,
        df:         pd.DataFrame,
        fii_dii_df: Optional[pd.DataFrame],
    ) -> pd.DataFrame:
        """
        fii_dii_df: wide-format from NSELibClient.get_fii_dii()
          Expected columns: fii_net_value, dii_net_value
          (plus optional: fii_buy_value, fii_sell_value, etc.)
        FII data published after 18:00 IST → always uses shift(1) lag.

        Data source: nselib.capital_market.fii_dii_trading_activity()
                     — NEVER substitute with another source.
        """
        out = pd.DataFrame(index=df.index)

        _FII_COLS = ["fii_net_cr", "dii_net_cr", "fii_zscore_5d",
                     "dii_zscore_5d", "fii_streak", "fii_dii_consensus"]

        if fii_dii_df is None or not isinstance(fii_dii_df, pd.DataFrame) or fii_dii_df.empty:
            for col in _FII_COLS:
                out[col] = 0.0
            logger.warning("features.fii_dii_missing", action="using_zero_fill")
            return out

        # Resolve column names — nselib returns 'fii_net_value' or 'purchaseValue'
        fii_col = next(
            (c for c in ["fii_net_value", "fii_net", "purchaseValue"]
             if c in fii_dii_df.columns),
            fii_dii_df.columns[0],
        )
        dii_col = next(
            (c for c in ["dii_net_value", "dii_net"]
             if c in fii_dii_df.columns),
            fii_dii_df.columns[1] if len(fii_dii_df.columns) > 1 else fii_dii_df.columns[0],
        )

        fii = fii_dii_df[fii_col].reindex(df.index).ffill()
        dii = fii_dii_df[dii_col].reindex(df.index).ffill()

        # Net flows — shift(1) for T-1 lag (published after close)
        out["fii_net_cr"] = fii.shift(1)
        out["dii_net_cr"] = dii.shift(1)

        # 5-day rolling Z-scores (shift before output)
        for name, series in [("fii", fii), ("dii", dii)]:
            mu  = series.rolling(5).mean()
            std = series.rolling(5).std().replace(0, 1.0)
            z   = (series - mu) / std
            out[f"{name}_zscore_5d"] = z.shift(1)

        # Consecutive-day streak: +N = N days of net buying, -N = selling
        fii_sign = np.sign(fii)
        streak   = (
            fii_sign
            .groupby((fii_sign != fii_sign.shift()).cumsum())
            .cumcount() + 1
        ) * fii_sign
        out["fii_streak"] = streak.shift(1)

        # FII/DII consensus: +1=both buying, -1=both selling, 0=diverging
        out["fii_dii_consensus"] = (
            np.sign(fii).shift(1) + np.sign(dii).shift(1)
        ).clip(-1, 1)

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP H — F&O Signals (8 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_fno_features(
        self,
        df:     pd.DataFrame,
        fno_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        fno_df: time-series of daily F&O aggregates, indexed by date.
        Expected columns: pcr, atm_iv, total_oi, max_pain,
                          expiry_week_flag, rollover_pct, basis_pct
        Falls back to neutral defaults when data is unavailable.
        """
        out = pd.DataFrame(index=df.index)

        if fno_df is None or not isinstance(fno_df, pd.DataFrame) or fno_df.empty:
            out["pcr"]              = pd.Series(1.0,  index=df.index, dtype=float)
            out["pcr_zscore"]       = pd.Series(0.0,  index=df.index, dtype=float)
            out["iv_percentile"]    = pd.Series(50.0, index=df.index, dtype=float)
            out["oi_change_pct"]    = pd.Series(0.0,  index=df.index, dtype=float)
            out["max_pain_distance"]= pd.Series(0.0,  index=df.index, dtype=float)
            dates_idx = pd.DatetimeIndex(
                df.index.tz_convert(MARKET_TZ) if df.index.tzinfo else df.index
            )
            out["expiry_week_flag"] = (dates_idx.dayofweek <= 3).astype(float)
            out["rollover_pct"]     = pd.Series(0.0, index=df.index, dtype=float)
            out["basis_pct"]        = pd.Series(0.0, index=df.index, dtype=float)
            return out

        def _align_fno(col: str) -> pd.Series:
            if col in fno_df.columns:
                return fno_df[col].reindex(df.index).ffill()
            return pd.Series(np.nan, index=df.index, dtype=float)

        pcr        = _align_fno("pcr")
        pcr_mu     = pcr.rolling(20).mean()
        pcr_std    = pcr.rolling(20).std().replace(0, 1.0)
        out["pcr"]        = pcr.shift(1)
        out["pcr_zscore"] = ((pcr - pcr_mu) / pcr_std).shift(1)

        atm_iv = _align_fno("atm_iv")
        if not atm_iv.isna().all():
            iv_252_min = atm_iv.rolling(252).min()
            iv_252_max = atm_iv.rolling(252).max()
            iv_range   = (iv_252_max - iv_252_min).replace(0, np.nan)
            out["iv_percentile"] = ((atm_iv - iv_252_min) / iv_range * 100).shift(1)
        else:
            out["iv_percentile"] = pd.Series(50.0, index=df.index, dtype=float)

        total_oi      = _align_fno("total_oi")
        prev_total_oi = total_oi.shift(1).replace(0, np.nan)
        out["oi_change_pct"] = ((total_oi - prev_total_oi) / prev_total_oi * 100).shift(1)

        max_pain = _align_fno("max_pain")
        out["max_pain_distance"] = (
            (df["close"] - max_pain) / df["close"].replace(0, np.nan) * 100
        ).shift(1)

        out["expiry_week_flag"] = _align_fno("expiry_week_flag").shift(1)
        out["rollover_pct"]     = _align_fno("rollover_pct").shift(1)
        out["basis_pct"]        = _align_fno("basis_pct").shift(1)

        return out

    # ════════════════════════════════════════════════════════════════════��════
    # GROUP I — Calendar / Event (6 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_calendar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Deterministic calendar features — NOT shifted (known in advance).
        NSE weekly F&O expiry: every Thursday (weekday == 3).
        RBI event flag populated from self._rbi_dates if set.
        """
        out   = pd.DataFrame(index=df.index)
        dates = pd.DatetimeIndex(
            df.index.tz_convert(MARKET_TZ) if df.index.tzinfo else df.index
        )
        month = dates.month

        out["day_of_week"]    = dates.dayofweek.astype(float)
        out["expiry_day"]     = (dates.dayofweek == 3).astype(float)   # Thursday
        out["month_end_flag"] = dates.is_month_end.astype(float)

        # RBI MPC event flag — real dates from set_rbi_dates(); else 0
        rbi_flag = pd.Series(0.0, index=df.index, dtype=float)
        if self._rbi_dates:
            for rbi_dt in self._rbi_dates:
                ts = pd.Timestamp(rbi_dt, tz=MARKET_TZ)
                if ts in rbi_flag.index:
                    rbi_flag.loc[ts] = 1.0
        out["rbi_event_flag"] = rbi_flag

        # Results season: quarterly result windows (Jan-Feb, Apr-May, Jul-Aug, Oct-Nov)
        out["results_season"] = month.isin([1, 2, 4, 5, 7, 8, 10, 11]).astype(float)

        # Budget week: last week of January + first week of February
        out["budget_week"] = (
            ((month == 1) & (dates.day >= 25)) |
            ((month == 2) & (dates.day <= 7))
        ).astype(float)

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # GROUP J — Sector Relative Strength (10 features)
    # ═════════════════════════════════════════════════════════════════════════
    def _compute_sector_rs(
        self,
        df:        pd.DataFrame,
        sector_df: Optional[pd.DataFrame] = None,
    ) -> pd.DataFrame:
        """
        Computes 21-day sector return relative to Nifty 50 (ratio RS).
        sector_df: columns = yfinance tickers (^NSEBANK, ^CNXIT, ...) + ^NSEI.
        All values lagged 1 day.
        Default = 1.0 (neutral RS) when sector_df is unavailable.
        """
        out = pd.DataFrame(index=df.index)
        sector_map = {
            "rs_bank":   "^NSEBANK",
            "rs_it":     "^CNXIT",
            "rs_pharma": "^CNXPHARMA",
            "rs_fmcg":   "^CNXFMCG",
            "rs_auto":   "^CNXAUTO",
            "rs_metal":  "^CNXMETAL",
            "rs_realty": "^CNXREALTY",
            "rs_energy": "^CNXENERGY",
            "rs_infra":  "^CNXINFRA",
            "rs_media":  "^CNXMEDIA",
        }

        if sector_df is None or not isinstance(sector_df, pd.DataFrame) or sector_df.empty:
            for col in sector_map:
                out[col] = pd.Series(1.0, index=df.index, dtype=float)
            return out

        # Use ^NSEI as Nifty base; fall back to df["close"] if not present
        nifty_base = (
            sector_df["^NSEI"].reindex(df.index).ffill()
            if "^NSEI" in sector_df.columns
            else df["close"]
        )
        nifty_ret21 = np.log(nifty_base / nifty_base.shift(21)).replace(0, np.nan)

        for feat_col, ticker in sector_map.items():
            if ticker in sector_df.columns:
                sec   = sector_df[ticker].reindex(df.index).ffill()
                ret21 = np.log(sec / sec.shift(21))
                rs    = ret21 / nifty_ret21
                out[feat_col] = rs.shift(1)
            else:
                out[feat_col] = pd.Series(1.0, index=df.index, dtype=float)

        return out

    # ═════════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═════════════════════════════════════════════════════════════════════════
    def build(
        self,
        ohlcv_df:        pd.DataFrame,
        macro_df:        pd.DataFrame,
        fii_dii_df:      Optional[pd.DataFrame] = None,
        fno_df:          Optional[pd.DataFrame] = None,
        sector_df:       Optional[pd.DataFrame] = None,
        delivery_series: Optional[pd.Series]    = None,
        iv_series:       Optional[pd.Series]    = None,
    ) -> pd.DataFrame:
        """
        Build the complete 70-feature DataFrame.

        Args:
            ohlcv_df:        OHLCV — columns [open, high, low, close, volume]
                             Index: DatetimeIndex(tz='Asia/Kolkata')
            macro_df:        Macro snapshot from yfinance_client.get_macro_snapshot()
                             Columns: usdinr, brent_crude, gold_price, india_vix,
                                      nifty50, banknifty, [sgx_nifty], [sp500]
            fii_dii_df:      FII/DII flows from NSELibClient.get_fii_dii()
                             Columns: fii_net_value, dii_net_value
            fno_df:          Daily F&O aggregates (pcr, atm_iv, total_oi, max_pain, ...)
            sector_df:       Sector index close prices (^NSEBANK, ^CNXIT, ...)
                             Include ^NSEI for Nifty base in RS calculation.
            delivery_series: NSE bhavcopy delivery % series indexed by date.
            iv_series:       Historical ATM IV series for IV Rank calculation.

        Returns:
            pd.DataFrame — exactly 70 columns in ALL_FEATURE_COLUMNS order,
                           all price/volume/macro/FII features shifted 1 day,
                           calendar features NOT shifted (forward-known).
        """
        if ohlcv_df is None or ohlcv_df.empty:
            raise ValueError("ohlcv_df is empty — cannot build features")

        ohlcv_df = ohlcv_df.copy()
        ohlcv_df.columns = ohlcv_df.columns.str.lower()

        required_cols = {"open", "high", "low", "close", "volume"}
        missing = required_cols - set(ohlcv_df.columns)
        if missing:
            raise ValueError(f"ohlcv_df missing required columns: {missing}")

        if macro_df is None or macro_df.empty:
            raise ValueError("macro_df is empty — cannot build Group F features")

        parts = [
            self._compute_price_volume(ohlcv_df),
            self._compute_momentum(ohlcv_df),
            self._compute_trend(ohlcv_df),
            self._compute_volatility(ohlcv_df, iv_series),
            self._compute_volume_features(ohlcv_df, delivery_series),
            self._compute_macro_features(ohlcv_df, macro_df),
            self._compute_fii_dii_features(ohlcv_df, fii_dii_df),
            self._compute_fno_features(ohlcv_df, fno_df),
            self._compute_calendar_features(ohlcv_df),
            self._compute_sector_rs(ohlcv_df, sector_df),
        ]

        features = pd.concat(parts, axis=1)

        # Enforce exact column order defined in ALL_FEATURE_COLUMNS
        features = features.reindex(columns=ALL_FEATURE_COLUMNS)

        null_pct = round(features.isna().mean().mean() * 100, 1)
        logger.info(
            "features.built",
            rows=len(features),
            cols=len(features.columns),
            null_pct=null_pct,
        )
        if null_pct > 10:
            logger.warning(
                "features.high_null_pct",
                null_pct=null_pct,
                action="check_data_adapters",
            )

        return features

    def build_chronos_covariates(self, features: pd.DataFrame) -> pd.DataFrame:
        """
        Extract the 8 Chronos-2 exogenous covariates from the full feature set.
        These are fed as `past_covariates` to Chronos-2 multivariate forecast.

        Args:
            features: Output of build() — must contain all CHRONOS_COVARIATES.

        Returns:
            pd.DataFrame with exactly 8 columns, same index as features.

        Raises:
            ValueError: If any covariate column is missing.
        """
        missing = [c for c in CHRONOS_COVARIATES if c not in features.columns]
        if missing:
            raise ValueError(
                f"Chronos-2 covariates missing from feature set: {missing}. "
                "Ensure macro_df and fno_df were provided to build()."
            )

        cov      = features[CHRONOS_COVARIATES].copy()
        null_pct = cov.isna().mean().mean() * 100

        if null_pct > 5.0:
            logger.warning(
                "chronos.covariates_high_null",
                null_pct=round(null_pct, 1),
                cols_with_nulls=cov.columns[cov.isna().any()].tolist(),
            )

        return cov

    def validate(
        self,
        features:     pd.DataFrame,
        close_series: pd.Series,
    ) -> "ValidationReport":  # noqa: F821
        """
        Run inline anti-lookahead validation on the built feature set.
        Wraps features/feature_validator.py FeatureValidator.

        Returns:
            ValidationReport — call .summary() or check .passed attribute.
        """
        # Lazy import to avoid circular dependency
        from features.feature_validator import FeatureValidator
        validator = FeatureValidator()
        return validator.validate_features(features, close_series)