"""Page 7: Macro India — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np, datetime, requests
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Macro · India Engine", page_icon="🌏", layout="wide")
flat_css(); st.session_state["_page_id"] = "macro"
API_BASE = "http://localhost:8000"

def _extras():
    st.button("🔄 Refresh Macro", use_container_width=True)

ticker = render_global_sidebar(page_extra_fn=_extras)
render_page_header("🌏","Macro India","VIX · Brent · USD/INR · SGX Nifty · RBI")
render_help_popover("Macro India","""
**VIX Regime → Position size:**
| VIX | Regime | Action |
|-----|--------|--------|
| < 13 | Complacency | Sell premium |
| 13-17 | Normal | Full signals valid |
| 18-24 | Elevated | -30% size |
| ≥ 25 | Circuit Breaker | CASH only |

**Brent Crude > $90** → inflationary → RBI hawkish → bearish equity.
**USD/INR > 84** → Rupee weak → IT sector benefits, midcaps hurt.
**SGX Nifty** = pre-market Nifty indicator.
""")

def get_macro():
    try:
        r = requests.get(f"{API_BASE}/macro/india-cues", timeout=15)
        if r.status_code==200:
            return r.json()
    except Exception as e:
        st.error(f"Error fetching macro cues: {e}")
    return None

m = get_macro()
if not m:
    st.warning("Live macro cues unavailable right now.")
    st.stop()
vc = {"COMPLACENCY":"#8892b0","NORMAL":"#00d4aa","ELEVATED":"#f59e0b","EXTREME":"#f43f5e"}.get(m.get("vix_regime","NORMAL"),"#e8eaf6")

c1,c2,c3,c4,c5 = st.columns(5)
c1.metric("India VIX",   m.get("vix","—"), m.get("vix_regime","—"))
c2.metric("USD/INR",     m.get("usdinr","—"))
c3.metric("Brent",       f"${m.get('brent_crude','—')}/bbl")
c4.metric("SGX Nifty",   m.get("sgx_nifty","—"))
c5.metric("FII Trend",   m.get("fii_trend","—"))

st.markdown(f"""<div style='background:#161922;border:2px solid {vc};border-radius:12px;padding:1rem 1.5rem;margin:.75rem 0;'>
<div style='font-size:.7rem;color:#8892b0;text-transform:uppercase;'>VIX Regime</div>
<div style='font-size:2.2rem;font-weight:800;color:{vc};'>{m.get("vix_regime","—")}</div>
<div style='color:#8892b0;font-size:.82rem;'>India VIX={m.get("vix","—")} · Elevated≥18 · Circuit Breaker≥25</div>
</div>""", unsafe_allow_html=True)

from ui_helpers import safe_yf_download

df_vix = safe_yf_download("^INDIAVIX", period="6mo")
if not df_vix.empty:
    idx_vix = df_vix.index
    vix_h = df_vix["Close"]
else:
    st.warning("Unable to load historical India VIX series.")
    idx_vix = pd.Index([])
    vix_h = pd.Series(dtype=float)

fig = go.Figure()
if len(idx_vix) > 0:
    fig.add_trace(go.Scatter(x=idx_vix,y=vix_h,name="India VIX",line=dict(color="#f59e0b",width=2),fill="tozeroy",fillcolor="rgba(245,158,11,0.07)"))
    fig.add_hline(y=18,line_color="#f59e0b",line_dash="dash",annotation_text="Elevated(18)")
    fig.add_hline(y=25,line_color="#f43f5e",line_dash="dash",annotation_text="Circuit Breaker(25)")
    fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                       height=280,margin=dict(l=0,r=0,t=30,b=0),
                       title=dict(text="India VIX — 6M History",font=dict(color="#e8eaf6")),
                       xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="VIX"),legend=dict(bgcolor="#1c2130"))
    st.plotly_chart(fig, width="stretch")

col_l,col_r = st.columns(2)
with col_l:
    st.markdown("#### Brent Crude — 3M")
    df_crude = safe_yf_download("BZ=F", period="3mo")
    if not df_crude.empty:
        idx_crude, crude = df_crude.index, df_crude["Close"]
    else:
        st.info("Historical Brent series unavailable.")
        idx_crude = pd.Index([])
        crude = pd.Series(dtype=float)
    if len(idx_crude) > 0:
        f2=go.Figure(go.Scatter(x=idx_crude,y=crude,line=dict(color="#f43f5e",width=2),fill="tozeroy",fillcolor="rgba(244,63,94,0.07)"))
        f2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",height=230,margin=dict(l=0,r=0,t=10,b=0),xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="$/bbl"))
        st.plotly_chart(f2, width="stretch")
with col_r:
    st.markdown("#### USD/INR — 3M")
    df_inr = safe_yf_download("USDINR=X", period="3mo")
    if not df_inr.empty:
        idx_inr, inr = df_inr.index, df_inr["Close"]
    else:
        st.info("Historical USD/INR series unavailable.")
        idx_inr = pd.Index([])
        inr = pd.Series(dtype=float)
    if len(idx_inr) > 0:
        f3=go.Figure(go.Scatter(x=idx_inr,y=inr,line=dict(color="#3b82f6",width=2),fill="tozeroy",fillcolor="rgba(59,130,246,0.07)"))
        f3.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",height=230,margin=dict(l=0,r=0,t=10,b=0),xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="INR/USD"))
        st.plotly_chart(f3, width="stretch")
