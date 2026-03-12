"""
Application-wide constants for the India Multi-Agent Financial Engine.
All values sourced from .env via settings.py, or hardcoded where they are
deterministic rules (VIX thresholds, lot sizes, market timings).

NEVER import from settings.py here — constants.py must be importable with
zero side-effects (no Pydantic validation, no env file reads).
"""
from __future__ import annotations

# ── Timezone ──────────────────────────────────────────────────────────────
MARKET_TZ = "Asia/Kolkata"
NSE_OPEN   = "09:15"
NSE_CLOSE  = "15:30"

# ── India VIX Regime Thresholds ──────────────────────────────────────────
# Used by: macro/india_vix_monitor.py, risk/circuit_breaker.py,
#          features/india_feature_set.py (vix_regime encoding 0-5)
VIX_COMPLACENCY_MAX  = 13.0   # regime 1: below 13 = complacency (sell premium)
VIX_NORMAL_MAX       = 18.0   # regime 2: 13-18 = normal (all signals valid)
VIX_ELEVATED_MAX     = 25.0   # regime 3: 18-25 = elevated (reduce size 30%)
VIX_CIRCUIT_BREAKER  = 25.0   # regime 4: ≥25 = hard override to HOLD/CASH
VIX_CRISIS_THRESHOLD = 30.0   # regime 5: ≥30 = crisis (force CASH/GOLD only)
VIX_CRISIS           = VIX_CRISIS_THRESHOLD  # alias used by yfinance_client.py

# ── Sector Index Tickers (yfinance) ──────────────────────────────────────
# Values match yfinance ticker symbols for each NSE sectoral index.
# Keys are short names used in sector_rotation.py and features.
SECTOR_TICKERS: dict[str, str] = {
    "bank":    "^NSEBANK",
    "it":      "^CNXIT",
    "pharma":  "^CNXPHARMA",
    "fmcg":    "^CNXFMCG",
    "auto":    "^CNXAUTO",
    "metal":   "^CNXMETAL",
    "realty":  "^CNXREALTY",
    "energy":  "^CNXENERGY",
    "infra":   "^CNXINFRA",
    "media":   "^CNXMEDIA",
}

# ── NSE Index Symbols (for option chain routing) ─────────────────────────
# These use /api/option-chain-indices; everything else uses /api/option-chain-equities
NSE_INDEX_SYMBOLS: frozenset[str] = frozenset({
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "SENSEX", "NIFTYIT",
})

# ── F&O / Expiry ─────────────────────────────────────────────────────────
NSE_WEEKLY_EXPIRY_WEEKDAY  = 3    # 3 = Thursday (0=Monday … 6=Sunday)
EXPIRY_CAUTION_DAYS_BEFORE = 2    # flag caution N days before expiry
FII_DATA_PUBLISH_HOUR_IST  = 18   # NSE publishes FII data after 18:00 IST
FEATURE_LAG_DAYS           = 1    # ALL features shifted 1 day (anti-lookahead)

# ── TA Indicator Parameters ───────────────────────────────────────────────
# Used by: features/india_feature_set.py, data/processors/technical_analyzer.py
RSI_PERIOD       = 14
MACD_FAST        = 12
MACD_SLOW        = 26
MACD_SIGNAL      = 9
BOLLINGER_PERIOD = 20
BOLLINGER_STD    = 2.0
ADX_PERIOD       = 14
VOLUME_MA_PERIOD = 20
ATR_PERIOD       = 14
CCI_PERIOD       = 20
ROC_PERIOD       = 10
WILLR_PERIOD     = 14
MFI_PERIOD       = 14
STOCH_K          = 14
STOCH_D          = 3
EMA_SHORT        = 21
EMA_LONG         = 50
SMA_LONG         = 200
HIST_VOL_PERIOD  = 21    # historical volatility lookback (trading days)
OBV_SLOPE_PERIOD = 5     # OBV slope lookback

