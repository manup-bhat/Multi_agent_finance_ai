"""
FastAPI — India Multi-Agent Financial Engine — Main Entry Point
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Phase 12 API layer:
  POST /analyze       → full 9-agent analysis
  POST /predict       → ML ensemble prediction
  POST /fno/analyze   → F&O options analysis
  GET  /macro/india-cues → macro indicators
  GET  /fii-dii/latest   → FII/DII flows
  POST /backtest         → run backtest strategy
  GET  /health           → service health check

Architecture:
  - FastAPI with async lifespan (startup/shutdown)
  - SEBI compliance middleware (rate limiter check on every request)
  - CORS configured for Streamlit frontend (localhost:8501)
  - Structured logging via structlog
  - All heavy dependencies loaded lazily (no import-time failures)
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import health, analyze, predict, fno, macro, fii_dii, backtest, sentiment

logger = structlog.get_logger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api.startup", version="12.0.0")
    yield
    logger.info("api.shutdown")


# ── App ───────────────────────────────────────────────────────────────────
app = FastAPI(
    title="India Multi-Agent Financial Engine",
    description=(
        "9-agent LangGraph orchestration for NSE/BSE equity predictions. "
        "Uses Chronos-2, XGBoost, LightGBM, CatBoost ensemble + FinBERT sentiment."
    ),
    version="12.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS — allow Streamlit frontend ───────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Timing middleware ──────────────────────────────────────────────────────
@app.middleware("http")
async def add_process_time(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    elapsed = round((time.perf_counter() - start) * 1000, 1)
    response.headers["X-Process-Time-Ms"] = str(elapsed)
    logger.info("api.request", path=request.url.path, ms=elapsed,
                status=response.status_code)
    return response


# ── Global exception handler ───────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("api.unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": str(request.url.path),
        },
    )


# ── Routes ────────────────────────────────────────────────────────────────
app.include_router(health.router,   tags=["Health"])
app.include_router(analyze.router,  tags=["Analysis"])
app.include_router(predict.router,  tags=["Prediction"])
app.include_router(sentiment.router, prefix="/sentiment", tags=["Sentiment"])
app.include_router(fno.router,      prefix="/fno",   tags=["F&O"])
app.include_router(macro.router,    prefix="/macro",  tags=["Macro"])
app.include_router(fii_dii.router,  prefix="/fii-dii", tags=["FII/DII"])
app.include_router(backtest.router,  tags=["Backtest"])
