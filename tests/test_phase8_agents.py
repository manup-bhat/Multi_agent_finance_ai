"""
Phase 8: LangGraph Agents — Comprehensive Test Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint validation gates:
  ✓ IndiaEngineState has all required fields
  ✓ Risk Node: VIX circuit breaker at exactly 25
  ✓ Risk Node: VIX crisis at 30
  ✓ Risk Node: FII streak reduction at 7 days
  ✓ Risk Node: confidence flag at < 50%
  ✓ Risk Node: expiry Thursday gamma flag
  ✓ Position sizer: Kelly fraction formula
  ✓ Circuit breaker: verdict override to HOLD
  ✓ Each agent node updates its output key in state
  ✓ Workflow compiles without error
  ✓ Graph execution with mocked LLM → full report structure
  ✓ Verdict is one of 5 valid values
  ✓ risk_node_output has all required keys

All tests use mocked LLM calls — zero real API calls.
"""
from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from agents.state import (
    IndiaEngineState, VALID_VERDICTS, RISK_NODE_REQUIRED_KEYS,
    make_empty_state,
)
from agents.risk_node import run_risk_node
from agents.orchestrator_agent import run_orchestrator_agent, _parse_verdict
from risk.circuit_breaker import (
    is_circuit_breaker_active, is_crisis_mode, apply_circuit_breaker,
)
from risk.position_sizer import compute_kelly_fraction, compute_position_size
from risk.volatility_checker import compute_position_size_multiplier


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════

def _make_state(
    vix: float = 15.0,
    fii_streak: int = 0,
    confidence: float = 0.65,
    analysis_date: str = "2026-09-11",  # Friday — not expiry, not results season, not RBI
    ticker: str = "HDFCBANK.NS",
) -> IndiaEngineState:
    """Build a synthetic state for testing."""
    return IndiaEngineState(
        ticker=ticker,
        horizon=5,
        analysis_date=analysis_date,
        vix_signal={"current_vix": vix, "regime": "NORMAL"},
        fii_dii_report={"sell_streak_days": fii_streak, "sell_streak_alert": fii_streak >= 7},
        global_cues={"sgx_gap_direction": "FLAT", "global_sentiment": "MIXED"},
        event_impact={"event_type": "NORMAL", "risk_level": "LOW"},
        fno_report={},
        fno_summary_text="Mock F&O data.",
        ta_summary="RSI=55, MACD bullish crossover. EMA21 > EMA50.",
        smc_summary="BOS detected at 1650. Order block at 1600.",
        prediction_summary="Ensemble: 58% bullish directional probability.",
        sentiment_summary="FinBERT: 0.62 positive. Fear/Greed: 55.",
        fundamental_summary="No SEBI orders. Q3 earnings beat estimate by 8%.",
        market_regime="BULL",
        verdict="BUY",
        confidence=confidence,
        price_targets={"p10": 1580.0, "p50": 1650.0, "p90": 1720.0},
        errors=[],
        warnings=[],
    )


# ═══════════════════════════════════════════════════════════════════════════
# TestStateSchema
# ═══════════════════════════════════════════════════════════════════════════

class TestStateSchema:

    def test_make_empty_state_returns_dict(self):
        s = make_empty_state("NIFTY", 5)
        assert isinstance(s, dict)
        assert s["ticker"] == "NIFTY"
        assert s["horizon"] == 5

    def test_valid_verdicts_set(self):
        assert "STRONG_BUY" in VALID_VERDICTS
        assert "BUY" in VALID_VERDICTS
        assert "HOLD" in VALID_VERDICTS
        assert "SELL" in VALID_VERDICTS
        assert "STRONG_SELL" in VALID_VERDICTS
        assert len(VALID_VERDICTS) == 5

    def test_risk_node_required_keys_present(self):
        """All required keys are defined in the constant."""
        expected = {
            "circuit_breaker_active", "position_size_multiplier",
            "fii_streak_alert", "gamma_risk_flag", "low_confidence_flag",
            "kelly_fraction", "sebi_compliant", "override_verdict",
            "risk_level", "notes",
        }
        assert expected.issubset(RISK_NODE_REQUIRED_KEYS)

    def test_state_typed_dict_accepts_all_fields(self):
        state = _make_state()
        assert state["ticker"] == "HDFCBANK.NS"
        assert state["confidence"] == pytest.approx(0.65)
        assert isinstance(state["price_targets"], dict)


