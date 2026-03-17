from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from api.routes.analyze import analyze
from api.routes.backtest import run_backtest
from api.routes.fii_dii import fii_dii_latest
from api.routes.fno import fno_analyze
from api.routes.macro import india_cues
from api.routes.predict import predict
from api.routes.sentiment import analyze_sentiment
from api.schemas import AnalyzeRequest, BacktestRequest, FnORequest, PredictRequest


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
    metrics = SimpleNamespace(win_rate_pct=58.4)
    return SimpleNamespace(
        sharpe_ratio=1.12,
        cagr_pct=18.6,
        max_drawdown_pct=7.4,
        metrics=metrics,
        n_trades=6,
        equity_curve=equity,
    )


@pytest.mark.asyncio
async def test_macro_route_with_mocked_live_data(monkeypatch):
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
    assert result.vix == 15.5
    assert result.fii_trend == "BUYING"


@pytest.mark.asyncio
async def test_fii_route_uses_real_report_builder(monkeypatch):
    async def fake_get_fii_dii(self, days=90):
        return _fii_df()

    monkeypatch.setattr("data.adapters.nselib_client.NSELibClient.get_fii_dii", fake_get_fii_dii)

    result = await fii_dii_latest()
    assert result.fii_net_crore == 1000.0
    assert result.fii_trend == "BUYING"


@pytest.mark.asyncio
async def test_fno_route_no_demo_values(monkeypatch):
    async def fake_get_ohlcv(self, ticker, period="5d", interval="1d"):
        return _price_df(rows=5, ticker=ticker)

    async def fake_get_option_chain(self, symbol, expiry=None):
        return _option_chain()

    async def fake_participant_oi(self):
        return pd.DataFrame()

    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_ohlcv", fake_get_ohlcv)
    monkeypatch.setattr("data.adapters.nsefin_client.NSEFinClient.get_option_chain", fake_get_option_chain)
    monkeypatch.setattr("data.adapters.nselib_client.NSELibClient.get_participant_oi", fake_participant_oi)

    result = await fno_analyze(FnORequest(symbol="NIFTY"))
    assert result["source"] == "live_fno_engine"
    assert result["pcr"] is not None


@pytest.mark.asyncio
async def test_predict_route_statistical_fallback(monkeypatch):
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
        "features.india_feature_set.IndiaFeatureSet.validate",
        lambda self, features, close_series: SimpleNamespace(passed=True, same_day_leaks=[], null_columns=[]),
    )
    monkeypatch.setattr(
        "prediction.inference.prediction_service.PredictionService.predict",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("no model")),
    )

    result = await predict(PredictRequest(ticker="HDFCBANK.NS", horizon=5))
    assert result.model_used == "statistical_live_fallback"
    assert result.p50 is not None


@pytest.mark.asyncio
async def test_sentiment_route_shape(monkeypatch):
    async def fake_build_live_sentiment_response(ticker, sources=None):
        from api.routes.sentiment import SentimentResponse, ArticleItem

        return SentimentResponse(
            ticker=ticker,
            composite_score=0.42,
            composite_label="BULLISH",
            fear_greed_index=61.0,
            fear_greed_label="GREED",
            social_bullish_pct=68.0,
            social_post_volume=24,
            euphoria_flag=False,
            sentiment_window_days=3,
            articles=[
                ArticleItem(
                    source="et_markets",
                    headline="HDFC Bank gains on strong deposit growth",
                    sentiment=1.0,
                    label="POSITIVE",
                    date="2024-03-01",
                )
            ],
        )

    monkeypatch.setattr("api.routes.sentiment.build_live_sentiment_response", fake_build_live_sentiment_response)

    result = await analyze_sentiment(SimpleNamespace(ticker="HDFCBANK.NS", sources=None))
    assert result.composite_label == "BULLISH"
    assert result.social_bullish_pct == 68.0
    assert len(result.articles) == 1


@pytest.mark.asyncio
async def test_analyze_route_deterministic_fallback(monkeypatch):
    async def fake_get_ohlcv(self, ticker, period="1y", interval="1d"):
        return _price_df(ticker=ticker)

    async def fake_macro_snapshot(self, period="1y"):
        return _macro_df()

    async def fake_vix(self, period="6mo"):
        return _vix_df()

    async def fake_fii(self, days=90):
        return _fii_df()

    async def fake_prediction_response(req, **kwargs):
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

    async def fake_sentiment_response(ticker, sources=None, current_vix=None):
        from api.routes.sentiment import SentimentResponse, ArticleItem
        return SentimentResponse(
            ticker=ticker,
            composite_score=0.3,
            composite_label="BULLISH",
            fear_greed_index=58.0,
            fear_greed_label="GREED",
            social_bullish_pct=70.0,
            social_post_volume=18,
            euphoria_flag=False,
            sentiment_window_days=3,
            articles=[ArticleItem(source="et_markets", headline="Strong outlook", sentiment=1.0, label="POSITIVE", date="2024-03-01")],
        )

    async def fake_option_chain(self, symbol, expiry=None):
        return _option_chain()

    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_ohlcv", fake_get_ohlcv)
    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_macro_snapshot", fake_macro_snapshot)
    monkeypatch.setattr("data.adapters.yfinance_client.YFinanceClient.get_india_vix", fake_vix)
    monkeypatch.setattr("data.adapters.nselib_client.NSELibClient.get_fii_dii", fake_fii)
    monkeypatch.setattr("api.routes.analyze.build_live_prediction_from_frames", fake_prediction_response)
    monkeypatch.setattr("api.routes.analyze.build_live_sentiment_response", fake_sentiment_response)
    monkeypatch.setattr("data.adapters.nsefin_client.NSEFinClient.get_option_chain", fake_option_chain)
    monkeypatch.setattr("agents.graph.workflow.get_workflow", lambda: (_ for _ in ()).throw(RuntimeError("skip llm")))

    result = await analyze(AnalyzeRequest(ticker="HDFCBANK.NS", horizon=5))
    assert result.verdict in {"BUY", "STRONG_BUY", "HOLD"}
    assert result.ticker == "HDFCBANK.NS"
    assert result.quant_summary
    assert result.fear_greed_index == 58.0
    assert result.social_post_volume == 18


@pytest.mark.asyncio
async def test_backtest_route_uses_real_fii_strategy(monkeypatch):
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

    result = await run_backtest(BacktestRequest(strategy="fii_flow", ticker="BANKNIFTY", years=2))
    assert result.strategy == "fii_flow"
    assert result.sharpe_ratio == 1.12
    assert result.n_trades == 6
