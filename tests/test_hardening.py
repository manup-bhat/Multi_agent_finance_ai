from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pandas as pd

from agents.orchestrator_agent import run_orchestrator_agent
from agents.state import make_empty_state
from agents.validation_node import run_validation_node
from agents.risk_node import run_risk_node
from config.india_calendar import resolve_sentiment_window_days
from config.settings import Settings
from data.adapters.nsefin_client import NSEFinClient
from prediction.inference.prediction_service import PredictionService, get_prediction_service
from utils.gemini_client import GeminiFailoverClient
from utils.ollama_client import _OLLAMA_HEALTH_CACHE, is_ollama_running


def test_make_empty_state_uses_last_trading_day(monkeypatch):
    monkeypatch.setattr("config.india_calendar.get_last_trading_day", lambda: date(2026, 3, 13))
    state = make_empty_state("HDFCBANK.NS", 5)
    assert state["analysis_date"] == "2026-03-13"


def test_validation_node_blocks_missing_agent_outputs():
    state = make_empty_state("HDFCBANK.NS", 5)
    state["quant_analysis"] = "present"
    result = run_validation_node(state)

    assert result["workflow_validation"]["ready"] is False
    assert "macro_analysis" in result["workflow_validation"]["missing_keys"]
    assert result["verdict"] == "HOLD"
    assert result["confidence"] == 0.0


def test_orchestrator_uses_deterministic_fallback_when_validation_fails(monkeypatch):
    monkeypatch.setattr(
        "agents.orchestrator_agent.call_gemini",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Gemini should not be called")),
    )
    state = make_empty_state("HDFCBANK.NS", 5)
    state["workflow_validation"] = {
        "ready": False,
        "missing_keys": ["macro_analysis", "emotion_analysis"],
    }

    result = run_orchestrator_agent(state)

    assert result["verdict"] == "HOLD"
    assert "validation" in result["orchestrator_report"].lower()


def test_prediction_service_handles_untrained_ticker_without_crashing(tmp_path):
    service = PredictionService(ticker="UNTRAINED.NS", horizon=5, model_dir=tmp_path)
    feature_df = pd.DataFrame([{"dummy": 1.0}])
    price_series = pd.Series([100.0, 101.0, 102.0], dtype=float)
    nifty_returns = pd.Series([0.01, 0.0, -0.005], dtype=float)
    covariate_df = pd.DataFrame([{"dummy": 1.0}])

    result = service.predict(
        feature_df=feature_df,
        price_series=price_series,
        nifty_returns=nifty_returns,
        covariate_df=covariate_df,
        vix_current=15.0,
        vix_series=None,
    )

    assert result.is_high_confidence is False
    assert result.confidence == 0.35
    assert result.top_features[0]["feature"] == "MODEL_AVAILABILITY"


def test_prediction_service_cache_reuses_loaded_service(tmp_path):
    first = get_prediction_service(ticker="HDFCBANK.NS", horizon=5, model_dir=tmp_path)
    second = get_prediction_service(ticker="HDFCBANK.NS", horizon=5, model_dir=tmp_path)
    assert first is second


def test_nsefin_filters_option_chain_to_nearest_expiry():
    client = NSEFinClient()
    chain_df = pd.DataFrame(
        {
            "expiry_date": ["27-Mar-2026", "27-Mar-2026", "03-Apr-2026", "03-Apr-2026"],
            "strike_price": [22000, 22100, 22000, 22100],
            "option_type": ["CE", "PE", "CE", "PE"],
        }
    )

    filtered = client._filter_option_chain_expiry(chain_df)

    assert set(filtered["expiry_date"]) == {"27-Mar-2026"}


def test_ollama_health_check_is_cached(monkeypatch):
    calls = {"count": 0}

    class FakeResponse:
        status_code = 200

    def fake_get(*args, **kwargs):
        calls["count"] += 1
        return FakeResponse()

    monkeypatch.setattr("utils.ollama_client.requests.get", fake_get)
    _OLLAMA_HEALTH_CACHE["checked_at"] = 0.0
    _OLLAMA_HEALTH_CACHE["running"] = False
    _OLLAMA_HEALTH_CACHE["active_url"] = "http://test:11434"

    assert is_ollama_running(force_refresh=True) is True
    assert is_ollama_running() is True
    assert calls["count"] == 1


def test_gemini_client_falls_back_to_flash(monkeypatch):
    client = GeminiFailoverClient()
    client._settings = SimpleNamespace(
        google_api_key="test-key",
        gemini_model="gemini-pro",
        gemini_model_fast="gemini-flash",
    )
    seen_models: list[str] = []

    class FailingLLM:
        def invoke(self, messages):
            raise RuntimeError("429 quota exceeded")

    class WorkingLLM:
        def invoke(self, messages):
            return SimpleNamespace(content="flash response")

    def fake_build_llm(*, model_name: str, max_tokens: int, temperature: float):
        seen_models.append(model_name)
        if model_name == "gemini-pro":
            return FailingLLM()
        return WorkingLLM()

    monkeypatch.setattr(client, "_build_llm", fake_build_llm)

    result = client.chat(system_prompt="sys", user_message="user")

    assert result["content"] == "flash response"
    assert result["model"] == "gemini-flash"
    assert seen_models == ["gemini-pro", "gemini-flash"]


def test_settings_accept_gemini_fallback_alias(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL_FALLBACK", "gemini-flash-alias")
    cfg = Settings(_env_file=None)
    assert cfg.gemini_model_fast == "gemini-flash-alias"


def test_resolve_sentiment_window_uses_event_day(monkeypatch):
    monkeypatch.setattr(
        "config.india_calendar.get_market_calendar_context",
        lambda reference=None: {"event_flag": "EXPIRY_DAY"},
    )
    assert resolve_sentiment_window_days() == 1


def test_risk_node_reduces_size_on_euphoria():
    state = make_empty_state("HDFCBANK.NS", 5)
    state["vix_signal"] = {"current_vix": 14.0, "regime": "NORMAL"}
    state["fii_dii_report"] = {"sell_streak_days": 0}
    state["composite_sent"] = {
        "fear_greed_index": 85,
        "social_post_volume": 42,
        "euphoria_flag": True,
    }
    state["confidence"] = 0.8

    result = run_risk_node(state)

    assert result["risk_node_output"]["euphoria_flag"] is True
    assert result["risk_node_output"]["position_size_multiplier"] < 1.0
    assert any("EUPHORIA" in note for note in result["risk_node_output"]["notes"])