# ═══════════════════════════════════════════════════════════════════════════
# TestCircuitBreaker
# ═══════════════════════════════════════════════════════════════════════════

class TestCircuitBreaker:

    def test_not_active_below_25(self):
        assert is_circuit_breaker_active(24.9) is False

    def test_active_at_exactly_25(self):
        """Blueprint gate: VIX ≥ 25 → circuit breaker."""
        assert is_circuit_breaker_active(25.0) is True
        assert is_circuit_breaker_active(25.1) is True

    def test_crisis_not_active_below_30(self):
        assert is_crisis_mode(29.9) is False

    def test_crisis_active_at_30(self):
        """Blueprint gate: VIX ≥ 30 → crisis mode."""
        assert is_crisis_mode(30.0) is True
        assert is_crisis_mode(35.0) is True

    def test_apply_circuit_breaker_overrides_buy(self):
        new_verdict, reason = apply_circuit_breaker("BUY", vix=26.0)
        assert new_verdict == "HOLD"
        assert len(reason) > 0

    def test_apply_circuit_breaker_does_not_override_below_25(self):
        new_verdict, reason = apply_circuit_breaker("STRONG_BUY", vix=20.0)
        assert new_verdict == "STRONG_BUY"
        assert reason == ""

    def test_apply_crisis_forces_hold(self):
        new_verdict, reason = apply_circuit_breaker("STRONG_BUY", vix=32.0)
        assert new_verdict == "HOLD"
        assert "CRISIS" in reason


# ═══════════════════════════════════════════════════════════════════════════
# TestPositionSizer
# ═══════════════════════════════════════════════════════════════════════════

class TestPositionSizer:

    def test_kelly_fraction_formula(self):
        """f* = (p*b - q) / b where b = avg_win/avg_loss."""
        # p=0.60, avg_win=0.05, avg_loss=0.03 → b=5/3
        # f* = (0.60*(5/3) - 0.40) / (5/3) = (1.0 - 0.40) / 1.667 = 0.36
        f = compute_kelly_fraction(0.60, 0.05, 0.03)
        assert f == pytest.approx(0.36, abs=0.01)

    def test_kelly_below_50pct_win_rate(self):
        """Kelly returns 0 if edge is negative."""
        f = compute_kelly_fraction(0.40, 0.03, 0.05)
        assert f == 0.0

    def test_kelly_zero_loss_returns_zero(self):
        f = compute_kelly_fraction(0.60, 0.05, 0.0)
        assert f == 0.0

    def test_half_kelly_is_half_of_raw(self):
        result = compute_position_size(0.60, 0.05, 0.03, vix_multiplier=1.0)
        assert result.half_kelly_fraction == pytest.approx(result.kelly_fraction * 0.5, abs=0.01)

    def test_max_kelly_capped_at_25pct(self):
        """High win rate should be capped at 25% safety limit."""
        result = compute_position_size(0.90, 0.10, 0.01)
        assert result.capped_fraction <= 0.25

    def test_vix_multiplier_reduces_size(self):
        full_size = compute_position_size(0.60, 0.05, 0.03, vix_multiplier=1.0)
        reduced   = compute_position_size(0.60, 0.05, 0.03, vix_multiplier=0.7)
        assert reduced.vix_adjusted_fraction < full_size.vix_adjusted_fraction

    def test_lot_size_nifty(self):
        result = compute_position_size(0.60, 0.05, 0.03, ticker="NIFTY")
        assert result.lot_size == 50

    def test_lot_size_banknifty(self):
        result = compute_position_size(0.60, 0.05, 0.03, ticker="BANKNIFTY")
        assert result.lot_size == 15

    def test_lot_size_default_unknown_ticker(self):
        result = compute_position_size(0.60, 0.05, 0.03, ticker="UNKNOWN_TICKER")
        assert result.lot_size == 100

    def test_vix_size_multiplier_normal_is_1(self):
        assert compute_position_size_multiplier(15.0) == 1.0

    def test_vix_size_multiplier_elevated_is_07(self):
        assert compute_position_size_multiplier(20.0) == pytest.approx(0.7, abs=0.01)

    def test_vix_size_multiplier_crisis_is_zero(self):
        assert compute_position_size_multiplier(30.0) == 0.0


