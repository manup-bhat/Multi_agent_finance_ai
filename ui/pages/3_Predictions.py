"""Page 3: Predictions — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st
import plotly.graph_objects as go
import numpy as np, pandas as pd, datetime, requests
from ui_helpers import render_global_sidebar, safe_yf_download, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Predictions · India Engine", page_icon="🔮", layout="wide")
flat_css()
st.session_state["_page_id"] = "predictions"

run_btn_val = False
def _extras():
    global run_btn_val
    run_btn_val = st.button("🔮 Run Prediction", use_container_width=True)

ticker  = render_global_sidebar(page_extra_fn=_extras)
horizon = st.session_state.get("global_horizon", 5)

render_page_header("🔮","ML Predictions",f"{ticker} · Chronos-2 + Ensemble · {horizon}-Day Forecast")
render_help_popover("ML Predictions","""
**Fan Chart:** P10/P50/P90 price bands. P50 = median. Wide bands = high uncertainty → smaller size.

**Direction Probabilities:** 5-class softmax: Very Bearish → Very Bullish

**Blueprint gate:** Directional accuracy > 55% required for live signal.

**How to trade:**
- P10 above current price → strong bull case
- Tight P10–P90 band → high model confidence
- Wide band + Neutral direction → avoid trading
""")

API_BASE = "http://localhost:8000"

def get_predict(tkr, hrz):
    try:
        r = requests.post(f"{API_BASE}/predict", json={"ticker": tkr, "horizon": hrz}, timeout=20)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None

prev = st.session_state.get("pred_ticker","")
if run_btn_val or prev != ticker or "pred_data" not in st.session_state:
    with st.spinner(f"Running prediction for {ticker}…"):
        data = get_predict(ticker, horizon)
        df_p = safe_yf_download(ticker, period="6mo")
        last_price = float(df_p["Close"].iloc[-1]) if not df_p.empty else None
        st.session_state.update({"pred_data": data, "pred_ticker": ticker, "pred_price": last_price, "pred_df": df_p})

data       = st.session_state.get("pred_data", get_predict(ticker, horizon))
last_price = st.session_state.get("pred_price")
df_hist    = st.session_state.get("pred_df")
if df_hist is None or df_hist.empty:
    df_hist = safe_yf_download(ticker, period="3mo")

if not data:
    st.warning("Live prediction API unavailable for this ticker right now.")
    st.stop()
if last_price is None or df_hist.empty:
    st.warning(f"Unable to load recent price history for `{ticker}`.")
    st.stop()

m1,m2,m3,m4 = st.columns(4)
m1.metric("Direction",  data.get("direction","—"))
m2.metric("Confidence", f"{data.get('confidence',0)*100:.1f}%")
m3.metric("Regime",     data.get("regime","—"))
m4.metric("Horizon",    f"{horizon} days")

# Historical Real Data (last 60 days)
idx_hist = df_hist.index[-60:]
hist     = df_hist["Close"].iloc[-60:]
idx_future = pd.bdate_range(start=pd.Timestamp(idx_hist[-1]).normalize(), periods=horizon + 1)
p10 = data.get("p10")
p50 = data.get("p50")
p90 = data.get("p90")

fig = go.Figure()
fig.add_trace(go.Scatter(x=idx_hist, y=hist, name="Historical", line=dict(color="#8892b0",width=1.5)))
if p50 is not None:
    median_path = np.linspace(last_price, p50, len(idx_future))
    fig.add_trace(go.Scatter(x=idx_future, y=median_path, name="P50 (Median)", line=dict(color="#00d4aa", width=2.5)))
if p10 is not None and p90 is not None:
    low_path = np.linspace(last_price, p10, len(idx_future))
    high_path = np.linspace(last_price, p90, len(idx_future))
    fig.add_trace(go.Scatter(x=idx_future, y=high_path, name="P90", line=dict(color="rgba(0,212,170,0.4)", width=1, dash="dot")))
    fig.add_trace(go.Scatter(x=idx_future, y=low_path, name="P10", fill="tonexty",
                              fillcolor="rgba(0,212,170,0.07)", line=dict(color="rgba(0,212,170,0.4)", width=1, dash="dot")))
fig.add_vline(x=idx_hist[-1], line_color="#f59e0b", line_dash="dash", annotation_text="Today")
fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                   height=360,margin=dict(l=0,r=0,t=30,b=0),legend=dict(bgcolor="#1c2130",bordercolor="#2d3554"),
                   title=dict(text=f"{ticker} · {horizon}-Day Fan Chart",font=dict(color="#e8eaf6")),
                   xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="Price ₹"))
st.plotly_chart(fig, width="stretch")

probs  = data.get("class_probs") or {}
if not probs:
    st.info("Class probability breakdown unavailable for this prediction.")
    st.stop()
colors = ["#f43f5e","#f59e0b","#8892b0","#3b82f6","#00d4aa"]
fig2 = go.Figure(go.Bar(x=list(probs.values()), y=list(probs.keys()), orientation="h", marker_color=colors,
                         text=[f"{v*100:.0f}%" for v in probs.values()], textposition="outside"))
fig2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",height=240,
                    margin=dict(l=0,r=60,t=30,b=0),
                    title=dict(text="5-Class Direction Probabilities",font=dict(color="#e8eaf6")),
                    xaxis=dict(gridcolor="#2d3554",range=[0,0.6]),yaxis=dict(gridcolor="#2d3554"))
st.plotly_chart(fig2, width="stretch")
