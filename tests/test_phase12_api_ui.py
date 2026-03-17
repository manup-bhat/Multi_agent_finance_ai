"""
Phase 12: API + UI integration contract checks.

These tests call route functions directly instead of FastAPI's TestClient.
That avoids the environment-specific TestClient hang while still validating:
  - response shape for each production API route
  - schema validation constraints
  - UI page presence on disk
"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

import pandas as pd
import pytest
from pydantic import ValidationError

from api.routes.analyze import analyze
from api.routes.backtest import run_backtest
from api.routes.fii_dii import fii_dii_latest
from api.routes.fno import fno_analyze
from api.routes.health import health
from api.routes.macro import india_cues
from api.routes.predict import predict
from api.schemas import AnalyzeRequest, BacktestRequest, FnORequest, PredictRequest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

UI_PAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui", "pages"))


def _price_df(rows: int = 320, ticker: str = "HDFCBANK.NS") -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="B", tz="Asia/Kolkata")
    close = pd.Series(range(rows), index=idx, dtype=float) + 1500.0
    return pd.DataFrame(
        {
            "open": close * 0.998,
            "high": close * 1.01,
            "low": close * 0.99,
            "close": close,
            "volume": 1_000_000.0,
            "ticker": ticker,
        },
        index=idx,
    )


def _macro_df(rows: int = 320) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="B", tz="Asia/Kolkata")
    return pd.DataFrame(
        {
            "usdinr": 83.2,
            "brent_crude": 82.5,
            "gold": 2050.0,
            "nifty50": 22000.0,
            "banknifty": 47000.0,
            "india_vix": 15.5,
        },
        index=idx,
    )


def _vix_df(rows: int = 120) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="B", tz="Asia/Kolkata")
    return pd.DataFrame({"vix": 15.5, "regime": "NORMAL"}, index=idx)


def _fii_df(rows: int = 40) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=rows, freq="B", tz="Asia/Kolkata")
    return pd.DataFrame(
        {
            "fii_net_value": [1000.0] * rows,
            "dii_net_value": [500.0] * rows,
        },
        index=idx,
    )


def _option_chain() -> pd.DataFrame:
    rows = []
    for strike in [21500, 21600, 21700]:
        rows.append(
            {
                "strike_price": strike,
                "option_type": "CE",
                "open_interest": 100000 + strike,
                "change_in_open_interest": 1000,
                "implied_volatility": 14.0,
            }
        )
        rows.append(
            {
                "strike_price": strike,
                "option_type": "PE",
                "open_interest": 120000 + strike,
                "change_in_open_interest": 900,
                "implied_volatility": 15.0,
            }
        )
    return pd.DataFrame(rows)


def _backtest_result() -> SimpleNamespace:
    idx = pd.date_range("2024-01-01", periods=20, freq="B", tz="Asia/Kolkata")
    equity = pd.Series([100000 + i * 750 for i in range(len(idx))], index=idx)
    return SimpleNamespace(
        sharpe_ratio=1.12,
        cagr_pct=18.6,
        max_drawdown_pct=7.4,
        metrics=SimpleNamespace(win_rate_pct=58.4),
        n_trades=6,
        equity_curve=equity,
    )


@pytest.mark.asyncio
async def test_health_route_returns_expected_contract():
    result = await health()
    assert result.status in {"healthy", "degraded"}
    assert result.version == "12.0.0"
    assert isinstance(result.modules, dict)
    assert "backtesting" in result.modules


@pytest.mark.asyncio
async def test_analyze_route_returns_structured_response(monkeypatch):
    async def fake_get_ohlcv(self, ticker, period="1y", interval="1d"):
        return _price_df(ticker=ticker)

    async def fake_macro_snapshot(self, period="1y"):
        return _macro_df()

    async def fake_vix(self, period="6mo"):
        return _vix_df()

    async def fake_fii_latest():
        from api.schemas import FIIDIIResponse
        return FIIDIIResponse(
            date="2024-03-01",
            fii_net_crore=1000.0,
            dii_net_crore=500.0,
            fii_trend="BUYING",
            fii_streak_days=2,
            consensus="STRONG_BULL",
        )

    async def fake_prediction_response(req):
        from api.schemas import PredictResponse
        return PredictResponse(
            ticker=req.ticker,
            horizon=req.horizon,
            direction="BULLISH",
            direction_prob=0.7,
            class_probs={"Bullish": 0.7},
            p10=1500.0,
            p50=1520.0,
            p90=1545.0,
            confidence=0.72,
            regime="BULL",
            model_used="statistical_live_fallback",
        )

    async def fake_sentiment_response(ticker, sources=None):
        from api.routes.sentiment import ArticleItem, SentimentResponse
        return SentimentResponse(
            ticker=ticker,
            composite_score=0.3,
            composite_label="BULLISH",
            fear_greed_index=58.0,
            fear_greed_label="GREED",
            articles=[ArticleItem(source="et_markets", headline="Strong outlook", sentiment=1.0, label="POSITIVE", date="2024-03-01")],
        )

    async def fake_option_chain(self, symbol):
        return _option_chain()

    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_ohlcv", fake_get_ohlcv)
    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_macro_snapshot", fake_macro_snapshot)
    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_india_vix", fake_vix)
    monkeypatch.setattr("api.routes.analyze.fii_dii_latest", fake_fii_latest)
    monkeypatch.setattr("api.routes.analyze.build_live_prediction_response", fake_prediction_response)
    monkeypatch.setattr("api.routes.analyze.build_live_sentiment_response", fake_sentiment_response)
    monkeypatch.setattr("data.adapters.nsefin_client.NSEFinClient.get_option_chain", fake_option_chain)
    monkeypatch.setattr("agents.graph.workflow.build_workflow", lambda: (_ for _ in ()).throw(RuntimeError("skip llm")))

    result = await analyze(AnalyzeRequest(ticker="HDFCBANK.NS", horizon=5))
    assert result.ticker == "HDFCBANK.NS"
    assert result.verdict in {"BUY", "STRONG_BUY", "HOLD", "SELL", "STRONG_SELL"}
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.key_risks, list)


@pytest.mark.asyncio
async def test_predict_route_returns_live_forecast_shape(monkeypatch):
    async def fake_get_ohlcv(self, ticker, period="3y", interval="1d"):
        return _price_df(ticker=ticker)

    async def fake_macro_snapshot(self, period="3y"):
        return _macro_df()

    async def fake_fii(self, days=90):
        return _fii_df()

    async def fake_vix(self, period="3y"):
        return _vix_df()

    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_ohlcv", fake_get_ohlcv)
    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_macro_snapshot", fake_macro_snapshot)
    monkeypatch.setattr("data.adapters.nselib_client.NSELibClient.get_fii_dii", fake_fii)
    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_india_vix", fake_vix)
    monkeypatch.setattr(
        "prediction.inference.prediction_service.PredictionService.predict",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("no model")),
    )

    result = await predict(PredictRequest(ticker="HDFCBANK.NS", horizon=5, regime="BULL"))
    assert result.direction in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert 0.0 <= result.confidence <= 1.0
    assert result.regime == "BULL"


@pytest.mark.asyncio
async def test_fno_route_returns_live_contract(monkeypatch):
    async def fake_get_ohlcv(self, ticker, period="5d", interval="1d"):
        return _price_df(rows=5, ticker=ticker)

    async def fake_get_option_chain(self, symbol):
        return _option_chain()

    async def fake_participant_oi(self):
        return pd.DataFrame()

    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_ohlcv", fake_get_ohlcv)
    monkeypatch.setattr("data.adapters.nsefin_client.NSEFinClient.get_option_chain", fake_get_option_chain)
    monkeypatch.setattr("data.adapters.nselib_client.NSELibClient.get_participant_oi", fake_participant_oi)

    result = await fno_analyze(FnORequest(symbol="BANKNIFTY"))
    assert result["pcr"] is not None
    assert "max_pain" in result


@pytest.mark.asyncio
async def test_macro_route_returns_vix_regime(monkeypatch):
    async def fake_macro_snapshot(self, period="6mo"):
        return _macro_df()

    async def fake_fii_latest():
        from api.schemas import FIIDIIResponse
        return FIIDIIResponse(
            date="2024-03-01",
            fii_net_crore=1000.0,
            dii_net_crore=500.0,
            fii_trend="BUYING",
            fii_streak_days=2,
            consensus="STRONG_BULL",
        )

    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_macro_snapshot", fake_macro_snapshot)
    monkeypatch.setattr("api.routes.macro.fii_dii_latest", fake_fii_latest)

    result = await india_cues()
    assert result.vix_regime in {"COMPLACENCY", "NORMAL", "ELEVATED", "EXTREME", "UNKNOWN"}
    assert len(result.india_summary) > 10


@pytest.mark.asyncio
async def test_fii_dii_route_returns_live_shape(monkeypatch):
    async def fake_get_fii_dii(self, days=90):
        return _fii_df()

    monkeypatch.setattr("data.adapters.nselib_client.NSELibClient.get_fii_dii", fake_get_fii_dii)

    result = await fii_dii_latest()
    assert result.date
    assert result.fii_trend in {"BUYING", "SELLING", "UNKNOWN", "NEUTRAL"}
    assert result.consensus in {"STRONG_BULL", "STRONG_BEAR", "FII_BULL_DII_BEAR", "DII_BULL_FII_BEAR", "UNKNOWN"}


@pytest.mark.asyncio
async def test_backtest_route_returns_blueprint_fields(monkeypatch):
    async def fake_get_ohlcv(self, ticker, period="2y", interval="1d"):
        return _price_df(rows=120, ticker=ticker)

    async def fake_get_india_vix(self, period="2y"):
        return _vix_df(rows=120)

    async def fake_get_fii_dii(self, days=504):
        return _fii_df(rows=120)

    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_ohlcv", fake_get_ohlcv)
    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_india_vix", fake_get_india_vix)
    monkeypatch.setattr("data.adapters.nselib_client.NSELibClient.get_fii_dii", fake_get_fii_dii)
    monkeypatch.setattr("backtesting.engine.BacktestEngine.run", lambda *args, **kwargs: _backtest_result())

    result = await run_backtest(BacktestRequest(strategy="mean_reversion", ticker="BANKNIFTY", years=2))
    assert isinstance(result.sharpe_ratio, float)
    assert isinstance(result.blueprint_gate_passed, bool)
    assert len(result.equity_curve) > 0


class TestUIPageFiles:

    @pytest.mark.parametrize("page_name", [
        "1_Dashboard.py", "2_Technical.py", "3_Predictions.py",
        "4_Emotion_Analysis.py", "5_FnO_Analysis.py", "6_FII_DII_Tracker.py",
        "7_Macro_India.py", "8_Sector_Rotation.py", "9_News_Sentiment.py",
        "10_Risk_Monitor.py", "11_Backtest_Results.py", "12_Model_Performance.py",
        "13_Audit_Trail.py",
    ])
    def test_page_file_exists(self, page_name):
        path = os.path.join(UI_PAGES_DIR, page_name)
        assert os.path.isfile(path), f"Missing UI page: {page_name}"

    def test_app_py_exists(self):
        path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui", "app.py"))
        assert os.path.isfile(path), "ui/app.py missing"

    def test_all_13_pages_present(self):
        pages = [f for f in os.listdir(UI_PAGES_DIR) if f.endswith(".py")]
        assert len(pages) >= 13, f"Expected 13 pages, found {len(pages)}"


class TestAPISchemas:

    def test_analyze_request_valid(self):
        req = AnalyzeRequest(ticker="HDFCBANK.NS", horizon=5)
        assert req.ticker == "HDFCBANK.NS"
        assert req.horizon == 5

    def test_analyze_request_invalid_horizon(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(ticker="HDFCBANK.NS", horizon=365)

    def test_backtest_request_valid(self):
        req = BacktestRequest(strategy="mean_reversion", ticker="BANKNIFTY", years=5)
        assert req.strategy == "mean_reversion"

    def test_backtest_request_invalid_strategy(self):
        with pytest.raises(ValidationError):
            BacktestRequest(strategy="invalid_strategy", ticker="BANKNIFTY", years=2)