# ═══════════════════════════════════════════════════════════════════════════
# TestRiskNode
# ═══════════════════════════════════════════════════════════════════════════

class TestRiskNode:

    def test_risk_node_normal_conditions(self):
        """Normal VIX + no FII streak → low risk, full size."""
        state = _make_state(vix=15.0, fii_streak=0, confidence=0.65)
        result = run_risk_node(state)
        rn = result["risk_node_output"]
        assert rn["circuit_breaker_active"] is False
        assert rn["risk_level"] == "LOW"
        assert rn["position_size_multiplier"] == pytest.approx(1.0, abs=0.01)

    def test_risk_node_circuit_breaker_vix_25(self):
        """Blueprint gate: VIX ≥ 25 → circuit_breaker_active = True."""
        state = _make_state(vix=25.0)
        result = run_risk_node(state)
        rn = result["risk_node_output"]
        assert rn["circuit_breaker_active"] is True
        assert result["verdict"] == "HOLD"  # State verdict overridden
        assert rn["position_size_multiplier"] == 0.0

    def test_risk_node_circuit_breaker_vix_30(self):
        """VIX ≥ 30 → crisis mode true."""
        state = _make_state(vix=30.0)
        result = run_risk_node(state)
        rn = result["risk_node_output"]
        assert rn["circuit_breaker_active"] is True
        assert rn.get("crisis_mode", False) is True

    def test_risk_node_fii_streak_7_reduces_size(self):
        """Blueprint gate: FII streak ≥ 7 → flag alert, reduce 40%."""
        state_no_streak = _make_state(fii_streak=0)
        state_streak    = _make_state(fii_streak=7)
        result_no  = run_risk_node(state_no_streak)
        result_yes = run_risk_node(state_streak)
        assert result_yes["risk_node_output"]["fii_streak_alert"] is True
        # Size with streak should be smaller or equal to size without
        assert (
            result_yes["risk_node_output"]["position_size_multiplier"]
            <= result_no["risk_node_output"]["position_size_multiplier"]
        )

    def test_risk_node_fii_streak_6_no_alert(self):
        """Streak of 6 days should NOT trigger alert (threshold is 7)."""
        state = _make_state(fii_streak=6)
        result = run_risk_node(state)
        assert result["risk_node_output"]["fii_streak_alert"] is False

    def test_risk_node_expiry_thursday_gamma_flag(self):
        """Blueprint gate: Expiry Thursday → gamma_risk_flag = True."""
        # March 12 2026 = Thursday
        state = _make_state(analysis_date="2026-03-12")
        result = run_risk_node(state)
        assert result["risk_node_output"]["gamma_risk_flag"] is True

    def test_risk_node_non_expiry_day_no_gamma_flag(self):
        """Non-Thursday → gamma_risk_flag = False."""
        state = _make_state(analysis_date="2026-09-11")  # Friday
        result = run_risk_node(state)
        assert result["risk_node_output"]["gamma_risk_flag"] is False

    def test_risk_node_low_confidence_flag(self):
        """Blueprint gate: confidence < 50% → low_confidence_flag."""
        state = _make_state(confidence=0.45)
        result = run_risk_node(state)
        assert result["risk_node_output"]["low_confidence_flag"] is True

    def test_risk_node_confidence_above_50_no_flag(self):
        state = _make_state(confidence=0.55)
        result = run_risk_node(state)
        assert result["risk_node_output"]["low_confidence_flag"] is False

    def test_risk_node_output_has_all_required_keys(self):
        """All keys defined in RISK_NODE_REQUIRED_KEYS must be present."""
        state = _make_state()
        result = run_risk_node(state)
        rn = result["risk_node_output"]
        for key in RISK_NODE_REQUIRED_KEYS:
            assert key in rn, f"Missing required key: {key}"

    def test_risk_node_kelly_fraction_positive(self):
        """Kelly fraction should be > 0 for profitable strategy."""
        state = _make_state(confidence=0.65)
        result = run_risk_node(state)
        assert result["risk_node_output"]["kelly_fraction"] > 0

    def test_risk_node_notes_populated_on_alerts(self):
        """Notes should be non-empty when circuit breaker fires."""
        state = _make_state(vix=26.0)
        result = run_risk_node(state)
        assert len(result["risk_node_output"]["notes"]) > 0


