"""Page 12: Model Performance — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np, datetime
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Model Perf · India Engine", page_icon="🎯", layout="wide")
flat_css(); st.session_state["_page_id"] = "model_perf"

days_val=30
def _extras():
    global days_val
    days_val=st.slider("Rolling Window (days)",10,90,30)

ticker=render_global_sidebar(page_extra_fn=_extras)
render_page_header("🎯","Model Performance",f"{ticker} · Rolling Accuracy · Drift · Retrain Log")
render_help_popover("Model Performance","""
**Rolling Accuracy:** Directional accuracy (up/down) over the rolling window.
**Blueprint gate:** 55% accuracy — below triggers auto-retrain.

**Drift detection triggers:**
1. Accuracy < 55% for 5+ consecutive days
2. Regime switch (BULL→BEAR)
3. FII flow reversal > 2σ

**Regime breakdown:** Check if model underperforms in BEAR (common for momentum models).
""")

from feedback.accuracy_tracker import AccuracyTracker
from feedback.prediction_logger import PredictionLogger

@st.cache_data(ttl=3600)
def get_tracker_data(tkr, days):
    try:
        db_logger = PredictionLogger()
        tracker = AccuracyTracker(db_logger)
        tkr_q = tkr if tkr != "ALL" else None
        tracker.resolve_pending(as_of_date=datetime.date.today())
        
        summary = tracker.compute_rolling_accuracy(days=days, ticker=tkr_q)
        rows = db_logger.get_recent(ticker=tkr_q, days=days)
        resolved = [r for r in rows if r.directional_match is not None]
        
        if not resolved:
            return summary, pd.DataFrame()
            
        df = pd.DataFrame([
            {"date": r.analysis_date, "match": r.directional_match, "error": r.pct_error or 0.0, "regime": r.market_regime or "UNKNOWN"}
            for r in resolved
        ])
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
        return summary, df
    except Exception as e:
        return None, pd.DataFrame()

summary, df_hist = get_tracker_data(ticker, days_val)

if df_hist.empty or summary is None:
    st.warning(f"⚠️ No resolved predictions found for {ticker} in the last {days_val} days. Predictions take 5-30 trading days to resolve.")
    st.stop()

# Convert daily binary matches to daily rolling average accuracy
df_daily = df_hist.groupby(df_hist["date"].dt.date)["match"].mean().reset_index()
df_daily.columns = ["date", "accuracy"]
df_daily["rolling_acc"] = df_daily["accuracy"].rolling(min(7, len(df_daily)), min_periods=1).mean()

cur_acc = summary.directional_accuracy
g_clr = "#00d4aa" if cur_acc >= 0.55 else "#f43f5e"

m1,m2,m3,m4=st.columns(4)
m1.metric("Rolling Accuracy",f"{cur_acc*100:.1f}%","✅>55%" if cur_acc>=0.55 else "❌ Below gate")
m2.metric("Avg Price Error", f"{summary.avg_pct_error*100:.2f}%")
m3.metric("Drift Detected",  "No ✅" if not summary.below_threshold else "Yes ⚠️")
m4.metric("Resolutions",     f"{summary.n_resolved} trades")

st.markdown(f"""<div style='background:#161922;border:2px solid {g_clr};border-radius:10px;padding:.75rem 1.5rem;margin:.5rem 0;'>
<span style='color:{g_clr};font-weight:700;'>{"✅ Accuracy above 55% — No retrain needed" if cur_acc>=0.55 else "⚠️ Accuracy drifted below 55% — Retrain recommended"}</span></div>""",unsafe_allow_html=True)

fig=go.Figure()
fig.add_trace(go.Scatter(x=df_daily["date"], y=df_daily["accuracy"]*100, name="Daily", line=dict(color="rgba(136,146,176,0.4)", width=1), mode="lines+markers"))
fig.add_trace(go.Scatter(x=df_daily["date"], y=df_daily["rolling_acc"]*100, name="Smoothed", line=dict(color="#3b82f6", width=2.5)))
fig.add_hline(y=55,line_color="#f43f5e",line_dash="dash",annotation_text="55% gate")
fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                   height=300,margin=dict(l=0,r=0,t=30,b=0),
                   title=dict(text=f"{ticker} · Directional Accuracy(%)",font=dict(color="#e8eaf6")),
                   legend=dict(bgcolor="#1c2130"),xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="%",range=[0,105]))
st.plotly_chart(fig, width="stretch")

col1,col2=st.columns(2)
with col1:
    st.markdown("#### Accuracy by Regime")
    regime_map = summary.regime_breakdown
    if not regime_map:
        st.info("No regime data available")
    for reg, acc_r in regime_map.items():
        bar_clr="#00d4aa" if acc_r>=0.55 else "#f43f5e"
        st.markdown(f"""<div style='background:#161922;border-radius:8px;padding:.6rem 1rem;margin:.3rem 0;border:1px solid #2d3554;display:flex;justify-content:space-between;align-items:center;'>
        <span>{reg}</span>
        <div><div style='background:#2d3554;border-radius:4px;height:10px;width:140px;overflow:hidden;display:inline-block;vertical-align:middle;margin-right:8px;'>
          <div style='background:{bar_clr};height:10px;width:{acc_r*140:.0f}px;'></div></div>
          <span style='color:{bar_clr};font-weight:700;'>{acc_r*100:.1f}%</span></div></div>""",unsafe_allow_html=True)
with col2:
    st.markdown("#### Price Error Distribution")
    errors = df_hist["error"].replace({None: np.nan}).dropna() * 100
    if len(errors) > 0:
        fig2=go.Figure(go.Histogram(x=errors,nbinsx=20,marker_color="#3b82f6",opacity=0.8))
        fig2.add_vline(x=float(errors.mean()),line_color="#f59e0b",line_dash="dash",
                       annotation_text=f"μ={float(errors.mean()):.2f}%")
        fig2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                            height=260,margin=dict(l=0,r=0,t=10,b=0),
                            xaxis=dict(gridcolor="#2d3554",title="% Error"),yaxis=dict(gridcolor="#2d3554",title="Count"))
        st.plotly_chart(fig2, width="stretch")
    else:
        st.info("No error data available")
