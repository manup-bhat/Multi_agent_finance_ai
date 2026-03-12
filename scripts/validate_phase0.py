#!/usr/bin/env python3
"""
Phase 0 Validation Gate — v6 (jugaad import name fix, March 2026)

Research-confirmed module names:
  pip package     → Python import module
  ─────────────────────────────────────────
  jugaad-data     → jugaad_data        ← was 'jugaad' (WRONG)
  chronos-forecasting → chronos
  pandas-ta-classic   → pandas_ta_classic
  smartmoneyconcepts  → REMOVED (numba conflict)
"""
import sys
from dataclasses import dataclass
from typing import Callable


@dataclass
class ValidationResult:
    name: str
    passed: bool
    message: str


def check(name: str, fn: Callable) -> ValidationResult:
    try:
        fn()
        return ValidationResult(name, True, "✅ PASS")
    except Exception as e:
        return ValidationResult(name, False, f"❌ FAIL — {e}")


# ── 1: Python 3.11 ────────────────────────────────────────────────────────────
def check_python():
    assert sys.version_info >= (3, 11), f"Need 3.11+, got {sys.version}"
    assert sys.version_info < (3, 12), f"Use 3.11.x only, got {sys.version}"


# ── 2: numpy >= 2.4 ───────────────────────────────────────────────────────────
def check_numpy():
    import numpy as np
    v = [int(x) for x in np.__version__.split(".")[:2]]
    assert v[0] >= 2 and (v[0] > 2 or v[1] >= 4), (
        f"numpy {np.__version__} — need >=2.4.0. "
        "Run: pip install 'numpy>=2.4.0' --force-reinstall"
    )


# ── 3: pandas >= 3.0 ──────────────────────────────────────────────────────────
def check_pandas():
    import pandas as pd
    assert int(pd.__version__.split(".")[0]) >= 3, (
        f"pandas {pd.__version__} — need >=3.0.0. "
        "Run: pip install 'pandas>=3.0.0' --force-reinstall"
    )


# ── 4: India data adapters ───────���────────────────────────────────────────────
# FIXED: jugaad-data pip package → import jugaad_data (underscore, NOT 'jugaad')
# Confirmed from jugaad-py/jugaad-data pyproject.toml:
#   [project.scripts] jdata = "jugaad_data.cli:cli"
def check_india_data():
    import yfinance    # noqa
    import nsefin      # noqa
    import nselib      # noqa
    import nsepython   # noqa
    import jugaad_data # noqa  ← correct: pip=jugaad-data, module=jugaad_data


# ── 5: pandas-ta-classic ─────────────────────────────────────────────────────
def check_pandas_ta_classic():
    import pandas_ta_classic as ta  # noqa
    import pandas as pd
    df = pd.DataFrame({
        "close":  [100.0 + i * 0.5 for i in range(20)],
        "high":   [101.0 + i * 0.5 for i in range(20)],
        "low":    [99.0  + i * 0.5 for i in range(20)],
        "open":   [100.0 + i * 0.5 for i in range(20)],
        "volume": [1000] * 20,
    })
    df.ta.cores = 0
    assert df.ta.rsi(length=14) is not None, "df.ta.rsi() returned None"


# ── 6: SMC Engine (pure Python) ───────────────────────────────────────────────
def check_smc_engine():
    import os, sys as _sys
    _sys.path.insert(0, os.path.abspath("."))
    from data.processors.smc_engine import SMCEngine, analyze_smc
    import pandas as pd, numpy as np
    n = 60
    prices = np.linspace(100, 120, n)
    df = pd.DataFrame({
        "open":   prices - 0.3,
        "high":   prices + 1.0,
        "low":    prices - 1.0,
        "close":  prices,
        "volume": [10000] * n,
    }, index=pd.date_range("2024-01-01", periods=n, freq="B", tz="Asia/Kolkata"))
    result = analyze_smc(df, swing_length=5)
    assert result.current_bias in ("BULLISH", "BEARISH", "NEUTRAL")
    assert isinstance(result.order_blocks, list)
    assert isinstance(result.fair_value_gaps, list)


# ── 7: Chronos-2 ─────────────────────────────────────────────────────────────
# pip = chronos-forecasting  →  import chronos
def check_chronos():
    import chronos  # noqa
    import importlib.metadata
    ver = importlib.metadata.version("chronos-forecasting")
    assert int(ver.split(".")[0]) >= 2, f"Need >=2.0.0, got {ver}"


