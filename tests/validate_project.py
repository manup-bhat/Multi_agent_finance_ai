#!/usr/bin/env python3
"""
India Stock Market Dashboard — Comprehensive Validation Script
================================================================
Tests every API endpoint, ML model, sentiment pipeline, data adapters,
and frontend build artefacts. Run with:

    python tests/validate_project.py
    python tests/validate_project.py --base-url http://localhost:8000
    python tests/validate_project.py --quick          # skip slow model checks
    python tests/validate_project.py --section api    # only run one section

Exit code 0 = all required checks passed, 1 = one or more failures.
"""

from __future__ import annotations
import sys
import os
import json
import time
import argparse
import subprocess
import importlib
import traceback
from typing import Any, Callable
from pathlib import Path

# ─── colour helpers ──────────────────────────────────────────────────────────

RESET   = "\033[0m"
GREEN   = "\033[92m"
RED     = "\033[91m"
YELLOW  = "\033[93m"
CYAN    = "\033[96m"
BOLD    = "\033[1m"
DIM     = "\033[2m"

def ok(msg: str)   -> str: return f"{GREEN}✓{RESET} {msg}"
def fail(msg: str) -> str: return f"{RED}✗{RESET} {msg}"
def warn(msg: str) -> str: return f"{YELLOW}⚠{RESET} {msg}"
def info(msg: str) -> str: return f"{CYAN}ℹ{RESET} {msg}"
def head(msg: str) -> str: return f"\n{BOLD}{CYAN}{'─'*60}\n  {msg}\n{'─'*60}{RESET}"

# ─── result tracker ─────────────────────────────────────────────────────────

