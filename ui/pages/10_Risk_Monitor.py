"""Page 10: Risk Monitor — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np, datetime
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Risk Monitor · India Engine", page_icon="🛡️", layout="wide")
flat_css(); st.session_state["_page_id"] = "risk"

import requests
API_BASE = "http://localhost:8000"
@st.cache_data(ttl=600)
def fetch_live_vix():
    try:
        r = requests.get(f"{API_BASE}/macro/india-cues", timeout=5)
        if r.status_code == 200:
            payload = r.json()
            vix = payload.get("vix")
            fii_trend = payload.get("fii_trend", "UNKNOWN")
            return (float(vix) if vix is not None else None, fii_trend)
    except Exception:
        pass
    return (None, "UNKNOWN")

live_vix, live_fii_trend = fetch_live_vix()
slider_default_vix = float(live_vix) if live_vix is not None else 15.0
cap_val=1_000_000; win_val=58; wl_val=1.8; vix_val=slider_default_vix
def _extras():
    global cap_val, win_val, wl_val, vix_val
    cap_val = st.number_input("Capital (₹)", value=1_000_000, step=100_000)
    win_val = st.slider("Win Rate (%)", 30, 80, 58)
    wl_val  = st.slider("Win/Loss Ratio", 0.5, 5.0, 1.8)
    vix_val = st.slider("India VIX", 8.0, 40.0, slider_default_vix)

ticker = render_global_sidebar(page_extra_fn=_extras)
render_page_header("🛡️","Risk Monitor",f"{ticker} · VIX Gate · Kelly Criterion · Drawdown")
render_help_popover("Risk Monitor","""
**VIX Gate — auto position sizing:**
- VIX < 13: Complacency → sell premium
- 13-17: Normal → Full Kelly/2
- 18-24: Elevated → -30% applied automatically
- ≥ 25: Circuit Breaker → 0% (CASH ONLY)

**Kelly Criterion:** `f = (p×b − (1−p)) / b`
p = win rate, b = win/loss ratio.
Use **Half Kelly** (recommended): lower volatility, 75% of Kelly growth.

**Max Drawdown > 20%** → review strategy immediately.
""")

vix=vix_val
reg_name,reg_clr,reg_msg = (
    ("EXTREME","#f43f5e","🔴 VIX CIRCUIT BREAKER — Force CASH/HOLD")  if vix>=25 else
    ("ELEVATED","#f59e0b","🟡 Elevated VIX — Reduce position size 30%") if vix>=18 else
    ("NORMAL","#00d4aa","🟢 Normal VIX — Full Kelly/2 valid")           if vix>=13 else
    ("COMPLACENCY","#8892b0","⚪ Complacency — Consider selling premium")
)

if live_vix is None:
    st.warning("Live India VIX unavailable. Slider is showing a manual estimate until the macro API responds.")

c1,c2,c3,c4=st.columns(4)
c1.metric("India VIX",    f"{vix:.1f}", reg_name)
c2.metric("Regime",       reg_name)
c3.metric("FII Trend",    live_fii_trend)
c4.metric("Circuit Breaker","🔴 ACTIVE" if vix>=25 else "🟢 CLEAR")

st.markdown(f"""<div style='background:#161922;border:2px solid {reg_clr};border-radius:12px;padding:1rem 1.5rem;margin:1rem 0;'>
<span style='color:{reg_clr};font-size:1.1rem;font-weight:700;'>{reg_msg}</span></div>""",unsafe_allow_html=True)

col_k,col_d=st.columns(2)
with col_k:
    st.markdown("#### Kelly Criterion Position Sizer")
    p=win_val/100; b=wl_val
    kelly=max(0,(p*b-(1-p))/b); half_k=kelly/2; pos=cap_val*half_k
    if vix>=25:   pos=0; half_k=0; note="⚠️ VIX Circuit Breaker → 0%"
    elif vix>=18: pos*=0.7; half_k*=0.7; note="⚠️ VIX Elevated → -30% applied"
    else:          note="✅ Full Kelly/2 valid"
    for lbl,val in [("Full Kelly %",f"{kelly*100:.1f}%"),("Half Kelly % (Rec.)",f"{half_k*100:.1f}%"),
                     (f"Position Size",f"₹{pos:,.0f}"),("Note",note)]:
        clr2="#00d4aa" if "✅" in str(val) else ("#f43f5e" if "⚠️" in str(val) else "#e8eaf6")
        st.markdown(f"""<div style='display:flex;justify-content:space-between;padding:.5rem .9rem;background:#161922;border-radius:7px;margin:.3rem 0;border:1px solid #2d3554;'>
        <span style='color:#8892b0;'>{lbl}</span><span style='color:{clr2};font-weight:600;'>{val}</span></div>""",unsafe_allow_html=True)
with col_d:
    st.markdown("#### Portfolio Drawdown (90d)")
    
    # Fetch real price data instead of np.random
    from ui_helpers import safe_yf_download
    price_df = safe_yf_download(ticker, period="6mo")
    
    if price_df is not None and not price_df.empty and len(price_df) > 10:
        price_series = price_df["Close"].tail(90)
        idx = price_series.index
        # Calculate simulated equity based on actual price returns (assuming 1.0 delta)
        returns = price_series.pct_change().dropna()
        equity_series = cap_val * (1 + returns).cumprod()
        # Prepend initial capital to match idx length correctly or just use length of returns
        idx = returns.index
        
        dd = (equity_series - equity_series.cummax()) / equity_series.cummax() * 100
        min_dd = float(dd.min()) if not dd.empty else 0.0
    else:
        st.warning("Could not fetch real price data for the drawdown monitor.")
        dd = None
        min_dd = None

    if dd is not None:
        fig=go.Figure(go.Scatter(x=idx,y=dd,fill="tozeroy",fillcolor="rgba(244,63,94,0.07)",
                                  line=dict(color="#f43f5e",width=2)))
        fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                           height=280,margin=dict(l=0,r=0,t=10,b=0),
                           xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="DD %"))
        st.plotly_chart(fig, width="stretch")
        st.metric("Max Drawdown (90d)", f"{min_dd:.1f}%")
