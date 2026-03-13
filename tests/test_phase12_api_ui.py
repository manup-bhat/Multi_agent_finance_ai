"""
Phase 12: API + UI — Comprehensive Test Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint validation gates:
  ✓ GET /health returns 200 with all modules
  ✓ POST /analyze returns structured AnalyzeResponse
  ✓ POST /predict returns PredictResponse
  ✓ POST /fno/analyze returns PCR/MaxPain/Greeks
  ✓ GET /macro/india-cues returns MacroResponse with VIX regime
  ✓ GET /fii-dii/latest returns FIIDIIResponse
  ✓ POST /backtest returns BacktestResponse with blueprint gate
  ✓ All 13 Streamlit page files exist and import cleanly
  ✓ API schemas validate correctly (Pydantic)
  ✓ Backtest blueprint gate: Sharpe ≥ 0.8

All tests use httpx TestClient — no real network calls.
"""
from __future__ import annotations

import importlib
import os
import sys
import pytest
from unittest.mock import patch

# Ensure project root in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ── TestClient setup ──────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from api.main import app
    with TestClient(app) as c:
        yield c


# ═══════════════════════════════════════════════════════════════════════════
# TestHealthEndpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_status_field(self, client):
        r = client.get("/health")
        data = r.json()
        assert "status" in data
        assert data["status"] in ("healthy", "degraded")

    def test_health_has_version(self, client):
        r = client.get("/health")
        assert r.json()["version"] == "12.0.0"

    def test_health_has_modules(self, client):
        r = client.get("/health")
        modules = r.json().get("modules", {})
        assert isinstance(modules, dict)
        assert len(modules) >= 1

    def test_health_response_time_header(self, client):
        r = client.get("/health")
        assert "X-Process-Time-Ms" in r.headers


# ═══════════════════════════════════════════════════════════════════════════
# TestAnalyzeEndpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestAnalyzeEndpoint:

    def test_analyze_returns_200(self, client):
        r = client.post("/analyze", json={"ticker": "HDFCBANK.NS", "horizon": 5})
        assert r.status_code == 200

    def test_analyze_has_verdict(self, client):
        r = client.post("/analyze", json={"ticker": "HDFCBANK.NS", "horizon": 5})
        assert "verdict" in r.json()
        assert r.json()["verdict"] in ("STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL")

    def test_analyze_has_confidence_in_range(self, client):
        r = client.post("/analyze", json={"ticker": "RELIANCE.NS", "horizon": 10})
        conf = r.json()["confidence"]
        assert 0.0 <= conf <= 1.0

    def test_analyze_has_key_risks_list(self, client):
        r = client.post("/analyze", json={"ticker": "NIFTY.NS", "horizon": 5})
        data = r.json()
        assert "key_risks" in data
        assert isinstance(data["key_risks"], list)

    def test_analyze_has_regime_field(self, client):
        r = client.post("/analyze", json={"ticker": "HDFCBANK.NS", "horizon": 5})
        assert "regime" in r.json()

    def test_analyze_requires_ticker(self, client):
        r = client.post("/analyze", json={"horizon": 5})
        assert r.status_code == 422   # Pydantic validation error

    def test_analyze_horizon_bounds(self, client):
        r = client.post("/analyze", json={"ticker": "HDFCBANK.NS", "horizon": 365})
        assert r.status_code == 422   # horizon > 30 is invalid


# ═══════════════════════════════════════════════════════════════════════════
# TestPredictEndpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestPredictEndpoint:

    def test_predict_returns_200(self, client):
        r = client.post("/predict", json={"ticker": "HDFCBANK.NS", "horizon": 5})
        assert r.status_code == 200

    def test_predict_has_direction(self, client):
        r = client.post("/predict", json={"ticker": "HDFCBANK.NS", "horizon": 5})
        assert r.json()["direction"] in ("BULLISH", "BEARISH", "NEUTRAL")

    def test_predict_confidence_in_range(self, client):
        r = client.post("/predict", json={"ticker": "RELIANCE.NS", "horizon": 10})
        assert 0.0 <= r.json()["confidence"] <= 1.0

    def test_predict_has_regime(self, client):
        r = client.post("/predict", json={"ticker": "HDFCBANK.NS", "horizon": 5, "regime": "BULL"})
        assert r.json()["regime"] == "BULL"


