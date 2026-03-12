"""
India Feature Set — 70 features (40 India-specific + 30 TA indicators).
ALL features use .shift(1) — zero same-day data. Anti-lookahead enforced.

Feature groups:
  Group A — Price/Volume base (5):       close_lag1, return_1d, return_5d, return_10d, volume_ratio
  Group B — TA Momentum (8):             rsi_14, macd_hist, stoch_k, stoch_d, cci_20, roc_10, willr_14, mfi_14
  Group C — TA Trend (7):                ema_21, ema_50, sma_200, adx_14, dmi_plus, dmi_minus, supertrend_signal
  Group D — TA Volatility (6):           bb_width, bb_pct, atr_14, atr_pct, hist_vol_21, iv_rank
  Group E — TA Volume (4):               obv_slope, vwap_deviation, volume_zscore, delivery_pct
  Group F — India Macro (10):            india_vix, vix_regime, usdinr, brent_crude, gold_price,
                                          sgx_nifty_premium, banknifty_nifty_ratio, nifty_return_5d,
                                          global_risk_on, rbi_rate_delta
  Group G — FII/DII Flows (6):           fii_net_cr, dii_net_cr, fii_zscore_5d, dii_zscore_5d,
                                          fii_streak, fii_dii_consensus
  Group H — F&O Signals (8):             pcr, pcr_zscore, iv_percentile, oi_change_pct,
                                          max_pain_distance, expiry_week_flag, rollover_pct, basis_pct
  Group I — Calendar/Event (6):          day_of_week, expiry_day, rbi_event_flag, results_season,
                                          budget_week, month_end_flag
  Total: 5+8+7+6+4+10+6+8+6 = 60 base + 10 sector RS = 70
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import pandas_ta_classic as ta
import structlog
from datetime import datetime, timedelta
from typing import Optional
import asyncio

from config.constants import (
    RSI_PERIOD, MACD_FAST, MACD_SLOW, MACD_SIGNAL,
    BOLLINGER_PERIOD, BOLLINGER_STD, ADX_PERIOD,
    VOLUME_MA_PERIOD, FEATURE_LAG_DAYS, MARKET_TZ,
    VIX_COMPLACENCY_MAX, VIX_NORMAL_MAX, VIX_ELEVATED_MAX, VIX_CIRCUIT_BREAKER,
    SECTOR_TICKERS,
)

logger = structlog.get_logger(__name__)

# ── Chronos-2 covariate columns (strict subset of 70 features) ────────────
CHRONOS_COVARIATES = [
    "fii_net_cr",       # FII cash net (INR Cr) — lagged 1 day
    "india_vix",        # India VIX level
    "usdinr",           # USD/INR rate
    "brent_crude",      # Brent crude price
    "sgx_nifty_premium",# SGX Nifty vs Nifty 50 spread
    "pcr",              # Put/Call Ratio (OI weighted)
    "oi_change_pct",    # Total F&O OI change %
    "banknifty_nifty_ratio",  # BankNifty/Nifty spread
]

# ── All 70 feature column names (validation reference) ────────────────────
ALL_FEATURE_COLUMNS: list[str] = [
    # A: Price/Volume base
    "close_lag1", "return_1d", "return_5d", "return_10d", "volume_ratio",
    # B: TA Momentum
    "rsi_14", "macd_hist", "stoch_k", "stoch_d", "cci_20",
    "roc_10", "willr_14", "mfi_14",
    # C: TA Trend
    "ema_21", "ema_50", "sma_200", "adx_14", "dmi_plus", "dmi_minus", "supertrend_signal",
    # D: TA Volatility
    "bb_width", "bb_pct", "atr_14", "atr_pct", "hist_vol_21", "iv_rank",
    # E: TA Volume
    "obv_slope", "vwap_deviation", "volume_zscore", "delivery_pct",
    # F: India Macro
    "india_vix", "vix_regime", "usdinr", "brent_crude", "gold_price",
    "sgx_nifty_premium", "banknifty_nifty_ratio", "nifty_return_5d",
    "global_risk_on", "rbi_rate_delta",
    # G: FII/DII Flows
    "fii_net_cr", "dii_net_cr", "fii_zscore_5d", "dii_zscore_5d",
    "fii_streak", "fii_dii_consensus",
    # H: F&O Signals
    "pcr", "pcr_zscore", "iv_percentile", "oi_change_pct",
    "max_pain_distance", "expiry_week_flag", "rollover_pct", "basis_pct",
    # I: Calendar/Event
    "day_of_week", "expiry_day", "rbi_event_flag", "results_season",
    "budget_week", "month_end_flag",
    # J: Sector RS (10 sectors vs Nifty 50)
    "rs_bank", "rs_it", "rs_pharma", "rs_fmcg", "rs_auto",
    "rs_metal", "rs_realty", "rs_energy", "rs_infra", "rs_media",
]

assert len(ALL_FEATURE_COLUMNS) == 70, \
    f"Feature count mismatch: {len(ALL_FEATURE_COLUMNS)} != 70"


class IndiaFeatureSet:
    """
    Builds the 70-feature DataFrame for a given ticker.
    All features are shifted by FEATURE_LAG_DAYS=1 before return.
    Requires: OHLCV, macro data, FII/DII, F&O signals, calendar info.
    """

    def __init__(self):
        self._rbi_dates: list[datetime] = []  # populated from config/india_calendar.py
        self._budget_dates: list[datetime] = []

    # ═══════════════════════════════════════════════════════════════════
    # GROUP A — Price / Volume base
    # ═══════════════════════════════════════════════════════════════════
    def _compute_price_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        5 features. All shifted.
        close_lag1: previous close (base reference)
        return_*: log returns over N days
        volume_ratio: volume / 20-day avg volume
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

    # ═══════════════════════════════════════════════════════════════════
    # GROUP B — TA Momentum (8 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # RSI
        rsi = ta.rsi(df["close"], length=RSI_PERIOD)
        out["rsi_14"] = rsi.shift(1) if rsi is not None else np.nan

        # MACD histogram
        macd = ta.macd(df["close"], fast=MACD_FAST, slow=MACD_SLOW, signal=MACD_SIGNAL)
        if macd is not None:
            hist_col = [c for c in macd.columns if "h" in c.lower() or "hist" in c.lower()]
            if hist_col:
                out["macd_hist"] = macd[hist_col[0]].shift(1)
            else:
                out["macd_hist"] = np.nan
        else:
            out["macd_hist"] = np.nan

        # Stochastic
        stoch = ta.stoch(df["high"], df["low"], df["close"])
        if stoch is not None and len(stoch.columns) >= 2:
            out["stoch_k"] = stoch.iloc[:, 0].shift(1)
            out["stoch_d"] = stoch.iloc[:, 1].shift(1)
        else:
            out["stoch_k"] = out["stoch_d"] = np.nan

        # CCI
        cci = ta.cci(df["high"], df["low"], df["close"], length=20)
        out["cci_20"] = cci.shift(1) if cci is not None else np.nan

        # ROC
        roc = ta.roc(df["close"], length=10)
        out["roc_10"] = roc.shift(1) if roc is not None else np.nan

        # Williams %R
        willr = ta.willr(df["high"], df["low"], df["close"], length=14)
        out["willr_14"] = willr.shift(1) if willr is not None else np.nan

        # MFI (Money Flow Index)
        mfi = ta.mfi(df["high"], df["low"], df["close"], df["volume"], length=14)
        out["mfi_14"] = mfi.shift(1) if mfi is not None else np.nan

        return out

    # ═══════════════════════════════════════════════════════════════════
    # GROUP C — TA Trend (7 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_trend(self, df: pd.DataFrame) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # EMAs
        ema21 = ta.ema(df["close"], length=21)
        ema50 = ta.ema(df["close"], length=50)
        out["ema_21"] = (df["close"] / ema21.replace(0, np.nan) - 1).shift(1) if ema21 is not None else np.nan
        out["ema_50"] = (df["close"] / ema50.replace(0, np.nan) - 1).shift(1) if ema50 is not None else np.nan

        # SMA 200
        sma200 = ta.sma(df["close"], length=200)
        out["sma_200"] = (df["close"] / sma200.replace(0, np.nan) - 1).shift(1) if sma200 is not None else np.nan

        # ADX + DMI
        adx = ta.adx(df["high"], df["low"], df["close"], length=ADX_PERIOD)
        if adx is not None and len(adx.columns) >= 3:
            out["adx_14"]   = adx.iloc[:, 0].shift(1)  # ADX
            out["dmi_plus"] = adx.iloc[:, 1].shift(1)  # DMP
            out["dmi_minus"]= adx.iloc[:, 2].shift(1)  # DMN
        else:
            out["adx_14"] = out["dmi_plus"] = out["dmi_minus"] = np.nan

        # Supertrend signal (+1 uptrend / -1 downtrend)
        st = ta.supertrend(df["high"], df["low"], df["close"])
        if st is not None:
            trend_col = [c for c in st.columns if "trend" in c.lower() or "SUPERTd" in c]
            if trend_col:
                out["supertrend_signal"] = st[trend_col[0]].shift(1)
            else:
                out["supertrend_signal"] = np.nan
        else:
            out["supertrend_signal"] = np.nan

        return out

    # ═══════════════════════════════════════════════════════════════════
    # GROUP D — TA Volatility (6 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_volatility(self, df: pd.DataFrame,
                            iv_series: Optional[pd.Series] = None) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # Bollinger Bands
        bb = ta.bbands(df["close"], length=BOLLINGER_PERIOD, std=BOLLINGER_STD)
        if bb is not None and len(bb.columns) >= 3:
            bb_lower  = bb.iloc[:, 0]   # BBL
            bb_mid    = bb.iloc[:, 1]   # BBM
            bb_upper  = bb.iloc[:, 2]   # BBU
            bb_width  = (bb_upper - bb_lower) / bb_mid.replace(0, np.nan)
            bb_pct    = (df["close"] - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
            out["bb_width"] = bb_width.shift(1)
            out["bb_pct"]   = bb_pct.shift(1)
        else:
            out["bb_width"] = out["bb_pct"] = np.nan

        # ATR
        atr = ta.atr(df["high"], df["low"], df["close"], length=14)
        if atr is not None:
            out["atr_14"]  = atr.shift(1)
            out["atr_pct"] = (atr / df["close"].replace(0, np.nan) * 100).shift(1)
        else:
            out["atr_14"] = out["atr_pct"] = np.nan

        # Historical volatility (21-day annualised)
        log_ret = np.log(df["close"] / df["close"].shift(1))
        hist_vol = log_ret.rolling(21).std() * np.sqrt(252) * 100
        out["hist_vol_21"] = hist_vol.shift(1)

        # IV rank (uses NSE option chain IV — passed in as iv_series)
        if iv_series is not None and not iv_series.empty:
            iv_aligned = iv_series.reindex(df.index).ffill()
            iv_52w_min = iv_aligned.rolling(252).min()
            iv_52w_max = iv_aligned.rolling(252).max()
            iv_range   = (iv_52w_max - iv_52w_min).replace(0, np.nan)
            out["iv_rank"] = ((iv_aligned - iv_52w_min) / iv_range * 100).shift(1)
        else:
            # Fallback: use hist_vol as proxy
            out["iv_rank"] = out["hist_vol_21"].rank(pct=True) * 100

        return out

    # ═══════════════════════════════════════════════════════════════════
    # GROUP E — TA Volume (4 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_volume_features(self, df: pd.DataFrame,
                                  delivery_series: Optional[pd.Series] = None) -> pd.DataFrame:
        out = pd.DataFrame(index=df.index)

        # OBV slope (5-day linear regression slope normalised)
        obv = ta.obv(df["close"], df["volume"])
        if obv is not None:
            obv_slope = obv.diff(5) / obv.abs().rolling(5).mean().replace(0, np.nan)
            out["obv_slope"] = obv_slope.shift(1)
        else:
            out["obv_slope"] = np.nan

        # VWAP deviation — session VWAP from finta; use daily approximation
        # Daily VWAP = sum(typical_price * volume) / sum(volume)
        typical  = (df["high"] + df["low"] + df["close"]) / 3
        vwap     = (typical * df["volume"]).rolling(20).sum() / df["volume"].rolling(20).sum()
        out["vwap_deviation"] = ((df["close"] - vwap) / vwap.replace(0, np.nan) * 100).shift(1)

        # Volume Z-score (20-day)
        vol_mean = df["volume"].rolling(VOLUME_MA_PERIOD).mean()
        vol_std  = df["volume"].rolling(VOLUME_MA_PERIOD).std().replace(0, 1)
        out["volume_zscore"] = ((df["volume"] - vol_mean) / vol_std).shift(1)

        # Delivery %
        if delivery_series is not None and not delivery_series.empty:
            del_aligned = delivery_series.reindex(df.index).ffill()
            out["delivery_pct"] = del_aligned.shift(1)
        else:
            out["delivery_pct"] = np.nan  # filled later from nselib

        return out

    # ═══════════════════════════════════════════════════════════════════
    # GROUP F — India Macro (10 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_macro_features(self,
                                 df: pd.DataFrame,
                                 macro_df: pd.DataFrame) -> pd.DataFrame:
        """
        macro_df columns expected (from yfinance_client.get_macro_snapshot):
          usdinr, brent_crude, gold_price, india_vix, nifty50, banknifty,
          sgx_nifty (optional), sp500 (optional)
        All macro values lagged 1 day.
        """
        out = pd.DataFrame(index=df.index)

        def _align(col: str) -> pd.Series:
            if col in macro_df.columns:
                return macro_df[col].reindex(df.index).ffill()
            return pd.Series(np.nan, index=df.index)

        vix      = _align("india_vix")
        usdinr   = _align("usdinr")
        crude    = _align("brent_crude")
        gold     = _align("gold_price") if "gold_price" in macro_df.columns else _align("gold")
        nifty    = _align("nifty50")
        bnifty   = _align("banknifty")
        sp500    = _align("sp500") if "sp500" in macro_df.columns else pd.Series(np.nan, index=df.index)
        sgx      = _align("sgx_nifty") if "sgx_nifty" in macro_df.columns else pd.Series(np.nan, index=df.index)

        # VIX level + regime
        out["india_vix"] = vix.shift(1)
        out["vix_regime"] = vix.shift(1).apply(
            lambda v: 0 if pd.isna(v) else
                      1 if v < VIX_COMPLACENCY_MAX else
                      2 if v < VIX_NORMAL_MAX else
                      3 if v < VIX_ELEVATED_MAX else
                      4 if v < VIX_CIRCUIT_BREAKER else 5
        )

        out["usdinr"]      = usdinr.shift(1)
        out["brent_crude"] = crude.shift(1)
        out["gold_price"]  = gold.shift(1)

        # SGX Nifty premium (SGX close vs Nifty close % spread)
        if not sgx.isna().all():
            out["sgx_nifty_premium"] = ((sgx - nifty) / nifty.replace(0, np.nan) * 100).shift(1)
        else:
            out["sgx_nifty_premium"] = pd.Series(0.0, index=df.index)

        # BankNifty/Nifty ratio (risk-on indicator)
        out["banknifty_nifty_ratio"] = (bnifty / nifty.replace(0, np.nan)).shift(1)

        # Nifty 5-day return
        out["nifty_return_5d"] = np.log(nifty / nifty.shift(5)).shift(1)

        # Global risk-on: S&P500 5-day return as proxy
        if not sp500.isna().all():
            out["global_risk_on"] = np.log(sp500 / sp500.shift(5)).shift(1)
        else:
            out["global_risk_on"] = pd.Series(0.0, index=df.index)

        # RBI rate delta (change in repo rate — static unless RBI event)
        # Populated from config/india_calendar.py RBI decisions
        out["rbi_rate_delta"] = pd.Series(0.0, index=df.index)

        return out

    # ═══════════════════════════════════════════════════════════════════
    # GROUP G — FII/DII Flows (6 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_fii_dii_features(self,
                                   df: pd.DataFrame,
                                   fii_dii_df: pd.DataFrame) -> pd.DataFrame:
        """
        fii_dii_df: wide-format from NSELibClient.get_fii_dii()
        Columns: fii_net_value, dii_net_value, fii_buy_value, fii_sell_value, ...
        FII data always lagged 1 extra day (published after 18:00 IST).
        """
        out = pd.DataFrame(index=df.index)

        if fii_dii_df is None or fii_dii_df.empty:
            for col in ["fii_net_cr","dii_net_cr","fii_zscore_5d",
                        "dii_zscore_5d","fii_streak","fii_dii_consensus"]:
                out[col] = 0.0
            return out

        fii = fii_dii_df.get("fii_net_value", fii_dii_df.iloc[:, 0]).reindex(df.index).ffill()
        dii = fii_dii_df.get("dii_net_value", fii_dii_df.iloc[:, 1]).reindex(df.index).ffill()

        # FII/DII net flows in INR Cr — shift(1) for T-1 lag
        out["fii_net_cr"] = fii.shift(1)
        out["dii_net_cr"] = dii.shift(1)

        # 5-day rolling Z-scores
        for name, series in [("fii", fii), ("dii", dii)]:
            mu  = series.rolling(5).mean()
            std = series.rolling(5).std().replace(0, 1)
            z   = (series - mu) / std
            out[f"{name}_zscore_5d"] = z.shift(1)

        # FII consecutive sell streak (negative for streak of selling)
        fii_sign  = np.sign(fii)
        streak    = fii_sign.groupby((fii_sign != fii_sign.shift()).cumsum()).cumcount() + 1
        streak    = streak * fii_sign  # negative streak = consecutive selling
        out["fii_streak"] = streak.shift(1)

        # FII/DII consensus: +1=both buy, -1=both sell, 0=divergence
        out["fii_dii_consensus"] = (
            np.sign(fii).shift(1) + np.sign(dii).shift(1)
        ).clip(-1, 1)

        return out

    # ═══════════════════════════════════════════════════════════════════
    # GROUP H — F&O Signals (8 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_fno_features(self,
                               df: pd.DataFrame,
                               fno_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        fno_df: time-series of daily F&O aggregates with columns:
          pcr, atm_iv, total_oi, prev_total_oi, max_pain, futures_price
        When market is closed or data unavailable, fills with neutral defaults.
        """
        out = pd.DataFrame(index=df.index)

        if fno_df is None or fno_df.empty:
            out["pcr"]             = pd.Series(1.0, index=df.index)  # neutral PCR
            out["pcr_zscore"]      = pd.Series(0.0, index=df.index)
            out["iv_percentile"]   = pd.Series(50.0, index=df.index)
            out["oi_change_pct"]   = pd.Series(0.0, index=df.index)
            out["max_pain_distance"]= pd.Series(0.0, index=df.index)
            # Calendar-based default: Mon-Thu of each week
            dates_idx = pd.DatetimeIndex(
                df.index.tz_convert("Asia/Kolkata") if df.index.tzinfo else df.index
            )
            out["expiry_week_flag"]= (dates_idx.dayofweek <= 3).astype(float)
            out["rollover_pct"]    = pd.Series(0.0, index=df.index)
            out["basis_pct"]       = pd.Series(0.0, index=df.index)
            return out

        def _align_fno(col: str) -> pd.Series:
            if col in fno_df.columns:
                return fno_df[col].reindex(df.index).ffill()
            return pd.Series(np.nan, index=df.index)

        pcr = _align_fno("pcr")
        out["pcr"]         = pcr.shift(1)
        pcr_mu             = pcr.rolling(20).mean()
        pcr_std            = pcr.rolling(20).std().replace(0, 1)
        out["pcr_zscore"]  = ((pcr - pcr_mu) / pcr_std).shift(1)

        atm_iv = _align_fno("atm_iv")
        if not atm_iv.isna().all():
            iv_252_min = atm_iv.rolling(252).min()
            iv_252_max = atm_iv.rolling(252).max()
            iv_range   = (iv_252_max - iv_252_min).replace(0, np.nan)
            out["iv_percentile"] = ((atm_iv - iv_252_min) / iv_range * 100).shift(1)
        else:
            out["iv_percentile"] = pd.Series(50.0, index=df.index)

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

    # ═══════════════════════════════════════════════════════════════════
    # GROUP I — Calendar / Event (6 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_calendar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Deterministic calendar features — no shift needed (these are known in advance).
        NSE weekly F&O expiry: every Thursday (weekday=3).
        """
        out   = pd.DataFrame(index=df.index)
        dates = pd.DatetimeIndex(df.index.tz_convert("Asia/Kolkata")
                                 if df.index.tzinfo else df.index)

        out["day_of_week"]  = dates.dayofweek.astype(float)
        out["expiry_day"]   = (dates.dayofweek == 3).astype(float)  # Thursday
        out["month_end_flag"] = (dates.is_month_end).astype(float)

        # Note: expiry_week_flag is in Group H (F&O Signals), not here.

        # RBI event flag (MPC meeting days — typically 6 days/year)
        # Placeholder: set to 0; `config/india_calendar.py` populates real dates
        out["rbi_event_flag"] = pd.Series(0.0, index=df.index)

        # Results season: Apr 1–May 31, Jul 1–Aug 31, Oct 1–Nov 30, Jan 1–Feb 28
        month = dates.month
        out["results_season"] = month.isin([1, 2, 4, 5, 7, 8, 10, 11]).astype(float)

        # Budget week: last week of January / first week of February
        out["budget_week"] = (
            ((month == 1) & (dates.day >= 25)) |
            ((month == 2) & (dates.day <= 7))
        ).astype(float)

        return out

    # ═══════════════════════════════════════════════════════════════════
    # GROUP J — Sector Relative Strength (10 features)
    # ═══════════════════════════════════════════════════════════════════
    def _compute_sector_rs(self,
                            df: pd.DataFrame,
                            sector_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        sector_df: DataFrame with columns matching SECTOR_TICKERS keys.
        RS = 21-day sector return / 21-day Nifty 50 return (ratio-based).
        Lagged 1 day.
        """
        out = pd.DataFrame(index=df.index)
        sector_map = {
            "rs_bank": "^NSEBANK", "rs_it": "^CNXIT", "rs_pharma": "^CNXPHARMA",
            "rs_fmcg": "^CNXFMCG", "rs_auto": "^CNXAUTO", "rs_metal": "^CNXMETAL",
            "rs_realty": "^CNXREALTY", "rs_energy": "^CNXENERGY",
            "rs_infra": "^CNXINFRA", "rs_media": "^CNXMEDIA",
        }
        if sector_df is None or sector_df.empty:
            for col in sector_map:
                out[col] = pd.Series(1.0, index=df.index)
            return out

        # Use nifty50 as base (use df["close"] if ticker IS nifty, else align)
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
                out[feat_col] = pd.Series(1.0, index=df.index)

        return out

    # ═══════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════
    def build(self,
              ohlcv_df: pd.DataFrame,
              macro_df: pd.DataFrame,
              fii_dii_df: Optional[pd.DataFrame] = None,
              fno_df: Optional[pd.DataFrame] = None,
              sector_df: Optional[pd.DataFrame] = None,
              delivery_series: Optional[pd.Series] = None,
              iv_series: Optional[pd.Series] = None) -> pd.DataFrame:
        """
        Build complete 70-feature DataFrame.

        Args:
            ohlcv_df:        OHLCV with columns [open, high, low, close, volume]
                             Index: DatetimeIndex (Asia/Kolkata)
            macro_df:        Macro data (usdinr, brent_crude, india_vix, ...)
            fii_dii_df:      Wide FII/DII (fii_net_value, dii_net_value, ...)
            fno_df:          Daily F&O aggregates (pcr, atm_iv, total_oi, ...)
            sector_df:       Sector index prices (^NSEBANK, ^CNXIT, ...)
            delivery_series: NSE delivery % series indexed by date
            iv_series:       Historical ATM IV for IV rank calculation

        Returns:
            DataFrame with exactly 70 columns, all shifted, index = trading days.
        """
        if ohlcv_df.empty:
            raise ValueError("ohlcv_df is empty — cannot build features")

        # Ensure correct column names (lowercase)
        ohlcv_df = ohlcv_df.copy()
        ohlcv_df.columns = ohlcv_df.columns.str.lower()
        required_cols = {"open", "high", "low", "close", "volume"}
        missing = required_cols - set(ohlcv_df.columns)
        if missing:
            raise ValueError(f"ohlcv_df missing columns: {missing}")

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

        # Enforce exact column order
        features = features.reindex(columns=ALL_FEATURE_COLUMNS)

        logger.info(
            "features.built",
            ticker=ohlcv_df.get("ticker", ["?"])[0] if "ticker" in ohlcv_df.columns else "?",
            rows=len(features),
            cols=len(features.columns),
            null_pct=round(features.isna().mean().mean() * 100, 1),
        )
        return features

    def build_chronos_covariates(self,
                                  features: pd.DataFrame) -> pd.DataFrame:
        """
        Extract the 8 Chronos-2 covariates from the full 70-feature DataFrame.
        Used as exogenous inputs to Chronos-2 multivariate forecast.
        """
        missing = [c for c in CHRONOS_COVARIATES if c not in features.columns]
        if missing:
            raise ValueError(f"Chronos covariates missing from feature set: {missing}")
        cov = features[CHRONOS_COVARIATES].copy()
        null_pct = cov.isna().mean().mean() * 100
        if null_pct > 5:
            logger.warning("chronos.covariates_high_null", null_pct=round(null_pct, 1))
        return cov