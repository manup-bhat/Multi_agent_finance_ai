#!/bin/bash
cd ~/multi-agent-india-engine
source .venv/bin/activate
python3 - << 'EOF'
"""Use jugaad's exact NSELive session to test FII/DII and option chain."""
import json, sys
from requests import Session

# Source-validated from jugaad_data/nse/live.py
BASE    = "https://www.nseindia.com/api"
WARMUP  = "https://www.nseindia.com/get-quotes/equity?symbol=LT"
HEADERS = {
    "Host":              "www.nseindia.com",
    "Referer":           "https://www.nseindia.com/get-quotes/equity?symbol=SBIN",
    "X-Requested-With":  "XMLHttpRequest",
    "pragma":            "no-cache",
    "sec-fetch-dest":    "empty",
    "sec-fetch-mode":    "cors",
    "sec-fetch-site":    "same-origin",
    "User-Agent":        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/80.0.3987.132 Safari/537.36",
    "Accept":            "*/*",
    "Accept-Encoding":   "gzip, deflate",
    "Accept-Language":   "en-GB,en-US;q=0.9,en;q=0.8",
    "Cache-Control":     "no-cache",
    "Connection":        "keep-alive",
}

def make_session():
    s = Session()
    s.headers.update(HEADERS)
    r = s.get(WARMUP, timeout=10)
    print(f"  Warmup: HTTP {r.status_code}, cookies={list(r.cookies.keys())}")
    return s

print("=" * 60)

# Test 1: FII/DII
print("\n[TEST 1] GET /api/fiidiiTradeReact")
try:
    s    = make_session()
    resp = s.get(f"{BASE}/fiidiiTradeReact", timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('Content-Type','?')}")
    print(f"  Body[:200]: {resp.text[:200]}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"  Type: {type(data).__name__}")
        if isinstance(data, list) and data:
            print(f"  List len: {len(data)}")
            print(f"  First keys: {list(data[0].keys()) if isinstance(data[0],dict) else data[0]}")
        elif isinstance(data, dict):
            print(f"  Dict keys: {list(data.keys())}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

# Test 2: Option chain NIFTY
print("\n[TEST 2] GET /api/option-chain-indices?symbol=NIFTY")
try:
    s    = make_session()
    resp = s.get(f"{BASE}/option-chain-indices", params={"symbol":"NIFTY"}, timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Content-Type: {resp.headers.get('Content-Type','?')}")
    print(f"  Body[:200]: {resp.text[:200]}")
    if resp.status_code == 200:
        try:
            data = resp.json()
            recs = data.get("records",{})
            items = recs.get("data",[])
            print(f"  records.data items: {len(items)}")
            if items:
                print(f"  First item keys: {list(items[0].keys())}")
                if "CE" in items[0]:
                    print(f"  CE keys: {list(items[0]['CE'].keys())[:6]}")
        except Exception as pe:
            print(f"  JSON parse error: {pe}")
except Exception as e:
    print(f"  ERROR: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
EOF