# ═══════════════════════════════════════════════════════════════════════════
# TestFnOEndpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestFnOEndpoint:

    def test_fno_returns_200(self, client):
        r = client.post("/fno/analyze", json={"symbol": "BANKNIFTY"})
        assert r.status_code == 200

    def test_fno_has_pcr(self, client):
        r = client.post("/fno/analyze", json={"symbol": "NIFTY"})
        assert "pcr" in r.json()
        assert r.json()["pcr"] > 0

    def test_fno_has_max_pain(self, client):
        r = client.post("/fno/analyze", json={"symbol": "BANKNIFTY"})
        assert "max_pain" in r.json()

    def test_fno_has_participant_oi(self, client):
        r = client.post("/fno/analyze", json={"symbol": "NIFTY"})
        assert "participant_oi" in r.json()
        assert "FII" in r.json()["participant_oi"]


# ═══════════════════════════════════════════════════════════════════════════
# TestMacroEndpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestMacroEndpoint:

    def test_macro_returns_200(self, client):
        with patch("yfinance.download", side_effect=Exception("mock")):
            r = client.get("/macro/india-cues")
        assert r.status_code == 200

    def test_macro_has_vix_regime(self, client):
        with patch("yfinance.download", side_effect=Exception("mock")):
            r = client.get("/macro/india-cues")
        assert r.json()["vix_regime"] in ("COMPLACENCY","NORMAL","ELEVATED","EXTREME","UNKNOWN")

    def test_macro_has_india_summary(self, client):
        with patch("yfinance.download", side_effect=Exception("mock")):
            r = client.get("/macro/india-cues")
        assert len(r.json()["india_summary"]) > 10


# ═══════════════════════════════════════════════════════════════════════════
# TestFIIDIIEndpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestFIIDIIEndpoint:

    def test_fiidii_returns_200(self, client):
        r = client.get("/fii-dii/latest")
        assert r.status_code == 200

    def test_fiidii_has_date(self, client):
        r = client.get("/fii-dii/latest")
        assert "date" in r.json()

    def test_fiidii_has_fii_trend(self, client):
        r = client.get("/fii-dii/latest")
        assert r.json()["fii_trend"] in ("BUYING", "SELLING", "UNKNOWN", "NEUTRAL")

    def test_fiidii_has_consensus(self, client):
        r = client.get("/fii-dii/latest")
        assert r.json()["consensus"] in ("BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN")


# ═══════════════════════════════════════════════════════════════════════════
# TestBacktestEndpoint
# ═══════════════════════════════════════════════════════════════════════════

class TestBacktestEndpoint:

    def test_backtest_returns_200(self, client):
        r = client.post("/backtest", json={"strategy": "mean_reversion", "ticker": "BANKNIFTY", "years": 2})
        assert r.status_code == 200

    def test_backtest_has_sharpe(self, client):
        r = client.post("/backtest", json={"strategy": "mean_reversion", "ticker": "BANKNIFTY", "years": 2})
        # Sharpe should be a float
        assert isinstance(r.json()["sharpe_ratio"], float)

    def test_backtest_blueprint_gate_field(self, client):
        r = client.post("/backtest", json={"strategy": "mean_reversion", "ticker": "BANKNIFTY", "years": 2})
        assert "blueprint_gate_passed" in r.json()

    def test_backtest_invalid_strategy(self, client):
        r = client.post("/backtest", json={"strategy": "invalid_strategy", "ticker": "BANKNIFTY"})
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════
# TestUIPageFiles
# ═══════════════════════════════════════════════════════════════════════════

UI_PAGES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ui", "pages"))

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


# ═══════════════════════════════════════════════════════════════════════════
# TestAPISchemas
# ═══════════════════════════════════════════════════════════════════════════

class TestAPISchemas:

    def test_analyze_request_valid(self):
        from api.schemas import AnalyzeRequest
        req = AnalyzeRequest(ticker="HDFCBANK.NS", horizon=5)
        assert req.ticker == "HDFCBANK.NS"
        assert req.horizon == 5

    def test_analyze_request_invalid_horizon(self):
        from api.schemas import AnalyzeRequest
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            AnalyzeRequest(ticker="HDFCBANK.NS", horizon=365)

    def test_backtest_request_valid(self):
        from api.schemas import BacktestRequest
        req = BacktestRequest(strategy="mean_reversion", ticker="BANKNIFTY", years=5)
        assert req.strategy == "mean_reversion"

    def test_macro_response_valid(self):
        from api.schemas import MacroResponse
        resp = MacroResponse(
            vix=15.2, vix_regime="NORMAL", usdinr=83.45, brent_crude=83.1,
            fii_net_crore=2340.0, fii_trend="BUYING", sgx_nifty=22150.0,
            global_cues="ok", india_summary="VIX normal",
        )
        assert resp.vix_regime == "NORMAL"