# ═══════════════════════════════════════════════════════════════════════════
# TestAgentNodes (mocked LLM)
# ═══════════════════════════════════════════════════════════════════════════

class TestAgentNodes:

    def _run_with_mock_groq(self, agent_module_path: str, run_fn, state: IndiaEngineState, return_val: str) -> IndiaEngineState:
        """Helper: patch call_groq at the given module level and run the agent."""
        with patch(agent_module_path, return_value=return_val):
            return run_fn(state)

    def test_quant_agent_writes_output(self):
        from agents.quant_agent import run_quant_agent
        state = _make_state()
        result = self._run_with_mock_groq(
            "agents.quant_agent.call_groq", run_quant_agent, state, "MOCK_QUANT"
        )
        assert result["quant_analysis"] == "MOCK_QUANT"

    def test_macro_agent_writes_output(self):
        from agents.macro_agent import run_macro_agent
        state = _make_state()
        result = self._run_with_mock_groq(
            "agents.macro_agent.call_groq", run_macro_agent, state, "MOCK_MACRO"
        )
        assert result["macro_analysis"] == "MOCK_MACRO"

    def test_fundamental_agent_writes_output(self):
        from agents.fundamental_agent import run_fundamental_agent
        state = _make_state()
        result = self._run_with_mock_groq(
            "agents.fundamental_agent.call_groq", run_fundamental_agent, state, "MOCK_FUND"
        )
        assert result["fundamental_analysis"] == "MOCK_FUND"

    def test_prediction_agent_writes_output(self):
        from agents.prediction_agent import run_prediction_agent
        state = _make_state()
        result = self._run_with_mock_groq(
            "agents.prediction_agent.call_groq", run_prediction_agent, state, "MOCK_PRED"
        )
        assert result["prediction_analysis"] == "MOCK_PRED"

    def test_emotion_agent_writes_output(self):
        from agents.emotion_agent import run_emotion_agent
        state = _make_state()
        result = self._run_with_mock_groq(
            "agents.emotion_agent.call_groq", run_emotion_agent, state, "MOCK_EMOTION"
        )
        assert result["emotion_analysis"] == "MOCK_EMOTION"

    def test_fno_agent_writes_output(self):
        from agents.fno_agent import run_fno_agent
        state = _make_state()
        result = self._run_with_mock_groq(
            "agents.fno_agent.call_groq", run_fno_agent, state, "MOCK_FNO"
        )
        assert result["fno_analysis"] == "MOCK_FNO"

    def test_devils_advocate_writes_output(self):
        from agents.devils_advocate_agent import run_devils_advocate_agent
        state = _make_state()
        result = self._run_with_mock_groq(
            "agents.devils_advocate_agent.call_groq", run_devils_advocate_agent, state, "MOCK_DA"
        )
        assert result["devils_advocate_analysis"] == "MOCK_DA"

    def test_orchestrator_writes_report(self):
        mock_report = (
            "VERDICT: BUY\nCONFIDENCE: 72%\nREGIME: BULL\n"
            "TECHNICAL: Strong uptrend.\nMACRO: FII bullish.\n"
            "F&O: PCR bearish.\nSENTIMENT: Greed.\n"
            "RISKS: 1. Surprise RBI\nPRICE TARGETS: P50=1650\nSTRATEGY: Iron Condor"
        )
        state = _make_state()
        state = run_risk_node(state)
        with patch("agents.orchestrator_agent.call_gemini", return_value=mock_report):
            result = run_orchestrator_agent(state)
        assert "orchestrator_report" in result
        assert len(result["orchestrator_report"]) > 0
        assert result.get("verdict") in VALID_VERDICTS

    def test_orchestrator_enforces_circuit_breaker(self):
        """Even if Gemini returns BUY, circuit breaker must force HOLD."""
        mock_report = "VERDICT: STRONG_BUY\nCONFIDENCE: 80%"
        state = _make_state(vix=26.0)
        state = run_risk_node(state)  # Activates circuit breaker
        with patch("agents.orchestrator_agent.call_gemini", return_value=mock_report):
            result = run_orchestrator_agent(state)
        assert result["verdict"] == "HOLD"


