"""Pydantic v2 schemas for all market data. Timezone: Asia/Kolkata. Currency: INR."""
from __future__ import annotations
from datetime import date, datetime
from typing import Optional
import pandas as pd
from pydantic import BaseModel, Field, field_validator


class OHLCVBar(BaseModel):
    timestamp: datetime
    open:   float = Field(gt=0)
    high:   float = Field(gt=0)
    low:    float = Field(gt=0)
    close:  float = Field(gt=0)
    volume: float = Field(ge=0)
    ticker: str

    @field_validator("timestamp", mode="before")
    @classmethod
    def ensure_ist(cls, v: datetime) -> datetime:
        ts = pd.Timestamp(v)
        return ts.tz_localize("Asia/Kolkata") if ts.tzinfo is None else ts.tz_convert("Asia/Kolkata")

    @field_validator("high")
    @classmethod
    def high_gte_low(cls, v: float, info) -> float:
        if "low" in info.data and v < info.data["low"]:
            raise ValueError("high must be >= low")
        return v


class IndiaVIXBar(BaseModel):
    date: date
    vix: float = Field(gt=0, lt=200)
    regime: str  # COMPLACENCY | NORMAL | ELEVATED | HIGH | CRISIS

    @field_validator("regime")
    @classmethod
    def valid_regime(cls, v: str) -> str:
        valid = {"COMPLACENCY", "NORMAL", "ELEVATED", "HIGH", "CRISIS"}
        if v not in valid:
            raise ValueError(f"regime must be one of {valid}")
        return v


class FIIDIIRecord(BaseModel):
    date: date
    fii_buy_value: float    # INR Crore
    fii_sell_value: float
    fii_net_value: float
    dii_buy_value: float
    dii_sell_value: float
    dii_net_value: float

    @property
    def consensus(self) -> str:
        fb, db = self.fii_net_value > 0, self.dii_net_value > 0
        if fb and db:   return "STRONG_BULL"
        if not fb and not db: return "STRONG_BEAR"
        return "FII_BULL_DII_BEAR" if fb else "DII_BULL_FII_BEAR"


class MacroSnapshot(BaseModel):
    date: date
    india_vix:   Optional[float] = None
    usdinr:      Optional[float] = None
    brent_crude: Optional[float] = None
    gold:        Optional[float] = None
    sp500:       Optional[float] = None
    nifty50:     Optional[float] = None
    banknifty:   Optional[float] = None


class AdapterResult(BaseModel):
    source: str
    ticker: str
    success: bool
    rows: int = 0
    error: Optional[str] = None
    fetched_at: datetime = Field(
        default_factory=lambda: pd.Timestamp.now(tz="Asia/Kolkata")
    )