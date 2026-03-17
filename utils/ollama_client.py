# utils/ollama_client.py
"""
Local Ollama client for phi4-mini-india.
Handles all preprocessing tasks locally — zero API cost.
Connects from WSL to Windows Ollama via host IP.

Tasks handled locally (saves Groq/Gemini API calls):
  - India news relevance filtering
  - Technical indicator formatting
  - JSON extraction from raw API responses
  - News preprocessing and summarisation
  - Quick sentiment classification
  - Emergency fallback analysis
"""

import json
import os
import subprocess

import requests
import structlog
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_fixed

load_dotenv()
logger = structlog.get_logger()

# ── Config from .env ──────────────────────────────────────────────
OLLAMA_BASE_URL    = os.getenv("OLLAMA_BASE_URL", "http://172.27.144.1:11434")
OLLAMA_MODEL       = os.getenv("OLLAMA_MODEL_PRIMARY", "phi4-mini-india:latest")
OLLAMA_MODEL_THINK = os.getenv("OLLAMA_MODEL_THINKING", "qwen3:4b")
OLLAMA_NUM_CTX     = int(os.getenv("OLLAMA_NUM_CTX", 4096))
OLLAMA_NUM_THREADS = int(os.getenv("OLLAMA_NUM_THREADS", 8))
OLLAMA_TEMPERATURE = float(os.getenv("OLLAMA_TEMPERATURE", 0.0))

# ── Task-specific system prompts ──────────────────────────────────
PROMPTS = {
    "relevance": (
        "Reply ONLY YES or NO. "
        "YES if text mentions: NSE, BSE, Nifty, Sensex, SEBI, RBI, "
        "Indian companies, FII, DII, rupee, Indian economy, "
        "or any stock ticker ending in .NS or .BO. "
        "NO if it does not. One word answer only."
    ),
    "json": (
        "Extract data as a single valid JSON object. "
        "Rules: use lowercase keys, wrap in curly braces, "
        "use double quotes, no extra text, no markdown. "
        "For Indian stock tickers always add .NS suffix for NSE stocks. "
        'Example output: {"ticker":"RELIANCE.NS","price":2850.50}'
    ),
    "ta_format": (
        "Write exactly 2 sentences describing these indicator values. "
        "Sentence 1: describe RSI and momentum. "
        "Sentence 2: describe trend strength. "
        "Do not mention trade recommendations. "
        "Maximum 2 sentences, no more."
    ),
    "news": (
        "Extract key India stock market facts. "
        "Return maximum 5 bullet points starting with -. "
        "One sentence each. Only market-relevant facts."
    ),
    "sentiment": (
        "Reply with exactly one word: POSITIVE, NEGATIVE, or NEUTRAL. "
        "No other text."
    ),
}

# ── Token limits per task (prevents slow responses) ───────────────
MAX_TOKENS = {
    "relevance": 5,
    "json":      80,
    "ta_format": 100,
    "news":      200,
    "sentiment": 5,
    "default":   512,
}


# ── Ticker normalisation ──────────────────────────────────────────
def normalise_ticker(ticker: str) -> str:
    """
    Normalise any ticker format to project standard: SYMBOL.NS

    Examples:
        "RELIANCE"        → "RELIANCE.NS"
        "RELIANCE.BO"     → "RELIANCE.NS"
        "HDFCBANK.NSE"    → "HDFCBANK.NS"
        "HDFCBANK.NS"     → "HDFCBANK.NS"  (already correct)
        "tcs"             → "TCS.NS"
        "NIFTY BANK"      → "NIFTYBANK.NS"
        "TCS IN Equity"   → "TCS.NS"
    """
    if not ticker:
        return ticker

    # Uppercase and strip whitespace
    t = ticker.upper().strip()

    # Remove known wrong suffixes
    for suffix in [".NSE", ".BSE", ".BO", ".IN", " IN EQUITY", " NS", " IN"]:
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()

    # Remove spaces and special characters from base symbol
    t = t.replace(" ", "").replace("-", "").replace("/", "")

    # Add correct suffix if missing
    if not t.endswith(".NS"):
        t = f"{t}.NS"

    return t