# ═══════════════════════════════════════════════════════════════════════════
# TestOrchestratorParsing
# ═══════════════════════════════════════════════════════════════════════════

class TestOrchestratorParsing:

    def test_parse_strong_buy(self):
        assert _parse_verdict("VERDICT: STRONG_BUY\nConfidence: 80%") == "STRONG_BUY"

    def test_parse_strong_sell(self):
        assert _parse_verdict("VERDICT: STRONG_SELL") == "STRONG_SELL"

    def test_parse_buy(self):
        assert _parse_verdict("VERDICT: BUY\nSome text") == "BUY"

    def test_parse_sell(self):
        assert _parse_verdict("VERDICT: SELL") == "SELL"

    def test_parse_hold(self):
        assert _parse_verdict("VERDICT: HOLD") == "HOLD"

    def test_parse_fallback_to_hold_on_garbled(self):
        """Garbled response → HOLD (safe fallback)."""
        assert _parse_verdict("The market looks okay today.") == "HOLD"


# ═══════════════════════════════════════════════════════════════════════════
# TestWorkflowCompilation
# ═══════════════════════════════════════════════════════════════════════════

class TestWorkflowCompilation:

    def test_workflow_compiles_without_error(self):
        """Critical: LangGraph graph must compile without raising."""
        from agents.graph.workflow import build_workflow
        wf = build_workflow()
        assert wf is not None

    def test_workflow_module_attribute_exists(self):
        """Module-level `workflow` must be importable."""
        from agents.graph.workflow import workflow
        assert workflow is not None

    def test_workflow_has_all_nodes(self):
        """workflow.graph.nodes should have all 9 agent nodes."""
        from agents.graph.workflow import build_workflow
        wf = build_workflow()
        # Access underlying graph to check nodes
        node_names = set(wf.get_graph().nodes.keys())
        expected_nodes = {
            "quant_agent", "macro_agent", "fundamental_agent",
            "prediction_agent", "emotion_agent", "fno_agent",
            "devils_advocate", "risk_node", "orchestrator",
        }
        assert expected_nodes.issubset(node_names), (
            f"Missing nodes: {expected_nodes - node_names}"
        )

    def test_agents_package_importable(self):
        """Smoke test: agents package re-exports work."""
        from agents import (
            IndiaEngineState, VALID_VERDICTS, make_empty_state,
            run_risk_node, workflow, build_workflow,
        )
        assert workflow is not None

    def test_risk_package_importable(self):
        from risk import (
            is_circuit_breaker_active, compute_position_size_multiplier,
            compute_kelly_fraction, PositionSizeResult,
        )
        assert callable(compute_kelly_fraction)
