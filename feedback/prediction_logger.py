"""
Prediction Logger — SQLite/PostgreSQL via SQLAlchemy
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Blueprint (Stage 4 — Feedback Loop):
  Log prediction → PostgreSQL (ticker, date, predicted, confidence)
  T+N: APScheduler runs accuracy_tracker.py → compare vs actual

This module handles:
  - DB schema creation (SQLite default / PostgreSQL in production)
  - Writing one row per analysis run
  - Retrieving rows for accuracy tracking

Schema (predictions table):
  id                 INTEGER PK (auto)
  ticker             TEXT NOT NULL
  analysis_date      DATE NOT NULL
  horizon_days       INTEGER NOT NULL (5/10/30)
  predicted_verdict  TEXT NOT NULL (STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL)
  predicted_p10      REAL — 10th percentile price target
  predicted_p50      REAL — 50th percentile price target (median)
  predicted_p90      REAL — 90th percentile price target
  confidence         REAL — 0.0 to 1.0
  market_regime      TEXT — BULL/SIDEWAYS/BEAR (HMM)
  vix_at_prediction  REAL — India VIX at time of prediction
  model_version      TEXT — MLflow run ID or timestamp
  actual_price_tn    REAL — filled in by accuracy_tracker.py at T+N
  actual_direction   TEXT — BULLISH/BEARISH/FLAT (filled in at T+N)
  directional_match  INTEGER — 1=correct, 0=wrong (filled in at T+N)
  pct_error          REAL — |actual - p50| / p50 (filled in at T+N)
  created_at         DATETIME (auto)
  updated_at         DATETIME (auto, updated on accuracy fill)
"""
from __future__ import annotations

import datetime
import os
import structlog
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator, Optional

from sqlalchemy import (
    Column, Integer, Float, String, Date, DateTime, Text,
    create_engine, inspect, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = structlog.get_logger(__name__)

# ─── Default DB (SQLite for dev, PostgreSQL for production) ───────────────
_DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///storage/predictions.db",
)


# ─── ORM Model ───────────────────────────────────────────────────────────
class _Base(DeclarativeBase):
    pass


class PredictionRecord(_Base):
    __tablename__ = "predictions"

    id                 = Column(Integer, primary_key=True, autoincrement=True)
    ticker             = Column(String(50), nullable=False, index=True)
    analysis_date      = Column(Date, nullable=False, index=True)
    horizon_days       = Column(Integer, nullable=False, default=5)
    predicted_verdict  = Column(String(20), nullable=False)
    predicted_p10      = Column(Float, nullable=True)
    predicted_p50      = Column(Float, nullable=True)
    predicted_p90      = Column(Float, nullable=True)
    confidence         = Column(Float, nullable=True)
    market_regime      = Column(String(20), nullable=True)
    vix_at_prediction  = Column(Float, nullable=True)
    model_version      = Column(String(100), nullable=True)
    actual_price_tn    = Column(Float, nullable=True)
    actual_direction   = Column(String(20), nullable=True)
    directional_match  = Column(Integer, nullable=True)  # 1=correct, 0=wrong
    pct_error          = Column(Float, nullable=True)
    created_at         = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.datetime.utcnow,
                                onupdate=datetime.datetime.utcnow)


@dataclass
class PredictionLog:
    """Input data to log a single prediction."""
    ticker:            str
    analysis_date:     datetime.date
    predicted_verdict: str
    confidence:        float
    horizon_days:      int = 5
    predicted_p10:     Optional[float] = None
    predicted_p50:     Optional[float] = None
    predicted_p90:     Optional[float] = None
    market_regime:     Optional[str] = None
    vix_at_prediction: Optional[float] = None
    model_version:     Optional[str] = None