class Results:
    def __init__(self):
        self.passed: list[str] = []
        self.failed: list[str] = []
        self.warned: list[str] = []
        self.skipped: list[str] = []

    def add_pass(self, name: str, detail: str = ""):
        msg = f"{name}: {detail}" if detail else name
        self.passed.append(name)
        print(ok(msg))

    def add_fail(self, name: str, detail: str = ""):
        msg = f"{name}: {detail}" if detail else name
        self.failed.append(name)
        print(fail(msg))

    def add_warn(self, name: str, detail: str = ""):
        msg = f"{name}: {detail}" if detail else name
        self.warned.append(name)
        print(warn(msg))

    def add_skip(self, name: str, reason: str = ""):
        msg = f"{name} (skipped: {reason})" if reason else f"{name} (skipped)"
        self.skipped.append(name)
        print(f"{DIM}⊘ {msg}{RESET}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed) + len(self.warned)
        print(head("VALIDATION SUMMARY"))
        print(f"{GREEN}Passed : {len(self.passed)}{RESET}")
        print(f"{YELLOW}Warned : {len(self.warned)}{RESET}")
        print(f"{RED}Failed : {len(self.failed)}{RESET}")
        print(f"{DIM}Skipped: {len(self.skipped)}{RESET}")
        if self.failed:
            print(f"\n{RED}Failed checks:{RESET}")
            for f in self.failed:
                print(f"  {RED}•{RESET} {f}")
        print()
        return 1 if self.failed else 0

r = Results()

# ─── helpers ─────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent

def check_import(module: str, name: str = "") -> Any | None:
    label = name or module
    try:
        mod = importlib.import_module(module)
        r.add_pass(f"import {label}")
        return mod
    except ImportError as e:
        r.add_fail(f"import {label}", str(e))
        return None

def check_file(path: str | Path, label: str = "") -> bool:
    p = Path(path) if not isinstance(path, Path) else path
    label = label or str(p.relative_to(PROJECT_ROOT))
    if p.exists():
        r.add_pass(f"file exists: {label}", f"{p.stat().st_size:,} bytes")
        return True
    else:
        r.add_fail(f"file exists: {label}", "NOT FOUND")
        return False

def get(url: str, timeout: int = 10) -> tuple[int, Any]:
    """HTTP GET — returns (status_code, parsed_json_or_text)"""
    try:
        import urllib.request
        import urllib.error
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except Exception as e:
        return 0, str(e)

def api_check(
    label: str,
    url: str,
    *,
    expected_status: int = 200,
    required_keys: list[str] | None = None,
    warn_only: bool = False,
    timeout: int = 15,
) -> tuple[int, Any]:
    status, body = get(url, timeout=timeout)
    if status == 0:
        (r.add_warn if warn_only else r.add_fail)(label, f"connection error: {body}")
        return status, body
    if status != expected_status:
        (r.add_warn if warn_only else r.add_fail)(label, f"HTTP {status} (expected {expected_status})")
        return status, body
    if required_keys and isinstance(body, dict):
        missing = [k for k in required_keys if k not in body]
        if missing:
            (r.add_warn if warn_only else r.add_fail)(label, f"missing keys: {missing}")
            return status, body
    r.add_pass(label, f"HTTP {status}")
    return status, body

# ─── arg parse ───────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Validate India Stock Market Dashboard")
    p.add_argument("--base-url", default="http://localhost:8000", help="FastAPI backend URL")
    p.add_argument("--quick", action="store_true", help="Skip slow ML model loading checks")
    p.add_argument("--section", choices=["files","imports","api","ml","sentiment","frontend","recharts"], help="Run only one section")
    return p.parse_args()

args = parse_args()
BASE = args.base_url.rstrip("/")
RUN  = lambda sec: args.section is None or args.section == sec

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: Critical project structure files
# ══════════════════════════════════════════════════════════════════════════════

if RUN("files"):
    print(head("1 / 7 · Project Structure"))
    must_exist = [
        "package.json",
        "next.config.js",
        "tsconfig.json",
        "api/main.py",
        "api/routes/sentiment.py",
        "api/routes/predict.py",
        "api/routes/fii_dii.py",
        "api/routes/backtest.py",
        "api/routes/fno.py",
        "api/routes/macro.py",
        "prediction/__init__.py",
        "backtesting/engine.py",
        "data/adapters/india_news_scraper.py",
        "components/charts/CandlestickChart.tsx",
        "components/charts/sentiment-timeline.tsx",
        "components/charts/ShapChart.tsx",
        "components/charts/EquityCurveChart.tsx",
        "components/charts/AccuracyChart.tsx",
        "components/charts/IvSmileChart.tsx",
        "components/charts/PayoffChart.tsx",
        "components/charts/SectorRotationChart.tsx",
        "components/charts/index.ts",
        "lib/chart-theme.ts",
        "lib/format-india.ts",
    ]
    for f in must_exist:
        check_file(PROJECT_ROOT / f)

    # Optional files (warn if missing, not fail)
    optional_files = [
        "ml/features/feature_engine.py",
        "scripts/train_initial_models.py",
    ]
    for f in optional_files:
        p = PROJECT_ROOT / f
        label = f
        if p.exists():
            r.add_pass(f"optional file: {label}", f"{p.stat().st_size:,} bytes")
        else:
            r.add_warn(f"optional file: {label}", "not yet created")

    # Check recharts is ABSENT from package.json
    pkg = (PROJECT_ROOT / "package.json").read_text()
    if '"recharts"' in pkg:
        r.add_fail("recharts removed from package.json", "still present in dependencies")
    else:
        r.add_pass("recharts removed from package.json")

    # Check lightweight-charts and apexcharts present
    for lib in ["lightweight-charts", "apexcharts", "react-apexcharts"]:
        if f'"{lib}"' in pkg:
            r.add_pass(f"package.json dependency: {lib}")
        else:
            r.add_fail(f"package.json dependency: {lib}", "NOT FOUND")

    # next.config.js transpilePackages
    nc = (PROJECT_ROOT / "next.config.js").read_text()
    if "transpilePackages" in nc and "lightweight-charts" in nc:
        r.add_pass("next.config.js: transpilePackages includes lightweight-charts")
    else:
        r.add_fail("next.config.js: transpilePackages lightweight-charts", "missing config")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: No recharts imports remaining in source
# ══════════════════════════════════════════════════════════════════════════════

if RUN("recharts"):
    print(head("2 / 7 · Recharts Removal Check"))

    source_dirs = ["app", "components", "pages"]
    recharts_files: list[str] = []
    for d in source_dirs:
        dir_path = PROJECT_ROOT / d
        if dir_path.exists():
            for f in dir_path.rglob("*.tsx"):
                content = f.read_text()
                if "from 'recharts'" in content or 'from "recharts"' in content:
                    recharts_files.append(str(f.relative_to(PROJECT_ROOT)))

    if recharts_files:
        r.add_fail("recharts imports in source", f"{len(recharts_files)} file(s): {recharts_files}")
    else:
        r.add_pass("recharts imports removed from all source files")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: Python import checks
# ══════════════════════════════════════════════════════════════════════════════

if RUN("imports"):
    print(head("3 / 7 · Python Imports"))

    # Add project root to path so imports resolve
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    python_modules = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("xgboost", "XGBoost"),
        ("lightgbm", "LightGBM"),
        ("catboost", "CatBoost"),
        ("sklearn", "scikit-learn"),
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("yfinance", "yfinance"),
        ("transformers", "HuggingFace Transformers"),
        ("torch", "PyTorch"),
        ("requests", "requests"),
        ("feedparser", "feedparser"),
        ("bs4", "BeautifulSoup4"),
        ("nselib", "nselib"),
    ]
    for module, name in python_modules:
        check_import(module, name)

    # Project-specific imports
    project_modules = [
        ("api.routes.sentiment", "api.routes.sentiment"),
        ("api.routes.predict", "api.routes.predict"),
        ("api.routes.fii_dii", "api.routes.fii_dii"),
        ("api.routes.backtest", "api.routes.backtest"),
        ("backtesting.engine", "backtesting.engine"),
        ("ml.features.feature_engine", "ml.features.feature_engine"),
        ("data.adapters.india_news_scraper", "data.adapters.india_news_scraper"),
    ]
    for module, name in project_modules:
        check_import(module, name)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: API endpoint validation