# ── PCR Thresholds ────────────────────────────────────────────────────────
PCR_BULLISH_THRESHOLD = 1.2   # PCR > 1.2 = bullish signal
PCR_BEARISH_THRESHOLD = 0.8   # PCR < 0.8 = bearish signal
PCR_EXTREME_HIGH      = 1.5   # extreme PCR = likely market bottom

# ── FII Flow Alert Thresholds ─────────────────────────────────────────────
FII_SELL_STREAK_ALERT_DAYS   = 7      # consecutive days of net selling
FII_SELL_ALERT_AMOUNT_CR     = 2000   # INR crore threshold per day

# ── Walk-Forward Optimisation (WFO) Parameters ───────────────────────────
# Used by: features/feature_engineer.py, prediction/training/india_walk_forward.py
# Source: blueprint §Build Phases — all values in TRADING DAYS
WFO_TRAIN_WINDOW_DAYS = 504   # 2 trading years
WFO_TEST_WINDOW_DAYS  = 63    # 3 trading months
WFO_EMBARGO_DAYS      = 5     # gap between train end and test start
WFO_STEP_SIZE_DAYS    = 21    # roll forward 1 trading month per fold
WFO_MIN_FOLDS         = 8     # minimum folds for statistical validity
WFO_MIN_DIRECTIONAL_ACCURACY = 0.55  # retrain trigger threshold

# ── Model / Prediction Config ─────────────────────────────────────────────
XGBOOST_N_CLASSES             = 5     # Very Bullish / Bullish / Neutral / Bearish / Very Bearish
PREDICTION_CONFIDENCE_THRESHOLD = 0.55
HMM_N_REGIMES                 = 3     # Bull / Sideways / Bear
HMM_REFIT_EVERY_DAYS          = 63    # refit HMM every 63 trading days
OPTUNA_N_TRIALS               = 50
OPTUNA_TIMEOUT_SECONDS        = 300

# ── Chronos-2 Config ──────────────────────────────────────────────────────
CHRONOS_N_COVARIATES     = 8
CHRONOS_HORIZONS         = [5, 10, 30]          # days ahead
CHRONOS_QUANTILE_LEVELS  = [0.1, 0.5, 0.9]      # confidence bands

# ── Sentiment Weights ─────────────────────────────────────────────────────
# Must sum to 1.0. Adjusted dynamically in composite_sentiment.py.
SENTIMENT_WEIGHT_FINBERT      = 0.35   # ProsusAI/finbert institutional
SENTIMENT_WEIGHT_FEAR_GREED   = 0.25   # Google GoEmotions India retail
SENTIMENT_WEIGHT_GDELT        = 0.20   # GDELT macro tone
SENTIMENT_WEIGHT_EARNINGS     = 0.20   # finbert-tone earnings call

FEAR_GREED_EXTREME_GREED = 80   # above = contrarian sell signal
FEAR_GREED_EXTREME_FEAR  = 20   # below = contrarian buy signal

# ── Backtesting ───────────────────────────────────────────────────────────
BACKTEST_COMMISSION_PCT = 0.0003   # 0.03% per trade (NSE standard)
BACKTEST_SLIPPAGE_PCT   = 0.0001   # 0.01% slippage estimate
BACKTEST_INITIAL_CAPITAL_INR = 1_000_000  # INR 10 lakhs default

# ── SEBI Compliance ───────────────────────────────────────────────────────
MAX_OPS_PER_SECOND   = 10    # SEBI hard limit April 2026
RATE_LIMIT_WINDOW_S  = 1     # token bucket window in seconds

# ── Devil's Advocate Agent Weights ────────────────────────────────────────
DEVILS_ADVOCATE_WEIGHT_LOW_CONF = 1.5   # amplify when confidence < 55%
DEVILS_ADVOCATE_WEIGHT_HIGH_VIX = 1.3   # amplify when VIX > 20