class PredictionLogger:
    """
    Handles writing and reading prediction logs.

    Usage:
        logger = PredictionLogger()
        logger.log_prediction(PredictionLog(ticker="HDFCBANK.NS", ...))
    """

    def __init__(self, db_url: str = _DEFAULT_DB_URL):
        self.db_url = db_url
        self._engine = create_engine(db_url, echo=False, future=True)
        self._Session = sessionmaker(self._engine, expire_on_commit=False)
        _Base.metadata.create_all(self._engine)
        logger.info("prediction_logger.init", db_url=db_url)

    @contextmanager
    def _session(self) -> Generator[Session, None, None]:
        with self._Session() as session:
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise

    def log_prediction(self, log: PredictionLog) -> int:
        """
        Insert a new prediction row. Returns the new row id.
        """
        record = PredictionRecord(
            ticker=log.ticker,
            analysis_date=log.analysis_date,
            horizon_days=log.horizon_days,
            predicted_verdict=log.predicted_verdict,
            predicted_p10=log.predicted_p10,
            predicted_p50=log.predicted_p50,
            predicted_p90=log.predicted_p90,
            confidence=log.confidence,
            market_regime=log.market_regime,
            vix_at_prediction=log.vix_at_prediction,
            model_version=log.model_version,
        )
        with self._session() as s:
            s.add(record)
            s.flush()
            row_id = int(record.id)

        logger.info(
            "prediction_logger.logged",
            ticker=log.ticker, date=str(log.analysis_date),
            verdict=log.predicted_verdict, id=row_id,
        )
        return row_id

    def fill_actual(
        self,
        row_id: int,
        actual_price_tn: float,
        actual_direction: str,
    ) -> None:
        """
        Fill in actual outcome after T+N days.
        Computes directional_match and pct_error.
        """
        with self._session() as s:
            rec = s.get(PredictionRecord, row_id)
            if rec is None:
                logger.warning("prediction_logger.fill_actual.not_found", id=row_id)
                return

            rec.actual_price_tn  = actual_price_tn
            rec.actual_direction  = actual_direction
            rec.updated_at        = datetime.datetime.utcnow()

            # Directional match: does predicted verdict agree with actual direction?
            predicted_bullish = rec.predicted_verdict in ("STRONG_BUY", "BUY")
            predicted_bearish = rec.predicted_verdict in ("STRONG_SELL", "SELL")
            actual_bullish    = actual_direction == "BULLISH"
            actual_bearish    = actual_direction == "BEARISH"
            rec.directional_match = int(
                (predicted_bullish and actual_bullish)
                or (predicted_bearish and actual_bearish)
                or (rec.predicted_verdict == "HOLD" and actual_direction == "FLAT")
            )

            # % error in price target (P50)
            if rec.predicted_p50 and rec.predicted_p50 > 0:
                rec.pct_error = abs(actual_price_tn - rec.predicted_p50) / rec.predicted_p50
            else:
                rec.pct_error = None

        logger.info(
            "prediction_logger.filled",
            id=row_id, match=rec.directional_match, pct_error=rec.pct_error,
        )

    def get_unresolved(self, as_of_date: datetime.date) -> list[PredictionRecord]:
        """Fetch rows whose T+N date has passed but actual not yet filled."""
        with self._Session() as s:
            rows = (
                s.query(PredictionRecord)
                .filter(PredictionRecord.actual_price_tn.is_(None))
                .filter(
                    text("analysis_date + horizon_days <= :today").bindparams(
                        today=as_of_date.toordinal()
                    )
                    if "sqlite" in self.db_url else
                    text(
                        "analysis_date + (horizon_days * interval '1 day') <= :today"
                    ).bindparams(today=as_of_date)
                )
                .all()
            )
        return list(rows)

    def get_recent(
        self,
        ticker: Optional[str] = None,
        days: int = 30,
    ) -> list[PredictionRecord]:
        """Get rows from the last N days, optionally filtered by ticker."""
        cutoff = datetime.date.today() - datetime.timedelta(days=days)
        with self._Session() as s:
            q = s.query(PredictionRecord).filter(
                PredictionRecord.analysis_date >= cutoff
            )
            if ticker:
                q = q.filter(PredictionRecord.ticker == ticker)
            rows = q.order_by(PredictionRecord.analysis_date.desc()).all()
        return list(rows)
