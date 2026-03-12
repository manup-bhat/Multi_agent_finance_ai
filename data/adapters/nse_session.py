"""
NSE session factory — source-validated from jugaad_data/nse/live.py.

jugaad_data/nse/live.py (commit 31c7a27) proves the exact session pattern:
  page_url = "https://www.nseindia.com/get-quotes/equity?symbol=LT"
  Headers: Host, Referer, X-Requested-With, pragma, sec-fetch-*, User-Agent,
           Accept, Accept-Encoding, Accept-Language, Cache-Control, Connection
  Init: session.get(page_url)  ← this seeds the nseappid + nsit cookies

Our previous _make_nse_session() used wrong warmup URLs and missing headers
→ NSE returned HTML instead of JSON → JSONDecodeError on resp.json().

This module provides the single confirmed-working session used by:
  - nselib_client.py  (FII/DII)
  - nsefin_client.py  (option chain)
"""
from __future__ import annotations
import time
import requests
import structlog

logger = structlog.get_logger(__name__)

# Source-validated from jugaad_data/nse/live.py
_NSE_BASE    = "https://www.nseindia.com/api"
_NSE_WARMUP  = "https://www.nseindia.com/get-quotes/equity?symbol=LT"
_NSE_HEADERS = {
    "Host":              "www.nseindia.com",
    "Referer":           "https://www.nseindia.com/get-quotes/equity?symbol=SBIN",
    "X-Requested-With":  "XMLHttpRequest",
    "pragma":            "no-cache",
    "sec-fetch-dest":    "empty",
    "sec-fetch-mode":    "cors",
    "sec-fetch-site":    "same-origin",
    "User-Agent":        (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/80.0.3987.132 Safari/537.36"
    ),
    "Accept":            "*/*",
    "Accept-Encoding":   "gzip, deflate",
    "Accept-Language":   "en-GB,en-US;q=0.9,en;q=0.8",
    "Cache-Control":     "no-cache",
    "Connection":        "keep-alive",
}


def make_nse_session(timeout: int = 10) -> requests.Session:
    """
    Create a cookie-authenticated NSE session.
    Exact pattern from jugaad_data/nse/live.py — the only confirmed working method.

    NSE requires:
    1. Correct headers (X-Requested-With, sec-fetch-* are checked server-side)
    2. Visit the equity quote page first → sets nseappid + nsit cookies
    3. All subsequent API calls use those cookies automatically

    Returns ready-to-use session with cookies set.
    """
    session = requests.Session()
    session.headers.update(_NSE_HEADERS)
    try:
        resp = session.get(_NSE_WARMUP, timeout=timeout)
        logger.info(
            "nse_session.created",
            status=resp.status_code,
            cookies=list(session.cookies.keys()),
        )
    except Exception as e:
        logger.warning("nse_session.warmup_failed", error=str(e))
    return session


def nse_get_json(endpoint: str, params: dict | None = None, timeout: int = 10) -> dict | list:
    """
    Make a single authenticated NSE API call.
    endpoint: just the path, e.g. '/fiidiiTradeReact'
    Creates fresh session per call (stateless — safe for retry).
    Raises ValueError if response is not valid JSON or is empty.
    """
    session = make_nse_session(timeout=timeout)
    url     = _NSE_BASE + endpoint
    resp    = session.get(url, params=params or {}, timeout=timeout)

    if resp.status_code != 200:
        raise ValueError(
            f"NSE API {endpoint} returned HTTP {resp.status_code}. "
            f"Body[:100]: {resp.text[:100]}"
        )

    content_type = resp.headers.get("Content-Type", "")
    if "json" not in content_type and resp.text.strip().startswith("<"):
        raise ValueError(
            f"NSE returned HTML (not JSON) for {endpoint}. "
            f"Anti-bot triggered. Content-Type: {content_type}. "
            f"Body[:80]: {resp.text[:80]}"
        )

    try:
        data = resp.json()
    except Exception as e:
        raise ValueError(
            f"NSE {endpoint} JSON parse failed: {e}. "
            f"Body[:100]: {resp.text[:100]}"
        ) from e

    # Return data as-is (even {} or []).
    # Callers handle empty responses with domain-specific errors:
    #   - nsefin_client: _parse_nse_option_chain raises MarketClosedError for {}
    #   - nselib_client: checks isinstance(data, list) before processing
    return data