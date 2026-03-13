"""
FastAPI Route Schemas — Pydantic request/response models for all endpoints.
Shared across all route modules.
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Optional, Literal


# ── Request Models ─────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    ticker:       str   = Field(..., description="NSE ticker (with .NS suffix)", json_schema_extra={"example": "HDFCBANK.NS"})
    horizon:      int   = Field(5, ge=1, le=30, description="Forecast horizon in trading days")
    include_fno:  bool  = Field(True, description="Include F&O analysis")
    include_sentiment: bool = Field(True, description="Include sentiment analysis")

class PredictRequest(BaseModel):
    ticker:   str  = Field(..., json_schema_extra={"example": "RELIANCE.NS"})
    horizon:  int  = Field(5, ge=1, le=30)
    regime:   Optional[Literal["BULL", "BEAR", "SIDEWAYS"]] = None

class FnORequest(BaseModel):
    symbol:  str           = Field(..., description="Index or equity symbol", json_schema_extra={"example": "BANKNIFTY"})
    expiry:  Optional[str] = Field(None, description="Expiry date YYYY-MM-DD (None = nearest)")

class BacktestRequest(BaseModel):
    strategy: Literal["mean_reversion", "ema_momentum", "vix_gated", "fii_flow"] = "mean_reversion"
    ticker:   str = Field("BANKNIFTY", json_schema_extra={"example": "BANKNIFTY"})
    years:    int = Field(5, ge=1, le=10, description="Backtest window in years")


# ── Response Models ────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status:  str
    version: str
    modules: dict[str, str]

class AnalyzeResponse(BaseModel):
    ticker:         str
    verdict:        str
    confidence:     float
    price_target_p10: Optional[float]
    price_target_p50: Optional[float]
    price_target_p90: Optional[float]
    regime:         str
    risk_level:     str
    quant_summary:  str
    macro_summary:  str
    fno_summary:    str
    emotion_summary: str
    key_risks:      list[str]
    circuit_breaker_active: bool
    vix_current:    Optional[float]

class PredictResponse(BaseModel):
    ticker:             str
    horizon:            int
    direction:          str
    direction_prob:     float
    class_probs:        Optional[dict[str, float]] = None
    p10:                Optional[float] = None
    p50:                Optional[float] = None
    p90:                Optional[float] = None
    confidence:         float
    regime:             str
    model_used:         str

class MacroResponse(BaseModel):
    vix:            Optional[float]
    vix_regime:     str
    usdinr:         Optional[float]
    brent_crude:    Optional[float]
    fii_net_crore:  Optional[float]
    fii_trend:      str
    sgx_nifty:      Optional[float]
    global_cues:    str
    india_summary:  str

class FIIDIIResponse(BaseModel):
    date:           str
    fii_net_crore:  Optional[float]
    dii_net_crore:  Optional[float]
    fii_trend:      str
    fii_streak_days: int
    consensus:      str

class BacktestResponse(BaseModel):
    strategy:       str
    ticker:         str
    sharpe_ratio:   float
    cagr_pct:       float
    max_drawdown_pct: float
    win_rate_pct:   float
    n_trades:       int
    blueprint_gate_passed: bool
    dates:          list[str]     = Field(default_factory=list)
    equity_curve:   list[float]   = Field(default_factory=list)
    benchmark_curve: list[float]  = Field(default_factory=list)
