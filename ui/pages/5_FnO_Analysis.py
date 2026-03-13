"""Page 5: F&O Analysis — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np, requests
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

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
    try:
        r = requests.post(f"{API_BASE}/fno/analyze", json={"symbol":sym}, timeout=10)
        if r.status_code==200: return r.json()
    except: pass
    return {"symbol":sym,"pcr":1.15,"pcr_signal":"SLIGHTLY_BULLISH","max_pain":21500,
            "iv_rank_pct":32.0,"atm_iv":14.5,"fii_futures_net":"LONG",
            "participant_oi":{"FII":{"long":182000,"short":97000,"net":85000},
                              "DII":{"long":42000,"short":38000,"net":4000},
                              "Client":{"long":210000,"short":310000,"net":-100000}},
            "strategy_recommendation":"Bull Call Spread 21500-22000 (low IV — debit spread favoured)",
            "greeks_atm":{"delta":0.50,"gamma":0.002,"theta":-12.5,"vega":35.0}}

prev = st.session_state.get("fno_symbol","")
if prev != symbol or "fno_data" not in st.session_state:
    with st.spinner("Fetching F&O…"):
        st.session_state.update({"fno_data":get_fno(symbol),"fno_symbol":symbol})
data = st.session_state.get("fno_data", get_fno(symbol))

m1,m2,m3,m4,m5 = st.columns(5)
m1.metric("PCR",       f"{data['pcr']:.2f}", data['pcr_signal'])
m2.metric("Max Pain",  f"₹{data['max_pain']:,}")
m3.metric("IV Rank",   f"{data['iv_rank_pct']:.0f}%", "Low ✅" if data['iv_rank_pct']<30 else ("High ⚠️" if data['iv_rank_pct']>70 else "Normal"))
m4.metric("ATM IV",    f"{data['atm_iv']:.1f}%")
m5.metric("FII Fut.",  data['fii_futures_net'])

st.markdown("---")
col_oi, col_g = st.columns([1.4,1])
with col_oi:
    st.markdown("#### Participant OI")
    poi = data.get("participant_oi",{}); parts=list(poi.keys()); nets=[poi[p]["net"] for p in parts]
    fig=go.Figure(go.Bar(x=parts,y=nets,marker_color=["#00d4aa" if n>0 else "#f43f5e" for n in nets],
                          text=[f"{n:+,}" for n in nets],textposition="outside"))
    fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                       height=280,margin=dict(l=0,r=0,t=10,b=0),
                       yaxis=dict(gridcolor="#2d3554",title="Net OI"),xaxis=dict(gridcolor="#2d3554"))
    st.plotly_chart(fig, width="stretch")
with col_g:
    st.markdown("#### ATM Greeks")
    for nm,val,unit in [("Δ Delta",data["greeks_atm"]["delta"],""),("Γ Gamma",data["greeks_atm"]["gamma"],""),
                         ("Θ Theta",data["greeks_atm"]["theta"],"₹/day"),("ν Vega",data["greeks_atm"]["vega"],"₹/1%IV")]:
        c={"Delta":"#00d4aa","Theta":"#f59e0b"}.get(([k for k in ["Delta","Theta"] if k in nm]+["x"])[0],"#3b82f6")
        st.markdown(f"""<div style='background:#161922;border:1px solid #2d3554;border-radius:8px;padding:.6rem 1rem;margin:.3rem 0;display:flex;justify-content:space-between;'>
        <span style='color:#8892b0;'>{nm}</span><span style='color:#3b82f6;font-weight:700;'>{val} {unit}</span></div>""",unsafe_allow_html=True)
    st.markdown(f"""<div style='background:#161922;border:1px solid rgba(0,212,170,.4);border-radius:10px;padding:.85rem 1rem;margin-top:.5rem;'>
    <span style='color:#00d4aa;font-size:.85rem;'>💡 {data.get("strategy_recommendation","—")}</span></div>""",unsafe_allow_html=True)

st.markdown("#### IV Smile Curve")
strikes=np.arange(20500,22500,250); atm=21500
iv=14.5+3*((strikes-atm)/500)**2
fig_iv=go.Figure(go.Scatter(x=strikes,y=iv,mode="lines+markers",line=dict(color="#3b82f6",width=2.5)))
fig_iv.add_vline(x=atm,line_color="#f59e0b",line_dash="dash",annotation_text="ATM")
fig_iv.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                      height=260,margin=dict(l=0,r=0,t=10,b=0),
                      xaxis=dict(gridcolor="#2d3554",title="Strike"),yaxis=dict(gridcolor="#2d3554",title="IV %"))
st.plotly_chart(fig_iv, width="stretch")
