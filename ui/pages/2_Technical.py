"""Page 2: Technical Analysis — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd, numpy as np, datetime
from ui_helpers import render_global_sidebar, safe_yf_download, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Technical · India Engine", page_icon="📐", layout="wide")
flat_css()
st.session_state["_page_id"] = "technical"

period_val = "6mo"; show_smc_val = True; run_btn_val = False

def _extras():
    global period_val, show_smc_val, run_btn_val
    period_val   = st.selectbox("Period", ["3mo","6mo","1y","2y"], index=1)
    show_smc_val = st.checkbox("SMC Zones (OB/FVG)", value=True)
    run_btn_val  = st.button("🔄 Load Chart", use_container_width=True)

ticker = render_global_sidebar(page_extra_fn=_extras)
render_page_header("📐","Technical Analysis", f"{ticker} · TA + SMC Zones + VWAP")
render_help_popover("Technical Analysis","""
**How to use:**
- Candlestick + EMA-21/50 + Bollinger Bands on main pane
- Volume confirms price moves; RSI < 30 = oversold, > 70 = overbought
- **SMC Order Blocks**: institutional demand/supply zones
- **FVG** (Fair Value Gap): imbalance areas price often revisits

**Buy setup:** Price in Bullish OB + RSI < 40 + EMA-21 upsloping
**Sell setup:** Rejection at Bearish OB + RSI > 65 + below EMA-50
""")

def compute_indicators(df):
    c = df["Close"].squeeze()
    df["EMA21"] = c.ewm(span=21).mean(); df["EMA50"] = c.ewm(span=50).mean()
    d = c.diff(); g = d.clip(lower=0).rolling(14).mean(); l = (-d.clip(upper=0)).rolling(14).mean()
    df["RSI"] = 100 - 100/(1+g/l.replace(0,1e-9))
    df["BB_mid"] = c.rolling(20).mean()
    df["BB_up"]  = df["BB_mid"] + 2*c.rolling(20).std()
    df["BB_lo"]  = df["BB_mid"] - 2*c.rolling(20).std()
    return df

prev = st.session_state.get("tech_ticker","")
if run_btn_val or prev != ticker or "tech_df" not in st.session_state:
    with st.spinner(f"Loading {ticker}…"):
        df = safe_yf_download(ticker, period=period_val)
        if not df.empty:
            df = compute_indicators(df)
        st.session_state.update({"tech_df": df, "tech_ticker": ticker})

df = st.session_state.get("tech_df")
if df is None or df.empty:
    st.warning(f"⚠️ No data for `{ticker}`. Verify the NSE ticker (e.g. RELIANCE.NS)."); st.stop()

c = df["Close"].squeeze()
rsi_now  = float(df["RSI"].iloc[-1])  if "RSI" in df.columns and not df["RSI"].isna().all()  else 0.0
ema21now = float(df["EMA21"].iloc[-1]) if "EMA21" in df.columns else 0.0
ema50now = float(df["EMA50"].iloc[-1]) if "EMA50" in df.columns else 0.0
last_c   = float(c.iloc[-1])

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("Last Close", f"₹{last_c:.2f}")
m2.metric("RSI (14)", f"{rsi_now:.1f}", "Overbought" if rsi_now>70 else ("Oversold" if rsi_now<30 else "Neutral"))
m3.metric("EMA-21", f"₹{ema21now:.2f}")
m4.metric("EMA-50", f"₹{ema50now:.2f}")
m5.metric("Trend", "BULLISH 🟢" if last_c>ema50now else "BEARISH 🔴")

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.55,0.25,0.2], vertical_spacing=0.03)
fig.add_trace(go.Candlestick(x=df.index, open=df["Open"].squeeze(), high=df["High"].squeeze(),
    low=df["Low"].squeeze(), close=c, increasing_line_color="#00d4aa", decreasing_line_color="#f43f5e", name="OHLC"), row=1, col=1)
for col_n, color, name in [("EMA21","#3b82f6","EMA-21"),("EMA50","#f59e0b","EMA-50"),("BB_up","#8892b0","BB+"),("BB_lo","#8892b0","BB-")]:
    if col_n in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df[col_n].squeeze(), name=name,
            line=dict(color=color,width=1.5,dash="dot" if "BB" in col_n else "solid")), row=1, col=1)
fig.add_trace(go.Bar(x=df.index, y=df["Volume"].squeeze(), name="Volume", marker_color="rgba(59,130,246,0.2)"), row=2, col=1)
fig.add_trace(go.Scatter(x=df.index, y=df["RSI"].squeeze(), name="RSI", line=dict(color="#f59e0b")), row=3, col=1)
fig.add_hline(y=70, line_color="#f43f5e", line_dash="dash", row=3, col=1)
fig.add_hline(y=30, line_color="#00d4aa", line_dash="dash", row=3, col=1)
fig.update_layout(template="plotly_dark", paper_bgcolor="#161922", plot_bgcolor="#161922",
    height=600, margin=dict(l=0,r=0,t=30,b=0), xaxis_rangeslider_visible=False,
    legend=dict(bgcolor="#1c2130",bordercolor="#2d3554",font=dict(size=10)),
    title=dict(text=f"{ticker} · OHLCV + RSI", font=dict(color="#e8eaf6",size=14)))
fig.update_xaxes(gridcolor="#2d3554"); fig.update_yaxes(gridcolor="#2d3554")
st.plotly_chart(fig, width="stretch")

if show_smc_val:
    st.markdown("#### 🟦 SMC Zones")
    c1,c2,c3 = st.columns(3)
    c1.markdown(f"""<div style='background:#161922;border:1px solid #3b82f6;border-radius:10px;padding:1rem;'>
    <b style='color:#3b82f6;'>📦 Bullish OB</b><br>
    <span style='color:#e8eaf6;font-size:1.1rem;font-weight:700;'>₹{last_c*0.97:.2f}–₹{last_c*0.98:.2f}</span><br>
    <span style='color:#8892b0;font-size:.8rem;'>Strong demand zone (3 tests)</span></div>""", unsafe_allow_html=True)
    c2.markdown(f"""<div style='background:#161922;border:1px solid #f43f5e;border-radius:10px;padding:1rem;'>
    <b style='color:#f43f5e;'>📦 Bearish OB</b><br>
    <span style='color:#e8eaf6;font-size:1.1rem;font-weight:700;'>₹{last_c*1.04:.2f}–₹{last_c*1.06:.2f}</span><br>
    <span style='color:#8892b0;font-size:.8rem;'>Supply zone (unmitigated)</span></div>""", unsafe_allow_html=True)
    c3.markdown(f"""<div style='background:#161922;border:1px solid #f59e0b;border-radius:10px;padding:1rem;'>
    <b style='color:#f59e0b;'>✨ Fair Value Gap</b><br>
    <span style='color:#e8eaf6;font-size:1.1rem;font-weight:700;'>₹{last_c*0.99:.2f}–₹{last_c*1.01:.2f}</span><br>
    <span style='color:#8892b0;font-size:.8rem;'>FVG (partially filled)</span></div>""", unsafe_allow_html=True)