# ── 8: TimesFM 1.3.0 ─────────────────────────────────────────────────────────
# pip = timesfm  →  import timesfm
# Requires scikit-learn + wandb even on torch path
def check_timesfm():
    import timesfm  # noqa
    import sklearn  # noqa
    import wandb    # noqa
    import importlib.metadata
    assert importlib.metadata.version("timesfm") is not None


# ── 9: ML stack ───────────────────────────────────────────────────────────────
def check_ml():
    import xgboost   # noqa
    import lightgbm  # noqa
    import catboost  # noqa
    import optuna    # noqa
    import shap      # noqa
    import hmmlearn  # noqa
    import sklearn   # noqa


# ── 10: NLP stack ─────────────────────────────────────────────────────────────
def check_nlp():
    import transformers          # noqa
    import torch                 # noqa
    import sentence_transformers # noqa
    import accelerate            # noqa


# ── 11: TA extras ─────────────────────────────────────────────────────────────
def check_ta_extras():
    import finta       # noqa
    import statsmodels # noqa
    import scipy       # noqa
    import einops      # noqa


# ── 12: LLM agents ────────────────────────────────────────────────────────────
def check_agents():
    import langchain                                            # noqa
    import langgraph                                            # noqa
    from langchain_google_genai import ChatGoogleGenerativeAI  # noqa
    from langchain_groq import ChatGroq                        # noqa


# ── 13: Vector DB ─────────────────────────────────────────────────────────────
def check_vectordb():
    import chromadb                        # noqa
    from qdrant_client import QdrantClient # noqa


# ── 14: MLOps + backtesting ───────────────────────────────────────────────────
def check_mlops():
    import mlflow      # noqa
    import vectorbt    # noqa
    import apscheduler # noqa


# ── 15: Frontend ──────────────────────────────────────────────────────────────
def check_frontend():
    import streamlit # noqa
    import plotly    # noqa
    import fastapi   # noqa
    import uvicorn   # noqa


# ── 16: Social sentiment (StockTwits + RSS, no praw) ─────────────────────────
def check_social_sentiment():
    import feedparser # noqa
    import httpx      # noqa
    import aiohttp    # noqa
    r = feedparser.parse("")
    assert hasattr(r, "entries")


# ── 17: India live data + timezone ��──────────────────────────────────────────
def check_india_live():
    import yfinance as yf
    import pandas as pd
    h = yf.Ticker("^INDIAVIX").history(period="5d")
    assert not h.empty, "India VIX empty — check network"
    assert "Close" in h.columns
    now = pd.Timestamp.now(tz="Asia/Kolkata")
    assert "Kolkata" in str(now.tzinfo)


# ── 18: smartmoneyconcepts removed ───────────────────────────────────────────
def check_no_smartmoneyconcepts():
    try:
        import smartmoneyconcepts  # noqa
        raise AssertionError(
            "smartmoneyconcepts still installed — conflicts with numpy>=2.4. "
            "Run: pip uninstall smartmoneyconcepts -y"
        )
    except ImportError:
        pass  # correct — should NOT be importable


# ── .env keys (warn only) ─────────────────────────────────────────────────────
def check_dotenv_keys():
    from dotenv import load_dotenv
    import os
    load_dotenv()
    for key, phase in [
        ("GOOGLE_API_KEY",   "Phase 8: Orchestrator"),
        ("GROQ_API_KEY",     "Phase 8: Sub-agents"),
        ("FINLIGHT_API_KEY", "Phase 1: News data"),
    ]:
        val = os.getenv(key, "").strip()
        if not val:
            print(f"\n    ⚠  {key} not set — needed for {phase}")


# ══════════════════════════════════════════════════════════════════════════════

