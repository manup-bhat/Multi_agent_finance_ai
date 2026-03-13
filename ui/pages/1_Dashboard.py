"""
Page 1: Dashboard — Main Ticker Analysis + Full Verdict
Reads ticker from render_global_sidebar() which persists to all pages.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import plotly.graph_objects as go
import pandas as pd, numpy as np, requests, datetime
from ui_helpers import render_global_sidebar, safe_yf_download, flat_css, render_page_header, render_help_popover

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Dashboard · India Engine", page_icon="📊", layout="wide")
flat_css()
st.session_state["_page_id"] = "dashboard"

# ── Sidebar (full global ticker picker + page extras) ──────────────────────
def _sidebar_extras():
    global incl_fno, horizon, analyse_btn
    incl_fno    = st.checkbox("Include F&O analysis", value=True)
    analyse_btn = st.button("🚀 Run Analysis", use_container_width=True)

incl_fno = True; horizon = 5; analyse_btn = False
ticker  = render_global_sidebar(page_extra_fn=_sidebar_extras)
horizon = st.session_state.get("global_horizon", 5)

render_page_header("📊", "Dashboard", f"Full 9-Agent Analysis · {ticker}")
render_help_popover("Dashboard", """
**How to use:**
1. Change ticker in the **sidebar** → **Run Analysis**
2. Verdict card shows BUY/HOLD/SELL + confidence %
3. Price chart: 6M history with EMA-21 and EMA-50
4. Agent summaries: individual signals from Quant, Macro, Emotion, F&O

**Key signals:**
- 🟢 STRONG_BUY — majority agents bullish + VIX < 18
- 🟡 HOLD — conflicting signals or elevated VIX
- 🔴 SELL — bearish agents or VIX circuit breaker active

**Blueprint gate:** Confidence > 60% required for live signal.
""")


def get_analysis(tkr, hrz, fno):
    try:
        r = requests.post(f"{API_BASE}/analyze",
                          json={"ticker": tkr, "horizon": hrz, "include_fno": fno}, timeout=180)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        st.error(f"Error fetching analysis: {e}")
    return {}


def verdict_color(v):
    return {"STRONG_BUY":"#00d4aa","BUY":"#3b82f6","HOLD":"#f59e0b",
            "SELL":"#f43f5e","STRONG_SELL":"#7f1d1d"}.get(v.upper().replace(" ","_"),"#8892b0")


prev_ticker = st.session_state.get("dashboard_ticker", "")
if analyse_btn or prev_ticker != ticker or "dashboard_result" not in st.session_state:
    with st.spinner(f"Analysing {ticker}…"):
        data = get_analysis(ticker, horizon, incl_fno)
        st.session_state.update({"dashboard_result": data, "dashboard_ticker": ticker})

data = st.session_state.get("dashboard_result", {})
if not data:
    st.info("Set ticker in sidebar and click **Run Analysis**."); st.stop()

# Metrics
verdict = data.get("verdict", "HOLD"); vc = verdict_color(verdict)
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.markdown(f"""<div style='background:#161922;border:1px solid {vc};border-radius:12px;padding:1rem;text-align:center;'>
      <div style='font-size:.7rem;color:#8892b0;text-transform:uppercase;'>Verdict</div>
      <div style='font-size:1.8rem;font-weight:800;color:{vc};'>{verdict}</div></div>""", unsafe_allow_html=True)
col2.metric("Confidence", f"{data.get('confidence',0)*100:.1f}%")
col3.metric("Regime",     data.get("regime","—"))
col4.metric("India VIX",  f"{data.get('vix_current','—')}")
col5.metric("Circuit Breaker", "🔴 ACTIVE" if data.get("circuit_breaker_active") else "🟢 Clear")

st.markdown("---")
col_chart, col_agents = st.columns([2, 1])
with col_chart:
    df = safe_yf_download(ticker, period="6mo")
    if df.empty:
        st.warning(f"⚠️ No price data for `{ticker}`. Check the ticker format (e.g. RELIANCE.NS).")
    else:
        prices = df["Close"].squeeze(); ema21 = prices.ewm(span=21).mean(); ema50 = prices.ewm(span=50).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=prices.index, y=prices, name="Price",       line=dict(color="#3b82f6", width=2)))
        fig.add_trace(go.Scatter(x=ema21.index,  y=ema21,  name="EMA-21",      line=dict(color="#00d4aa", width=1.5, dash="dot")))
        fig.add_trace(go.Scatter(x=ema50.index,  y=ema50,  name="EMA-50",      line=dict(color="#f59e0b", width=1.5, dash="dot")))
        fig.update_layout(template="plotly_dark", paper_bgcolor="#161922", plot_bgcolor="#161922",
                          height=340, margin=dict(l=10,r=10,t=40,b=10),
                          legend=dict(bgcolor="#1c2130",bordercolor="#2d3554"),
                          title=dict(text=f"{ticker} · 6M Price", font=dict(color="#e8eaf6",size=14)),
                          xaxis=dict(gridcolor="#2d3554"), yaxis=dict(gridcolor="#2d3554"))
        st.plotly_chart(fig, width="stretch")

with col_agents:
    st.markdown("#### 🤖 Agent Summaries")
    for name, text in [("📐 Quant", data.get("quant_summary","")), ("🌏 Macro", data.get("macro_summary","")),
                        ("😨 Emotion", data.get("emotion_summary","")), ("⚡ F&O", data.get("fno_summary",""))]:
        t = str(text)
        short_t = t[:150] + "…" if len(t) > 150 else t
        st.markdown(f"""<div style='background:#161922;border:1px solid #2d3554;border-radius:10px;padding:.85rem 1rem;margin-top:.35rem; margin-bottom: 5px;'>
          <b style='color:#00d4aa;'>{name}</b><br>
          <span style='color:#8892b0;font-size:.85rem;line-height:1.4;'>{short_t}</span></div>""", unsafe_allow_html=True)
        if len(t) > 0:
            with st.popover(f"🔍 Click to view full detail", use_container_width=True):
                st.markdown(f"<div style='color:#e8eaf6; line-height:1.6;'>{t}</div>", unsafe_allow_html=True)

st.markdown("#### ⚠️ Key Risks")
risks = data.get("key_risks", [])
cols  = st.columns(len(risks) or 1)
for i, risk in enumerate(risks):
    with cols[i]:
        st.markdown(f"""<div style='background:#1c2130;border:1px solid rgba(244,63,94,.3);border-radius:10px;padding:.75rem 1rem;'>
          <span style='color:#f43f5e;font-size:.85rem;'>⚠ {risk}</span></div>""", unsafe_allow_html=True)