# ── Health check ──────────────────────────────────────────────────
def is_ollama_running() -> bool:
    """
    Check if Ollama server is reachable from WSL.
    Auto-detects Windows host IP if connection fails on configured URL.
    """
    # Try configured URL first
    try:
        r = requests.get(
            f"{OLLAMA_BASE_URL}/api/tags",
            timeout=3,
        )
        if r.status_code == 200:
            return True
    except Exception:
        pass

    # Try auto-detected IP as fallback
    detected_ip = _get_windows_host_ip()
    if detected_ip:
        fallback_url = f"http://{detected_ip}:11434"
        try:
            r = requests.get(f"{fallback_url}/api/tags", timeout=3)
            if r.status_code == 200:
                logger.warning(
                    "Ollama found on different IP",
                    configured=OLLAMA_BASE_URL,
                    actual=fallback_url,
                    tip="Update OLLAMA_BASE_URL in .env",
                )
                return True
        except Exception:
            pass

    logger.warning(
        "Ollama not reachable",
        url=OLLAMA_BASE_URL,
        tip="Run D:\\start_ollama.bat on Windows first",
    )
    return False


def _get_windows_host_ip() -> str:
    """Auto-detect Windows host IP from WSL routing table."""
    try:
        result = subprocess.run(
            ["ip", "route"],
            capture_output=True,
            text=True,
        )
        for line in result.stdout.splitlines():
            if "default" in line:
                return line.split()[2]
    except Exception:
        pass
    return ""


def get_active_ollama_url() -> str:
    """Return the working Ollama URL — configured or auto-detected."""
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if r.status_code == 200:
            return OLLAMA_BASE_URL
    except Exception:
        pass
    ip = _get_windows_host_ip()
    return f"http://{ip}:11434" if ip else OLLAMA_BASE_URL


# ── Core chat function ────────────────────────────────────────────
@retry(stop=stop_after_attempt(2), wait=wait_fixed(2))
def _chat(
    system_prompt: str,
    user_message:  str,
    max_tokens:    int  = 512,
    use_thinking:  bool = False,
) -> str:
    """
    Core function — sends chat request to Ollama via /api/chat.

    Uses messages array format which correctly applies the system
    prompt unlike /api/generate which often ignores it for phi4-mini.

    use_thinking=True routes to qwen3:4b with /think flag for
    complex reasoning tasks (slower but more capable).
    """
    if not is_ollama_running():
        return ""

    model        = OLLAMA_MODEL_THINK if use_thinking else OLLAMA_MODEL
    active_url   = get_active_ollama_url()

    # Qwen3 thinking mode — prepend /think flag to enable CoT
    if use_thinking:
        user_message = f"/think\n{user_message}"

    payload = {
        "model":  model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        "options": {
            "num_ctx":        OLLAMA_NUM_CTX,
            "num_thread":     OLLAMA_NUM_THREADS,
            "temperature":    OLLAMA_TEMPERATURE,
            "num_predict":    max_tokens,
            "top_k":          10,
            "top_p":          0.9,
            "repeat_penalty": 1.1,
        },
    }

    try:
        response = requests.post(
            f"{active_url}/api/chat",
            json=payload,
            timeout=60,
        )
        response.raise_for_status()

        data   = response.json()
        result = data["message"]["content"].strip()

        logger.info(
            "Local LLM response",
            model=model,
            chars=len(result),
            tokens_generated=data.get("eval_count", 0),
            duration_ms=round(data.get("total_duration", 0) / 1_000_000),
        )
        return result

    except requests.exceptions.Timeout:
        logger.warning("Ollama timeout — model may be loading, retrying...")
        raise

    except Exception as e:
        logger.error(f"Ollama chat error: {e}")
        return ""


# ── Public task functions ─────────────────────────────────────────

def is_india_relevant(headline: str) -> bool:
    """
    Returns True if headline is relevant to Indian stock markets.
    Used to filter news before sending to Groq agents.
    Saves ~1 Groq API call per irrelevant headline filtered out.

    Examples:
        is_india_relevant("Nifty falls 300 points") → True
        is_india_relevant("Fed raises US rates")     → False
        is_india_relevant("RELIANCE.NS up 2.3%")    → True
    """
    result = _chat(
        system_prompt=PROMPTS["relevance"],
        user_message=headline,
        max_tokens=MAX_TOKENS["relevance"],
    )
    return "yes" in result.lower()


def format_ta_to_text(ta_values: dict) -> str:
    """
    Convert raw pandas-ta indicator numbers to plain English.
    Output is fed to Quant Agent — saves Groq tokens on
    raw number processing.

    Example:
        format_ta_to_text({"RSI": 68.5, "ADX": 32.1})
        → "RSI at 68.5 indicates moderate overbought conditions
           with positive momentum. ADX at 32.1 confirms a strong
           trending market rather than a sideways range."
    """
    return _chat(
        system_prompt=PROMPTS["ta_format"],
        user_message=str(ta_values),
        max_tokens=MAX_TOKENS["ta_format"],
    )