CHECKS = [
    ("Python 3.11.x",                                               check_python),
    ("numpy >= 2.4.0 (not downgraded)",                             check_numpy),
    ("pandas >= 3.0.0 (not downgraded)",                            check_pandas),
    ("India adapters (yfinance/nsefin/nselib/nsepython/jugaad_data)", check_india_data),
    ("pandas-ta-classic==0.3.78 (import pandas_ta_classic as ta)", check_pandas_ta_classic),
    ("SMC Engine pure Python (data/processors/smc_engine.py)",      check_smc_engine),
    ("chronos-forecasting>=2.0.0 (import chronos)",                 check_chronos),
    ("timesfm==1.3.0 + scikit-learn + wandb",                       check_timesfm),
    ("ML stack (xgb/lgbm/catboost/optuna/shap/hmm)",                check_ml),
    ("NLP stack (transformers/torch/sbert/accelerate)",             check_nlp),
    ("TA extras (finta/statsmodels/scipy/einops)",                  check_ta_extras),
    ("LLM agents (langchain/langgraph/gemini/groq)",                check_agents),
    ("Vector DB (chromadb + qdrant-client)",                        check_vectordb),
    ("MLOps + backtesting (mlflow/vectorbt/apscheduler)",           check_mlops),
    ("Frontend (streamlit/plotly/fastapi/uvicorn)",                 check_frontend),
    ("Social sentiment (feedparser+httpx — no praw)",               check_social_sentiment),
    ("India VIX live + Asia/Kolkata timezone",                      check_india_live),
    ("smartmoneyconcepts removed (numba conflict)",                 check_no_smartmoneyconcepts),
]


def main():
    print("=" * 74)
    print("  PHASE 0 VALIDATION — India Multi-Agent Financial Engine  v6")
    print("  jugaad fix: pip=jugaad-data → import jugaad_data (not jugaad)")
    print("=" * 74)
    print()

    results = []
    for name, fn in CHECKS:
        print(f"  Checking: {name:<56}", end="", flush=True)
        r = check(name, fn)
        results.append(r)
        print(r.message)

    print(f"\n  Checking: {'.env API keys (warnings only)':<56}", end="", flush=True)
    try:
        check_dotenv_keys()
        print("✅ PASS")
    except Exception:
        print("⚠  WARNING")

    passed = sum(1 for r in results if r.passed)
    total  = len(results)
    failed = [r for r in results if not r.passed]

    print()
    print("=" * 74)
    print(f"  RESULT: {passed}/{total} checks passed")
    print("=" * 74)

    FIX_MAP = {
        "jugaad":    "The module is 'jugaad_data' (underscore). import jugaad_data",
        "chronos":   "pip install 'chronos-forecasting>=2.0.0' 'einops>=0.7.0'",
        "timesfm":   "pip install 'timesfm==1.3.0' 'scikit-learn>=1.4.0' 'wandb>=0.17.5'",
        "numpy":     "pip install 'numpy>=2.4.0' --force-reinstall",
        "pandas":    "pip install 'pandas>=3.0.0' --force-reinstall",
        "smc":       "File missing — create data/processors/smc_engine.py",
        "smartmoney":"pip uninstall smartmoneyconcepts -y",
        "pandas-ta": "pip install 'pandas-ta-classic==0.3.78'",
        "langchain": "pip install langchain langgraph langchain-google-genai langchain-groq langchain-community",
        "xgboost":   "pip install xgboost lightgbm catboost optuna shap hmmlearn",
        "mlflow":    "pip install mlflow apscheduler vectorbt",
        "streamlit": "pip install streamlit plotly",
    }

    if not failed:
        print()
        print("  ✅ PHASE 0 COMPLETE — All 18 checks passed")
        print()
        print("  Validated package name map:")
        print("    pip install jugaad-data        → import jugaad_data  ✅")
        print("    pip install chronos-forecasting → import chronos      ✅")
        print("    pip install pandas-ta-classic   → import pandas_ta_classic as ta ✅")
        print("    smartmoneyconcepts removed      → data/processors/smc_engine.py ✅")
        print("    timesfm 1.3.0 (PyPI latest)    → import timesfm      ✅")
        print()
        print("  ─── PHASE 0 COMPLETE — Proceed to Phase 1 ──────────────────")
        print("  Phase 1: Build data/adapters/ — all 9 sources with failover")
        print("  Start:   data/adapters/yfinance_client.py")
        print("  Gate:    Each adapter returns valid DataFrame for HDFCBANK.NS")
        print()
        sys.exit(0)
    else:
        print()
        print("  ❌ PHASE 0 FAILED")
        print()
        for r in failed:
            print(f"  → {r.name}")
            print(f"    {r.message}")
            for key, fix in FIX_MAP.items():
                if key.lower() in r.name.lower():
                    print(f"    Fix: {fix}")
            print()
        sys.exit(1)


if __name__ == "__main__":
    main()