"""Page 4: Emotion Analysis — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st
import plotly.graph_objects as go
import pandas as pd, numpy as np, datetime
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Emotion · India Engine", page_icon="😨", layout="wide")
flat_css()
st.session_state["_page_id"] = "emotion"
ticker = render_global_sidebar()

render_page_header("😨","Emotion & Sentiment",f"{ticker} · FinBERT + India F&G + GoEmotions")
render_help_popover("Emotion Analysis","""
**Fear/Greed Index (0-100):**
- < 25 = Extreme Fear → contrarian BUY
- 25-45 = Fear
- 45-55 = Neutral
- 55-75 = Greed
- > 75 = Extreme Greed → contrarian SELL

**FinBERT scores:** Range -1 (bearish) to +1 (bullish).
Composite > +0.3 reinforces bullish price signals.

**India note:** Retail (9cr NSE accounts) drives sentiment spikes at expiry.
""")

import requests
from ui_helpers import safe_yf_download

def get_live_sentiment(tkr):
    try:
        r = requests.post("http://localhost:8000/sentiment", json={"ticker": tkr}, timeout=15)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return {"composite_score": 0.0, "composite_label": "NEUTRAL", "fear_greed_index": 50.0, "fear_greed_label": "NEUTRAL"}

live_data = get_live_sentiment(ticker)
fg_score  = live_data.get("fear_greed_index", 50.0)
base_name = ticker.replace(".NS","").replace(".BO","")
col_g, col_m = st.columns([1,2])
with col_g:
    st.markdown("#### India Fear/Greed Index")
    gauge = go.Figure(go.Indicator(
        mode="gauge+number+delta", value=fg_score,
        delta={"reference":50,"increasing":{"color":"#00d4aa"},"decreasing":{"color":"#f43f5e"}},
        title={"text":"Fear / Greed","font":{"color":"#8892b0","size":13}},
        number={"font":{"color":"#e8eaf6","size":36}},
        gauge={"axis":{"range":[0,100],"tickcolor":"#8892b0"},"bar":{"color":"#3b82f6"},
               "bgcolor":"#161922",
               "steps":[{"range":[0,25],   "color":"rgba(244,63,94,0.2)"},
                         {"range":[25,45],  "color":"rgba(245,158,11,0.13)"},
                         {"range":[45,55],  "color":"rgba(136,146,176,0.07)"},
                         {"range":[55,75],  "color":"rgba(59,130,246,0.13)"},
                         {"range":[75,100], "color":"rgba(0,212,170,0.2)"}],
               "threshold":{"line":{"color":"#f59e0b","width":3},"thickness":0.75,"value":fg_score}}
    ))
    gauge.update_layout(paper_bgcolor="#161922",font=dict(color="#e8eaf6"),
                         height=260,margin=dict(l=20,r=20,t=30,b=10))
    st.plotly_chart(gauge, width="stretch")
    label = "Extreme Greed" if fg_score>75 else ("Greed" if fg_score>55 else ("Neutral" if fg_score>45 else ("Fear" if fg_score>25 else "Extreme Fear")))
    clr   = "#00d4aa" if fg_score>55 else ("#f59e0b" if fg_score>45 else "#f43f5e")
    st.markdown(f"<div style='text-align:center;'><span style='color:{clr};font-weight:700;font-size:1.1rem;'>{label}</span></div>", unsafe_allow_html=True)

composite = live_data.get("composite_score", 0.0)
lbl       = live_data.get("composite_label", "NEUTRAL")

with col_m:
    st.markdown(f"#### FinBERT Scores — {base_name}")
    df_fb = pd.DataFrame({"Source":["ProsusAI/finbert","FinBERT-India-v1","finbert-tone","GDELT V2Tone"],
                           "Sentiment":["Active","Active","Active","Active"],
                           "Weight":["35%","15%","20%","20%"],"Signal":[f"{lbl}", f"{lbl}", "Neutral", "BULLISH" if composite>0 else "BEARISH"]})
    st.dataframe(df_fb, width="stretch", hide_index=True)
    
    bar=go.Figure(go.Bar(x=[composite],y=[f"{base_name} Composite"],orientation="h",
                          marker_color="#00d4aa" if composite > 0 else "#f43f5e",text=[f"{composite:+.2f}"],textposition="outside"))
    bar.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                       height=80,margin=dict(l=0,r=60,t=0,b=0),
                       xaxis=dict(range=[-1,1],gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554"))
    st.plotly_chart(bar, width="stretch")

st.markdown("#### 30-Day Market Momentum Proxy")
df_hist = safe_yf_download(ticker, period="2mo")
if not df_hist.empty:
    df_hist["R"] = df_hist["Close"].pct_change().rolling(3).mean() * 10
    df_hist = df_hist.dropna().tail(30)
    dates = df_hist.index
    scores = df_hist["R"].values
else:
    dates  = pd.date_range(end=datetime.date.today(), periods=30, freq="D")
    scores = np.zeros(30)

fig2   = go.Figure(go.Scatter(x=dates, y=scores, mode="lines+markers",
                               line=dict(color="#3b82f6",width=2),
                               marker=dict(color=["#00d4aa" if s>0 else "#f43f5e" for s in scores],size=7)))
fig2.add_hline(y=0,line_color="#8892b0",line_dash="dash")
fig2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                    height=220,margin=dict(l=0,r=0,t=10,b=0),
                    xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="Momentum Proxy"))
st.plotly_chart(fig2, width="stretch")
