"""Pages 6-13: All updated with render_global_sidebar() and width='stretch' — FII/DII Tracker."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np, datetime, requests
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="FII/DII · India Engine", page_icon="🏦", layout="wide")
flat_css(); st.session_state["_page_id"] = "fiidii"
API_BASE = "http://localhost:8000"

days_val = 30
def _extras():
    global days_val
    days_val = st.slider("History (days)", 10, 90, 30)
    st.button("Refresh", use_container_width=True)

ticker = render_global_sidebar(page_extra_fn=_extras)
render_page_header("🏦","FII/DII Tracker","Daily institutional flows · Z-score · Consensus")
render_help_popover("FII/DII Tracker","""
**FII (Foreign)** — global funds. **DII (Domestic)** — Indian MFs, insurance.

**Z-score |z| > 2** = unusual flow event. **FII buying streak > 7 days** → watch for reversal.

**Consensus rules:**
- FII + DII buying → strong bull signal
- FII selling + DII buying → neutral (DII absorbs supply)
- Both selling → defensive stance
""")

from data.adapters.nselib_client import NSELibClient

@st.cache_data(ttl=3600*2)
def get_real_history(n):
    try:
        client = NSELibClient()
        df = client._fetch_fii_dii_sync()
        if not df.empty:
            df = df.rename(columns={"fii_net_value": "FII", "dii_net_value": "DII"})
            return df.tail(n)[["FII", "DII"]]
    except Exception as e:
        st.warning(f"Failed to fetch live FII/DII data: {e}")
    return pd.DataFrame(columns=["FII", "DII"])

hist = get_real_history(days_val)
if hist.empty:
    st.warning("No live FII/DII history available right now.")
    st.stop()

if len(hist) > 0 and hist["FII"].abs().sum() > 0:
    last_fii = hist["FII"].iloc[-1]
    last_dii = hist["DII"].iloc[-1]
    fii_strk = (hist["FII"][::-1] > 0).cumprod().sum() if last_fii > 0 else (hist["FII"][::-1] < 0).cumprod().sum()
    streak_txt = f"{fii_strk} days {'Buy' if last_fii > 0 else 'Sell'}"
else:
    last_fii, last_dii, streak_txt = 0, 0, "Unknown"

m1,m2,m3,m4 = st.columns(4)
m1.metric("FII Net",   f"₹{last_fii:,.0f} Cr",  "BUYING ✅" if last_fii > 0 else "SELLING ❌")
m2.metric("DII Net",   f"₹{last_dii:,.0f} Cr",  "BUYING ✅" if last_dii > 0 else "SELLING ❌")
m3.metric("FII Streak", streak_txt)
m4.metric("Consensus", "BULLISH" if last_fii > 0 and last_dii > 0 else "BEARISH" if last_fii < 0 and last_dii < 0 else "MIXED")

fig=go.Figure()
fig.add_trace(go.Bar(x=hist.index,y=hist["FII"],name="FII",marker_color=["#00d4aa" if v>0 else "#f43f5e" for v in hist["FII"]]))
fig.add_trace(go.Bar(x=hist.index,y=hist["DII"],name="DII",marker_color=["#3b82f6" if v>0 else "#f59e0b" for v in hist["DII"]]))
fig.add_hline(y=0,line_color="#e8eaf6",line_width=0.5)
fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                   barmode="group",height=340,margin=dict(l=0,r=0,t=30,b=0),
                   title=dict(text=f"{days_val}-Day FII/DII Net Flow (₹ Cr)",font=dict(color="#e8eaf6")),
                   legend=dict(bgcolor="#1c2130"),xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="₹ Cr"))
st.plotly_chart(fig, width="stretch")

col1,col2=st.columns(2)
with col1:
    st.markdown("#### Cumulative Flow")
    cum=hist.cumsum()
    fig2=go.Figure()
    fig2.add_trace(go.Scatter(x=cum.index,y=cum["FII"],name="FII",line=dict(color="#00d4aa",width=2),fill="tozeroy",fillcolor="rgba(0,212,170,0.07)"))
    fig2.add_trace(go.Scatter(x=cum.index,y=cum["DII"],name="DII",line=dict(color="#3b82f6",width=2),fill="tozeroy",fillcolor="rgba(59,130,246,0.07)"))
    fig2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",height=250,margin=dict(l=0,r=0,t=10,b=0),xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554"))
    st.plotly_chart(fig2, width="stretch")
with col2:
    st.markdown("#### FII Z-Score")
    rm=hist["FII"].rolling(30).mean(); rs=hist["FII"].rolling(30).std()
    z=(hist["FII"]-rm)/rs.replace(0,1)
    fig3=go.Figure(go.Scatter(x=z.index,y=z,mode="lines",line=dict(color="#f59e0b",width=2),fill="tozeroy",fillcolor="rgba(0,212,170,0.07)"))
    fig3.add_hline(y=2,line_color="#f43f5e",line_dash="dash",annotation_text="+2σ")
    fig3.add_hline(y=-2,line_color="#00d4aa",line_dash="dash",annotation_text="-2σ")
    fig3.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",height=250,margin=dict(l=0,r=0,t=10,b=0),xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="Z-Score"))
    st.plotly_chart(fig3, width="stretch")