def extract_json(raw_text: str, schema_example: str = "") -> str:
    """
    Extract structured JSON from messy API responses.
    Auto-normalises any ticker found to .NS format.
    Used to clean nsefin/nselib raw outputs before processing.

    Examples:
        extract_json("HDFC Bank closed at 1823.50 NSE up 2.3%")
        → '{"ticker":"HDFCBANK.NS","price":1823.50,"change_pct":2.3}'

        extract_json("Reliance Q3 profit 21930 crore")
        → '{"ticker":"RELIANCE.NS","profit_cr":21930}'
    """
    user_msg = raw_text[:1500]
    if schema_example:
        user_msg = f"Schema example: {schema_example}\nText: {user_msg}"

    result = _chat(
        system_prompt=PROMPTS["json"],
        user_message=user_msg,
        max_tokens=MAX_TOKENS["json"],
    )

    # Post-process: normalise ticker to .NS format if present
    try:
        data = json.loads(result)
        if "ticker" in data:
            data["ticker"] = normalise_ticker(str(data["ticker"]))
        return json.dumps(data)
    except (json.JSONDecodeError, ValueError):
        # Return raw result if JSON parsing fails
        logger.warning("JSON parsing failed", raw=result[:100])
        return result


def preprocess_news(articles: list) -> str:
    """
    Extract key India-relevant facts from raw news articles.
    Reduces token count before sending to Fundamental Agent on Groq.
    Only processes first 5 articles, first 150 chars of each summary.

    Input:  list of dicts with 'title' and 'summary' keys
    Output: "- Reliance Q3 profit up 12%\n- FII bought Rs 3200 crore..."
    """
    if not articles:
        return ""

    combined = "\n".join([
        f"- {a.get('title', '')}: {a.get('summary', '')[:150]}"
        for a in articles[:5]
    ])
    return _chat(
        system_prompt=PROMPTS["news"],
        user_message=combined,
        max_tokens=MAX_TOKENS["news"],
    )


def classify_sentiment(text: str) -> str:
    """
    Quick sentiment classification for financial text.
    Used as pre-filter before FinBERT for speed on obvious cases.
    For nuanced analysis use FinBERT in sentiment/finbert_analyzer.py.

    Returns: "POSITIVE", "NEGATIVE", or "NEUTRAL"

    Examples:
        classify_sentiment("SEBI penalised brokerage Rs 25 crore")
        → "NEGATIVE"

        classify_sentiment("Nifty hits all-time high")
        → "POSITIVE"
    """
    result = _chat(
        system_prompt=PROMPTS["sentiment"],
        user_message=text,
        max_tokens=MAX_TOKENS["sentiment"],
    )
    for word in ["POSITIVE", "NEGATIVE", "NEUTRAL"]:
        if word in result.upper():
            return word
    return "NEUTRAL"


def filter_india_news(articles: list) -> list:
    """
    Filter a list of news articles keeping only India-relevant ones.
    Runs is_india_relevant() on each article title.
    Returns filtered list ready for Groq agents.

    Example:
        raw = [
            {"title": "Nifty falls 300 points as FII selling continues"},
            {"title": "Fed raises US interest rates by 25 bps"},
            {"title": "RELIANCE.NS Q3 profit beats estimates"},
        ]
        filter_india_news(raw)
        → [
            {"title": "Nifty falls 300 points as FII selling continues"},
            {"title": "RELIANCE.NS Q3 profit beats estimates"},
          ]
    """
    if not articles:
        return []

    filtered = []
    for article in articles:
        title = article.get("title", "")
        if title and is_india_relevant(title):
            filtered.append(article)

    logger.info(
        "News filtered",
        total=len(articles),
        kept=len(filtered),
        removed=len(articles) - len(filtered),
    )
    return filtered


def emergency_analysis(ticker: str, ta_summary: str) -> str:
    """
    Last-resort analysis when both Groq keys and Gemini are exhausted.
    Uses qwen3:4b with thinking mode for best possible local quality.

    Not as capable as cloud agents but prevents total system failure.
    Logged as WARNING so you can monitor how often this triggers.

    Example:
        emergency_analysis(
            "RELIANCE.NS",
            "RSI=72, ADX=35, MACD positive, above VWAP"
        )
    """
    ticker = normalise_ticker(ticker)

    prompt = (
        f"Analyse {ticker} for Indian stock market. "
        f"Technical indicators: {ta_summary}. "
        f"Give exactly 3 sentences: "
        f"1) current trend direction, "
        f"2) key level to watch, "
        f"3) overall bias bullish bearish or neutral. "
        f"Be concise and specific. Use INR for prices."
    )

    logger.warning(
        "Emergency local analysis triggered",
        ticker=ticker,
        reason="All cloud APIs exhausted",
    )

    return _chat(
        system_prompt=(
            "You are a concise Indian stock market analyst. "
            "Give only factual analysis based on the data provided."
        ),
        user_message=prompt,
        max_tokens=200,
        use_thinking=True,
    )


