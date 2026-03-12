-- India Multi-Agent Financial Prediction Engine
-- Initial DB schema for Phase 0

-- Prediction logs table (populated from Phase 10 feedback loop)
CREATE TABLE IF NOT EXISTS predictions (
    id              SERIAL PRIMARY KEY,
    ticker          VARCHAR(20) NOT NULL,
    analysis_date   TIMESTAMP WITH TIME ZONE NOT NULL,
    horizon_days    INTEGER NOT NULL,
    verdict         VARCHAR(20) NOT NULL,
    confidence      FLOAT,
    predicted_price_p10  FLOAT,   -- 10th percentile from Chronos-2
    predicted_price_p50  FLOAT,   -- 50th percentile (median)
    predicted_price_p90  FLOAT,   -- 90th percentile
    direction_class VARCHAR(20),  -- STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
    regime          VARCHAR(20),  -- Bull / Bear / Sideways (from HMM)
    vix_at_time     FLOAT,
    model_version   VARCHAR(50),
    actual_price    FLOAT,        -- Filled by accuracy_tracker.py at T+N
    error_pct       FLOAT,        -- Filled at T+N
    direction_correct BOOLEAN,    -- Filled at T+N
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_predictions_ticker_date 
    ON predictions (ticker, analysis_date);

CREATE INDEX IF NOT EXISTS idx_predictions_regime 
    ON predictions (regime);

-- Model performance tracking
CREATE TABLE IF NOT EXISTS model_performance (
    id              SERIAL PRIMARY KEY,
    model_name      VARCHAR(100) NOT NULL,
    model_version   VARCHAR(50) NOT NULL,
    regime          VARCHAR(20),
    window_start    DATE NOT NULL,
    window_end      DATE NOT NULL,
    directional_acc FLOAT,
    sharpe_ratio    FLOAT,
    total_trades    INTEGER,
    created_at      TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- API key usage tracking (for rate limit compliance)
CREATE TABLE IF NOT EXISTS api_usage (
    id              SERIAL PRIMARY KEY,
    source          VARCHAR(50) NOT NULL,  -- yfinance, nsefin, nselib, etc.
    endpoint        VARCHAR(200),
    called_at       TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    response_ms     INTEGER,
    success         BOOLEAN
);

CREATE INDEX IF NOT EXISTS idx_api_usage_source_time 
    ON api_usage (source, called_at);