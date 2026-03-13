"""
Central settings — loaded from .env via Pydantic v2 Settings.
Call get_settings() everywhere. Never read os.environ directly.
"""
from __future__ import annotations
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8",
        case_sensitive=False, extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────────────
    google_api_key: str = ""
    groq_api_key: str = ""
    groq_api_key_1: str = ""
    groq_api_key_2: str = ""
    gemini_model: str = "gemini-2.5-pro-exp-03-25"
    gemini_model_fast: str = "gemini-2.5-flash"
    groq_model_primary: str = "llama-3.3-70b-versatile"
    groq_model_fast: str = "llama3-8b-8192"
    gemini_max_tokens: int = 8192
    groq_max_tokens: int = 4096
    gemini_temperature: float = 0.1
    groq_temperature: float = 0.1

    # ── News ─────────────────────────────────────────────────────────
    finlight_api_key: str = ""

    # ── yfinance tickers ─────────────────────────────────────────────
    yfinance_india_vix_ticker: str = "^INDIAVIX"
    yfinance_nifty_ticker: str = "^NSEI"
    yfinance_banknifty_ticker: str = "^NSEBANK"
    yfinance_usdinr_ticker: str = "USDINR=X"
    yfinance_crude_ticker: str = "BZ=F"
    yfinance_gold_ticker: str = "GC=F"
    yfinance_default_period: str = "2y"
    yfinance_cache_ttl_minutes: int = 15

    # ── NSE scrape config ────────────────────────────────────────────
    nse_request_delay_min: float = 1.0
    nse_request_delay_max: float = 3.0
    nse_max_retries: int = 3
    nse_timeout_seconds: int = 15
    nse_user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
    nse_fallback_enabled: bool = True
    nse_fallback_delay: int = 5

    # ── Social sentiment (no keys needed) ────────────────────────────
    stocktwits_base_url: str = "https://api.stocktwits.com/api/2/streams/symbol"
    stocktwits_rate_limit_delay: int = 18
    rss_cache_ttl_minutes: int = 30

    # ── GDELT ────────────────────────────────────────────────────────
    gdelt_base_url: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    gdelt_maxrecords: int = 50
    gdelt_cache_ttl_minutes: int = 60

    # ── India market ─────────────────────────────────────────────────
    india_timezone: str = "Asia/Kolkata"
    nse_market_open: str = "09:15"
    nse_market_close: str = "15:30"
    nse_weekly_expiry_day: int = 3   # Thursday
    expiry_week_caution_days: int = 2
    fii_data_publish_time: str = "18:00"

    # ── VIX thresholds ───────────────────────────────────────────────
    vix_normal_max: float = 18.0
    vix_elevated_max: float = 25.0
    vix_crisis_threshold: float = 30.0

    # ── ML ───────────────────────────────────────────────────────────
    chronos_model: str = "amazon/chronos-t5-small"
    chronos_prediction_horizons: str = "5,10,30"
    chronos_quantile_levels: str = "0.1,0.5,0.9"
    xgboost_n_classes: int = 5
    xgboost_random_seed: int = 42
    lightgbm_random_seed: int = 42
    hmm_n_regimes: int = 3
    prediction_confidence_threshold: float = 0.55
    optuna_n_trials: int = 50

    # ── Walk-forward ─────────────────────────────────────────────────
    wfo_train_window_days: int = 504
    wfo_test_window_days: int = 63
    wfo_embargo_days: int = 5
    wfo_step_size_days: int = 21
    wfo_min_directional_accuracy: float = 0.55

    # ── Feature engineering ──────────────────────────────────────────
    fii_data_lag_days: int = 1
    feature_shift_days: int = 1
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: int = 2
    adx_period: int = 14
    volume_ma_period: int = 20

    # ── F&O ──────────────────────────────────────────────────────────
    pcr_bullish_threshold: float = 1.2
    pcr_bearish_threshold: float = 0.8
    oi_change_threshold: float = 0.15
    max_pain_gravity_days: int = 2

    # ── Sentiment ────────────────────────────────────────────────────
    finbert_model: str = "ProsusAI/finbert"
    goemotions_model: str = "google/goemotions-bert-base"
    sentiment_batch_size: int = 32
    sentiment_cache_ttl_minutes: int = 120
    fear_greed_extreme_greed: int = 80
    fear_greed_extreme_fear: int = 20

    # ── Vector DB ────────────────────────────────────────────────────
    vector_db: str = "qdrant"
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "india_finance_docs"
    chroma_persist_dir: str = "./storage/chroma_db"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    rag_top_k: int = 5

    # ── Database ─────────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "india_engine"
    postgres_user: str = "engine_user"
    postgres_password: str = "change_this_strong_password"
    sqlite_path: str = "./storage/prediction_logs/predictions.db"

    # ── Feedback ─────────────────────────────────────────────────────
    prediction_log_enabled: bool = True
    accuracy_check_horizon_days: int = 5
    retrain_accuracy_threshold: float = 0.55
    drift_window_days: int = 30

    # ── App ──────────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "change_this_to_random_32char_string"
    model_artifacts_dir: str = "./storage/model_artifacts"
    analysis_history_dir: str = "./storage/analysis_history"

    # ── SEBI ─────────────────────────────────────────────────────────
    max_ops_per_second: int = 10
    static_ip_required: bool = False

    # ── Backtesting ──────────────────────────────────────────────────
    backtest_benchmark_ticker: str = "^NSEI"
    backtest_initial_capital: float = 1_000_000.0
    backtest_commission_pct: float = 0.0003
    backtest_slippage_pct: float = 0.0001

    @property
    def chronos_horizons(self) -> list[int]:
        return [int(x) for x in self.chronos_prediction_horizons.split(",")]

    @property
    def chronos_quantiles(self) -> list[float]:
        return [float(x) for x in self.chronos_quantile_levels.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Singleton — call everywhere. Never instantiate Settings() directly."""
    return Settings()