# ── Validation tests ──────────────────────────────────────────────
def run_validation_tests() -> bool:
    """
    Run all validation tests.
    Call once after setup to confirm everything works correctly.

    Usage:
        python -c "
        from utils.ollama_client import run_validation_tests
        run_validation_tests()
        "

    Returns True if all tests pass, False otherwise.
    """
    print("\n🧪 Running Ollama Client Validation Tests...\n")

    if not is_ollama_running():
        print("❌ Ollama not running.")
        print("   → Run D:\\start_ollama.bat on Windows first")
        print(f"   → Then retry: configured URL = {OLLAMA_BASE_URL}")
        return False

    print(f"✅ Ollama reachable at {get_active_ollama_url()}\n")

    tests = [
        # (test name, function, expected result)
        (
            "India Relevance — YES (Nifty news)",
            lambda: is_india_relevant(
                "Nifty falls 300 points as FII selling continues"
            ),
            True,
        ),
        (
            "India Relevance — YES (.NS ticker)",
            lambda: is_india_relevant(
                "RELIANCE.NS Q3 profit beats estimates by 8 percent"
            ),
            True,
        ),
        (
            "India Relevance — NO (US news)",
            lambda: is_india_relevant(
                "Fed raises US interest rates by 25 bps"
            ),
            False,
        ),
        (
            "Sentiment — NEGATIVE (SEBI penalty)",
            lambda: classify_sentiment(
                "SEBI imposed Rs 25 crore penalty on brokerage firm"
            ),
            "NEGATIVE",
        ),
        (
            "Sentiment — POSITIVE (profit beat)",
            lambda: classify_sentiment(
                "Reliance Q3 profit up 12 percent beats estimates"
            ),
            "POSITIVE",
        ),
        (
            "JSON extraction — ticker normalised to .NS",
            lambda: json.loads(
                extract_json(
                    "HDFC Bank closed at 1823.50 on NSE up 2.3 percent"
                )
            ).get("ticker", "").endswith(".NS"),
            True,
        ),
        (
            "Ticker normalisation — RELIANCE.BO → RELIANCE.NS",
            lambda: normalise_ticker("RELIANCE.BO"),
            "RELIANCE.NS",
        ),
        (
            "Ticker normalisation — hdfcbank → HDFCBANK.NS",
            lambda: normalise_ticker("hdfcbank"),
            "HDFCBANK.NS",
        ),
        (
            "Ticker normalisation — already correct",
            lambda: normalise_ticker("TCS.NS"),
            "TCS.NS",
        ),
        (
            "TA formatting — returns 2 sentences",
            lambda: len(
                format_ta_to_text(
                    {"RSI": 68.5, "ADX": 32.1, "MACD_hist": 1.23}
                ).split(".")
            ) >= 2,
            True,
        ),
        (
            "News filtering — keeps India, removes US",
            lambda: len(
                filter_india_news([
                    {"title": "Nifty falls 300 points"},
                    {"title": "Fed raises US rates"},
                    {"title": "SEBI issues new F&O guidelines"},
                ])
            ),
            2,
        ),
    ]

    passed = 0
    failed = 0

    for name, fn, expected in tests:
        try:
            result  = fn()
            success = result == expected
            icon    = "✅" if success else "❌"

            if success:
                passed += 1
            else:
                failed += 1

            print(f"{icon} {name}")
            if not success:
                print(f"   Expected : {expected}")
                print(f"   Got      : {result}")
            print()

        except Exception as e:
            failed += 1
            print(f"❌ {name}")
            print(f"   Error: {e}\n")

    # Summary
    total = len(tests)
    print("─" * 50)
    print(f"Results: {passed}/{total} passed  |  {failed}/{total} failed")
    print("─" * 50)

    if passed == total:
        print("✅ All tests passed — ollama_client.py ready for project use")
        return True
    else:
        print("⚠️  Some tests failed — check output above")
        return False


# ── Run directly for quick test ───────────────────────────────────
if __name__ == "__main__":
    run_validation_tests()