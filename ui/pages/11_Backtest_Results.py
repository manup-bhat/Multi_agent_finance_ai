"""Page 11: Backtest Results — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np, datetime, requests
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Backtest · India Engine", page_icon="📈", layout="wide")
flat_css(); st.session_state["_page_id"] = "backtest"
API_BASE = "http://localhost:8000"

strat_val="mean_reversion"; years_val=5; run_btn_val=False
def _extras():
    global strat_val, years_val, run_btn_val
    strat_val   = st.selectbox("Strategy",["mean_reversion","ema_momentum","vix_gated","fii_flow"])
    years_val   = st.slider("Years", 1, 10, 5)
    run_btn_val = st.button("▶ Run Backtest", use_container_width=True)

ticker = render_global_sidebar(page_extra_fn=_extras)
render_page_header("📈","Backtest Results",f"{ticker} · Walk-Forward · India Costs · vs Nifty 50 TRI")
render_help_popover("Backtest Results","""
**Metric gates:**
| Metric | Gate | Meaning |
|--------|------|---------|
| Sharpe | > 0.8 | Risk-adjusted return |
| CAGR | — | Compound annual growth |
| Max DD | < 25% | Worst peak-to-trough |
| Win Rate | > 50% | % profitable trades |

**Costs:** 0.03% commission + 0.01% slippage + STT (India-calibrated).
**Walk-forward:** Out-of-sample testing — prevents overfitting.

**Strategies:**  
- `mean_reversion` — RSI+BB  
- `ema_momentum` — EMA crossover+VIX gate  
- `vix_gated` — 0 positions when VIX>18  
- `fii_flow` — enter only on FII buying days
""")

def get_backtest(strat, tkr, yrs):
    try:
        r=requests.post(f"{API_BASE}/backtest",json={"strategy":strat,"ticker":tkr,"years":yrs},timeout=60)
        if r.status_code==200: return r.json()
    except Exception as e: 
        st.error(f"Failed to fetch real backtest data: {str(e)}")
        pass
    return {"strategy":strat,"ticker":tkr,"sharpe_ratio":0.0,"cagr_pct":0.0,
            "max_drawdown_pct":0.0,"win_rate_pct":0.0,"n_trades":0,"blueprint_gate_passed":False, "dates": [], "equity_curve": [], "benchmark_curve": []}

prev_t=st.session_state.get("bt_ticker",""); prev_s=st.session_state.get("bt_strategy","")
if run_btn_val or prev_t!=ticker or prev_s!=strat_val or "bt_data" not in st.session_state:
    with st.spinner("Running deep walk-forward vectorbt backtest..."):
        data=get_backtest(strat_val,ticker,years_val)
        st.session_state.update({"bt_data":data,"bt_ticker":ticker,"bt_strategy":strat_val})

data=st.session_state.get("bt_data",get_backtest(strat_val,ticker,years_val))
gate=data.get("blueprint_gate_passed",False); g_clr="#00d4aa" if gate else "#f43f5e"
st.markdown(f"""<div style='background:#161922;border:2px solid {g_clr};border-radius:10px;padding:.85rem 1.5rem;margin-bottom:1rem;'>
<span style='color:{g_clr};font-weight:700;'>{"✅ Blueprint Gate PASSED — Sharpe>0.8" if gate else "❌ Blueprint Gate FAILED — Sharpe too low"}</span></div>""",unsafe_allow_html=True)

m1,m2,m3,m4,m5=st.columns(5)
m1.metric("Sharpe",   f"{data.get('sharpe_ratio', 0):.3f}","✅" if data.get('sharpe_ratio', 0)>=0.8 else "❌")
m2.metric("CAGR",     f"{data.get('cagr_pct', 0):.1f}%")
m3.metric("Max DD",   f"{data.get('max_drawdown_pct', 0):.1f}%")
m4.metric("Win Rate", f"{data.get('win_rate_pct', 0):.1f}%")
m5.metric("Trades",   f"{data.get('n_trades', 0)}")

# Use actual API returned data
dates_str = data.get("dates", [])
strat_curve = data.get("equity_curve", [])
bench_curve = data.get("benchmark_curve", [])

if not dates_str or not strat_curve:
    st.warning("No equity curve data returned for this backtest. (Could be a data fetching issue)")
else:
    idx = pd.to_datetime(dates_str)
    # Normalize curves to start at 100 for easy comparison
    strat_eq = (pd.Series(strat_curve) / strat_curve[0]) * 100
    
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=idx,y=strat_eq,name=f"Strategy ({strat_val})",line=dict(color="#00d4aa",width=2.5)))
    
    if bench_curve and len(bench_curve) == len(strat_curve) and bench_curve[0] != 0:
        nifty_eq = (pd.Series(bench_curve) / bench_curve[0]) * 100
        fig.add_trace(go.Scatter(x=idx,y=nifty_eq,name="Nifty 50 TRI",line=dict(color="#8892b0",width=1.5,dash="dot")))
        
    fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                       height=380,margin=dict(l=0,r=0,t=30,b=0),
                       legend=dict(bgcolor="#1c2130",bordercolor="#2d3554"),
                       title=dict(text=f"{ticker} · {strat_val} vs Nifty 50 TRI — {years_val}Y",font=dict(color="#e8eaf6")),
                       xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="Indexed=100"))
    st.plotly_chart(fig, width="stretch")
    
    dd=(strat_eq-strat_eq.cummax())/strat_eq.cummax()*100
    fig2=go.Figure(go.Scatter(x=idx,y=dd,fill="tozeroy",fillcolor="rgba(244,63,94,0.07)",line=dict(color="#f43f5e",width=1.5)))
    fig2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                        height=180,margin=dict(l=0,r=0,t=10,b=0),
                        xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554",title="DD %"))
    st.plotly_chart(fig2, width="stretch")