# ══════════════════════════════════════════════════════════════════════════════

if RUN("api"):
    print(head("4 / 7 · API Endpoints"))
    TICKER = "RELIANCE"
    HORIZON = 10

    endpoints: list[tuple[str, str, int, list[str] | None, bool]] = [
        # label, path, exp_status, required_keys, warn_only
        ("GET /health", "/health", 200, None, False),
        ("GET /", "/", 200, None, True),
        ("GET /ticker/search?q=RELIANCE", f"/ticker/search?q={TICKER}", 200, None, True),
        ("GET /predict/{ticker}", f"/predict/{TICKER}?horizon={HORIZON}", 200,
            ["direction", "confidence", "verdict", "p10", "p50", "p90"], False),
        ("GET /sentiment/{ticker}", f"/sentiment/{TICKER}", 200,
            ["composite_score", "composite_label", "fear_greed_index"], False),
        ("GET /sentiment/debug/{ticker}", f"/sentiment/debug/{TICKER}", 200, None, True),
        ("GET /fii-dii/latest", "/fii-dii/latest", 200,
            ["fii_net_crore", "dii_net_crore", "consensus"], False),
        ("GET /macro/vix", "/macro/vix", 200, ["vix", "regime"], True),
        ("GET /macro/sector-rotation", "/macro/sector-rotation", 200, None, True),
        ("GET /fno/chain/BANKNIFTY", "/fno/chain/BANKNIFTY", 200, ["pcr", "max_pain"], True),
        ("GET /model/performance", "/model/performance", 200, None, True),
        ("GET /news/rss?ticker=RELIANCE", f"/news/rss?ticker={TICKER}", 200, None, True),
    ]

    for label, path, exp, keys, warn_only in endpoints:
        url = f"{BASE}{path}"
        t0 = time.time()
        code, body = api_check(label, url, expected_status=exp, required_keys=keys, warn_only=warn_only)
        elapsed = time.time() - t0
        if code == exp:
            print(f"  {DIM}↳ {elapsed:.2f}s{RESET}")

    # POST /backtest
    print(info("Testing POST /backtest ..."))
    try:
        import urllib.request
        import urllib.error
        payload = json.dumps({"strategy": "mean_reversion", "ticker": "NIFTY", "years": 1}).encode()
        req = urllib.request.Request(
            f"{BASE}/backtest",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
            if all(k in body for k in ["cagr_pct", "sharpe_ratio", "blueprint_gate_passed"]):
                r.add_pass("POST /backtest", f"CAGR={body['cagr_pct']:.1f}%, Sharpe={body['sharpe_ratio']:.2f}")
            else:
                r.add_fail("POST /backtest", f"missing required keys: {body.keys()}")
    except Exception as e:
        r.add_warn("POST /backtest", str(e))

    # POST /analyze
    print(info("Testing POST /analyze ..."))
    try:
        import urllib.request
        payload = json.dumps({"ticker": TICKER, "horizon": HORIZON}).encode()
        req = urllib.request.Request(
            f"{BASE}/analyze",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = json.loads(resp.read().decode())
            if "verdict" in body or "direction" in body:
                r.add_pass("POST /analyze", f"verdict={body.get('verdict', body.get('direction', '?'))}")
            else:
                r.add_warn("POST /analyze", f"unexpected response shape: {list(body.keys())[:5]}")
    except Exception as e:
        r.add_warn("POST /analyze", str(e))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: ML model loading & inference
# ══════════════════════════════════════════════════════════════════════════════

if RUN("ml") and not args.quick:
    print(head("5 / 7 · ML Models"))

    sys.path.insert(0, str(PROJECT_ROOT))

    # Feature engine
    try:
        from ml.features.feature_engine import FeatureEngine
        fe = FeatureEngine()
        r.add_pass("FeatureEngine: instantiation")
    except Exception as e:
        r.add_fail("FeatureEngine: instantiation", str(e))

    # Prediction service
    try:
        from prediction import PredictionService
        svc = PredictionService()
        r.add_pass("PredictionService: instantiation")

        # Try inference on RELIANCE
        try:
            result = svc.predict("RELIANCE", horizon=10)
            if hasattr(result, "direction") or (isinstance(result, dict) and "direction" in result):
                r.add_pass("PredictionService.predict(RELIANCE)", f"direction={getattr(result, 'direction', result.get('direction', '?'))}")
            else:
                r.add_warn("PredictionService.predict(RELIANCE)", "unexpected return shape")
        except Exception as e:
            r.add_warn("PredictionService.predict(RELIANCE)", str(e))

    except ImportError as e:
        r.add_warn("PredictionService: import", str(e))
    except Exception as e:
        r.add_fail("PredictionService: instantiation", str(e))

    # Model files
    model_dirs = [
        PROJECT_ROOT / "models",
        PROJECT_ROOT / "prediction" / "models",
        PROJECT_ROOT / "ml" / "models",
    ]
    found_model = False
    for d in model_dirs:
        if d.exists():
            model_files = list(d.glob("*.pkl")) + list(d.glob("*.joblib")) + list(d.glob("*.json")) + list(d.glob("*.cbm"))
            if model_files:
                r.add_pass(f"Model directory: {d.relative_to(PROJECT_ROOT)}", f"{len(model_files)} file(s)")
                found_model = True
                break
    if not found_model:
        r.add_warn("Model files", "no .pkl/.joblib/.json/.cbm model files found — run train_initial_models.py first")

    # Backtest engine
    try:
        from backtesting.engine import BacktestEngine
        engine = BacktestEngine()
        r.add_pass("BacktestEngine: instantiation")
        try:
            result = engine.run("mean_reversion", "NIFTY", years=1)
            if hasattr(result, "sharpe_ratio") or isinstance(result, dict) and "sharpe_ratio" in result:
                sr = getattr(result, "sharpe_ratio", result.get("sharpe_ratio", "?"))
                r.add_pass("BacktestEngine.run(mean_reversion, NIFTY, 1yr)", f"Sharpe={sr:.2f}" if isinstance(sr, float) else str(sr))
        except Exception as e:
            r.add_warn("BacktestEngine.run", str(e))
    except Exception as e:
        r.add_fail("BacktestEngine: instantiation", str(e))

elif RUN("ml") and args.quick:
    print(head("5 / 7 · ML Models"))
    r.add_skip("ML model loading", "--quick flag set")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: Sentiment pipeline
# ══════════════════════════════════════════════════════════════════════════════

if RUN("sentiment"):
    print(head("6 / 7 · Sentiment Pipeline"))

    sys.path.insert(0, str(PROJECT_ROOT))

    # News scraper
    try:
        from data.adapters.india_news_scraper import IndiaNewsScraper
        scraper = IndiaNewsScraper()
        r.add_pass("IndiaNewsScraper: instantiation")

        # Try fetching for a liquid ticker
        try:
            t0 = time.time()
            articles = scraper.get_news("RELIANCE", max_articles=10)
            elapsed = time.time() - t0
            if articles:
                r.add_pass("IndiaNewsScraper.get_news(RELIANCE)", f"{len(articles)} articles in {elapsed:.1f}s")
            else:
                r.add_warn("IndiaNewsScraper.get_news(RELIANCE)", "returned 0 articles (scraper may be rate-limited)")
        except Exception as e:
            r.add_warn("IndiaNewsScraper.get_news", str(e))
    except Exception as e:
        r.add_fail("IndiaNewsScraper: instantiation", str(e))

    # FinBERT
    try:
        from transformers import pipeline as hf_pipeline
        r.add_pass("HuggingFace transformers: available")
        if not args.quick:
            try:
                pipe = hf_pipeline("text-classification", model="ProsusAI/finbert", max_length=512, truncation=True)
                result = pipe("Reliance Industries reported strong quarterly earnings beat")
                r.add_pass("FinBERT inference", f"label={result[0]['label']}, score={result[0]['score']:.3f}")

                # Neutral test — should NOT be neutral for a clearly positive sentence
                if result[0]["label"].upper() == "NEUTRAL":
                    r.add_warn("FinBERT neutral bias", "clearly bullish sentence classified as NEUTRAL")
            except Exception as e:
                r.add_warn("FinBERT inference", str(e))
        else:
            r.add_skip("FinBERT inference", "--quick flag set")
    except ImportError:
        r.add_warn("HuggingFace transformers", "not installed — sentiment will fall back to rule-based")

    # Google Finance RSS fallback (from sentiment.py)
    try:
        from api.routes.sentiment import _fetch_google_finance_rss
        texts = _fetch_google_finance_rss("RELIANCE.NS", max_items=5)
        if texts:
            r.add_pass("Google Finance RSS fallback", f"{len(texts)} texts fetched")
        else:
            r.add_warn("Google Finance RSS fallback", "returned 0 texts — may be network error")
    except (ImportError, AttributeError):
        r.add_warn("Google Finance RSS fallback", "_fetch_google_finance_rss not importable — check api/routes/sentiment.py")
    except Exception as e:
        r.add_warn("Google Finance RSS fallback", str(e))

    # Sentiment endpoint non-neutral test via API
    status, body = get(f"{BASE}/sentiment/RELIANCE", timeout=30)
    if status == 200 and isinstance(body, dict):
        label = body.get("composite_label", "")
        score = body.get("composite_score", 0)
        r.add_pass("Sentiment API response shape", f"label={label}, score={score:.3f}")
        if label == "NEUTRAL" and abs(score) < 0.01:
            r.add_warn("Sentiment neutral bias", "RELIANCE shows near-zero score — may indicate scraper returned empty (check SCRAPER_RETURNED_EMPTY warning)")
        warnings = body.get("warnings", [])
        if "SCRAPER_RETURNED_EMPTY" in warnings:
            r.add_warn("Sentiment scraper empty", "primary scrapers returned no data — RSS fallback used")
    else:
        r.add_warn("Sentiment API", f"HTTP {status}" if status else "connection error")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: Frontend build check
# ══════════════════════════════════════════════════════════════════════════════

if RUN("frontend"):
    print(head("7 / 7 · Frontend"))

    # TypeScript compile check (fast — just tsc noEmit)
    try:
        result = subprocess.run(
            ["npx", "tsc", "--noEmit", "--project", "tsconfig.json"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            r.add_pass("TypeScript: tsc --noEmit")
        else:
            lines = result.stdout.strip().split("\n") + result.stderr.strip().split("\n")
            errors = [l for l in lines if "error TS" in l][:5]
            r.add_warn("TypeScript: tsc --noEmit", f"{len(errors)} TS errors (sample: {errors[:2]})")
    except subprocess.TimeoutExpired:
        r.add_warn("TypeScript: tsc --noEmit", "timed out after 60s")
    except FileNotFoundError:
        r.add_warn("TypeScript: tsc --noEmit", "npx/tsc not in PATH — skip")

    # Check .next build output if it exists
    next_dir = PROJECT_ROOT / ".next"
    if next_dir.exists():
        chunks = list((next_dir / "static" / "chunks").glob("*.js")) if (next_dir / "static" / "chunks").exists() else []
        r.add_pass(".next build directory exists", f"{len(chunks)} chunk files")
        # Confirm recharts NOT in build
        recharts_in_build = False
        for chunk in chunks[:20]:  # sample first 20 chunks
            try:
                if "recharts" in chunk.read_text(errors="replace"):
                    recharts_in_build = True
                    break
            except Exception:
                pass
        if recharts_in_build:
            r.add_warn(".next build recharts check", "recharts found in build chunks — rebuild with: npm run build")
        else:
            r.add_pass(".next build: recharts not in sampled chunks")
    else:
        r.add_skip(".next build directory", "run `npm run build` to populate")

    # Check node_modules has new chart packages
    nm = PROJECT_ROOT / "node_modules"
    if nm.exists():
        for pkg in ["lightweight-charts", "apexcharts", "react-apexcharts"]:
            if (nm / pkg).exists():
                r.add_pass(f"node_modules/{pkg}")
            else:
                r.add_fail(f"node_modules/{pkg}", "NOT INSTALLED — run: npm install")
        if (nm / "recharts").exists():
            r.add_warn("node_modules/recharts", "still installed — run: npm remove recharts")
        else:
            r.add_pass("node_modules/recharts removed")
    else:
        r.add_warn("node_modules", "directory missing — run: npm install")

# ─── final summary ────────────────────────────────────────────────────────────

sys.exit(r.summary())
