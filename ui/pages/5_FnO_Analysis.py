"""Page 5: F&O Analysis — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np
from ui_helpers import (
    render_global_sidebar,
    flat_css,
    render_page_header,
    render_help_popover,
    cached_api_post_json,
)

st.set_page_config(page_title="F&O · India Engine", page_icon="⚡", layout="wide")
flat_css(); st.session_state["_page_id"] = "fno"
API_BASE = "http://localhost:8000"

symbol_opt = "BANKNIFTY"
def _extras():
    global symbol_opt
    symbol_opt = st.selectbox("F&O Symbol Override",
        ["BANKNIFTY","NIFTY","FINNIFTY","—Use Global Stock—"], index=3)

ticker = render_global_sidebar(page_extra_fn=_extras)
base   = ticker.replace(".NS","").replace(".BO","")
symbol = base if symbol_opt == "—Use Global Stock—" else symbol_opt

render_page_header("⚡","F&O Analysis",f"{symbol} · PCR · Max Pain · IV Smile · Greeks")
render_help_popover("F&O Analysis","""
**PCR > 1** → Put buyers dominant → slightly bullish. **Max Pain** = strike where sellers want expiry.
**IV Rank < 30%** → Cheap premium → buy debit spreads. **> 70%** → Sell premium (strangles).

**FII Net LONG futures** → strong bullish index signal.
**Warning:** NSE F&O data only on trading days.
""")

def get_fno(sym):
    return cached_api_post_json(
        f"{API_BASE}/fno/analyze",
        {"symbol": sym},
        timeout=10,
    )

prev = st.session_state.get("fno_symbol","")
if prev != symbol or "fno_data" not in st.session_state:
    with st.spinner("Fetching F&O…"):
        st.session_state.update({"fno_data":get_fno(symbol),"fno_symbol":symbol})
data = st.session_state.get("fno_data", get_fno(symbol))

if not data:
    st.warning("Live F&O data unavailable right now.")
    st.stop()

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("PCR",       f"{data['pcr']:.2f}" if data.get("pcr") is not None else "—", data.get('pcr_signal', '—'))
m2.metric("Max Pain",  f"₹{data['max_pain']:,}" if data.get("max_pain") is not None else "—")
m3.metric("IV Rank",   f"{data['iv_rank_pct']:.0f}%" if data.get("iv_rank_pct") is not None else "—")
m4.metric("ATM IV",    f"{data['atm_iv']:.1f}%" if data.get("atm_iv") is not None else "—")
m5.metric("Source",    data.get("source", "—"))

st.markdown("---")
col_oi, col_g = st.columns([1.4,1])
with col_oi:
    st.markdown("#### Participant OI")
    poi = data.get("participant_oi",{})
    parts = list(poi.keys())
    nets = [poi[p].get("net") for p in parts]
    valid_nets = [n for n in nets if n is not None]
    if valid_nets:
        fig=go.Figure(go.Bar(x=parts,y=[n or 0 for n in nets],marker_color=["#00d4aa" if (n or 0)>0 else "#f43f5e" for n in nets],
                              text=[f"{(n or 0):+,}" for n in nets],textposition="outside"))
        fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                           height=280,margin=dict(l=0,r=0,t=10,b=0),
                           yaxis=dict(gridcolor="#2d3554",title="Net OI"),xaxis=dict(gridcolor="#2d3554"))
        st.plotly_chart(fig, width="stretch")
    else:
        st.info("Participant OI breakdown unavailable for this session.")
with col_g:
    st.markdown("#### Live Summary")
    greeks = data.get("greeks_atm") or {}
    if greeks:
        for nm,val,unit in [("Δ Delta",greeks.get("delta"),""),("Γ Gamma",greeks.get("gamma"),""),
                             ("Θ Theta",greeks.get("theta"),"₹/day"),("ν Vega",greeks.get("vega"),"₹/1%IV")]:
            st.markdown(f"""<div style='background:#161922;border:1px solid #2d3554;border-radius:8px;padding:.6rem 1rem;margin:.3rem 0;display:flex;justify-content:space-between;'>
            <span style='color:#8892b0;'>{nm}</span><span style='color:#3b82f6;font-weight:700;'>{val if val is not None else "—"} {unit}</span></div>""",unsafe_allow_html=True)
    else:
        st.info("ATM Greeks unavailable from the live option chain snapshot.")
    st.markdown(f"""<div style='background:#161922;border:1px solid rgba(0,212,170,.4);border-radius:10px;padding:.85rem 1rem;margin-top:.5rem;'>
    <span style='color:#00d4aa;font-size:.85rem;'>💡 {data.get("strategy_recommendation","—")}</span></div>""",unsafe_allow_html=True)

st.markdown("#### Live Interpretation")
st.info(
    "This page now shows only live option-chain-derived metrics. "
    "If the NSE option chain is unavailable outside market hours, the page will surface that instead of synthetic curves."
)
