from __future__ import annotations

import json

from utils.llm_router import LLMBudgetTracker, LLMRouter


def test_budget_tracker_transitions_by_usage(tmp_path):
    tracker = LLMBudgetTracker(
        path=tmp_path / "budget.json",
        groq_daily_token_budget=100,
        gemini_daily_call_budget=10,
    )

    assert tracker.groq_stage() == "normal"

    tracker.record_groq_usage("fast", 20, 20)
    assert tracker.groq_stage() == "normal"

    tracker.record_groq_usage("fast", 10, 20)
    assert tracker.groq_stage() == "economy"

    tracker.record_groq_usage("fast", 5, 10)
    assert tracker.groq_stage() == "emergency"

    tracker.record_groq_usage("fast", 10, 0)
    assert tracker.groq_stage() == "survival"


def test_route_agent_call_cascades_on_low_confidence_fast_output(tmp_path, monkeypatch):
    tracker = LLMBudgetTracker(path=tmp_path / "budget.json")
    router = LLMRouter(budget_tracker=tracker)
    calls: list[str] = []

    def fake_groq_text(**kwargs):
        calls.append(kwargs["model_role"])
        if len(calls) == 1:
            return (
                "QUANT VERDICT: BULLISH\n"
                "STRENGTH: MODERATE\n"
                "KEY SIGNALS:\n- RSI positive\n- MACD positive\n- Trend improving\n"
                "INDIA-SPECIFIC NOTES: Broad market stable.\n"
                "CONFIDENCE: LOW"
            )
        return (
            "QUANT VERDICT: BULLISH\n"
            "STRENGTH: STRONG\n"
            "KEY SIGNALS:\n- RSI above 60\n- MACD expanding\n- EMA alignment bullish\n"
            "INDIA-SPECIFIC NOTES: Nifty breadth supports continuation.\n"
            "CONFIDENCE: HIGH"
        )

    monkeypatch.setattr(router, "_has_groq_key", lambda: True)
    monkeypatch.setattr(router, "_call_groq_text", fake_groq_text)

    result = router.route_agent_call("quant_agent", "sys", "user")

    assert "CONFIDENCE: HIGH" in result
    assert calls == ["fast", "primary"]


def test_route_agent_call_economy_mode_keeps_simple_agents_on_fast_only(tmp_path, monkeypatch):
    tracker = LLMBudgetTracker(path=tmp_path / "budget.json")
    router = LLMRouter(budget_tracker=tracker)
    calls: list[str] = []

    def fake_groq_text(**kwargs):
        calls.append(kwargs["model_role"])
        return (
            "EMOTION VERDICT: GREED\n"
            "INDIA FEAR/GREED: 68 and elevated optimism.\n"
            "INSTITUTIONAL SENTIMENT: Positive.\n"
            "RETAIL SENTIMENT: Euphoric.\n"
            "GDELT INDIA TONE: Supportive.\n"
            "CONTRARIAN SIGNAL: Watch for overheating.\n"
            "CONFIDENCE: LOW"
        )

    monkeypatch.setattr(router, "_has_groq_key", lambda: True)
    monkeypatch.setattr(tracker, "groq_stage", lambda: "economy")
    monkeypatch.setattr(router, "_call_groq_text", fake_groq_text)

    result = router.route_agent_call("emotion_agent", "sys", "user")

    assert "EMOTION VERDICT" in result
    assert calls == ["fast"]


def test_route_agent_call_survival_mode_uses_local_fallback(tmp_path, monkeypatch):
    tracker = LLMBudgetTracker(path=tmp_path / "budget.json")
    router = LLMRouter(budget_tracker=tracker)

    monkeypatch.setattr(tracker, "groq_stage", lambda: "survival")
    monkeypatch.setattr(router, "_has_groq_key", lambda: True)
    monkeypatch.setattr(
        router,
        "_call_groq_text",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("Groq should not be called")),
    )
    monkeypatch.setattr(router, "_call_local_text", lambda **kwargs: "LOCAL_RESULT")

    result = router.route_agent_call("macro_agent", "sys", "user")

    assert result == "LOCAL_RESULT"


def test_extract_json_uses_json_mode_and_normalises_ticker(tmp_path, monkeypatch):
    tracker = LLMBudgetTracker(path=tmp_path / "budget.json")
    router = LLMRouter(budget_tracker=tracker)
    captured: dict[str, object] = {}

    def fake_groq_text(**kwargs):
        captured["response_format"] = kwargs["response_format"]
        return '{"ticker":"reliance.bo","price":2850.5}'

    monkeypatch.setattr(router, "_call_groq_text", fake_groq_text)

    result = router.extract_json("Reliance closed at 2850.5 on NSE")

    assert captured["response_format"] == {"type": "json_object"}
    data = json.loads(result)
    assert data["ticker"] == "RELIANCE.NS"


def test_preprocess_news_trims_to_five_bullets(tmp_path, monkeypatch):
    tracker = LLMBudgetTracker(path=tmp_path / "budget.json")
    router = LLMRouter(budget_tracker=tracker)
    monkeypatch.setattr(
        router,
        "_call_local_text",
        lambda **kwargs: "\n".join(f"* line {idx}" for idx in range(7)),
    )

    result = router.preprocess_news(
        [{"title": f"title {idx}", "summary": "summary"} for idx in range(7)]
    )

    assert result.count("\n") == 4
    assert result.splitlines()[0].startswith("- ")
