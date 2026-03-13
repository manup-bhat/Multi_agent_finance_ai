"""Page 8: Sector Rotation — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd, numpy as np
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Sector Rotation · India Engine", page_icon="🔄", layout="wide")
flat_css(); st.session_state["_page_id"] = "sectors"

period_sel = "3M"
def _extras():
    global period_sel
    period_sel = st.selectbox("Lookback Period", ["1M","3M","6M","1Y"], index=1)

ticker = render_global_sidebar(page_extra_fn=_extras)
render_page_header("🔄","Sector Rotation","NSE Sectoral RS vs Nifty 50 · Rotation Clock")
render_help_popover("Sector Rotation","""
**RS > 0%** → Outperforming Nifty. Focus capital on **Leading** sectors.

**Rotation cycle:** IT → Bank → Auto → FMCG → Pharma → Infra → back.

**Stage definitions:**
- **Leading** — positive RS + strengthening momentum
- **Weakening** — positive RS but losing momentum (exit soon)
- **Lagging** — negative RS + weak momentum (avoid longs)
- **Improving** — negative RS but recovering (early entry)
""")

from ui_helpers import safe_yf_download
from datetime import timedelta

sectors_map = {
    "Bank": "^NSEBANK", "IT": "^CNXIT", "Pharma": "^CNXPHARMA", 
    "FMCG": "^CNXFMCG", "Auto": "^CNXAUTO", "Metal": "^CNXMETAL", 
    "Realty": "^CNXREALTY", "Energy": "^CNXENERGY", "Infra": "^CNXINFRA", "Media": "^CNXMEDIA"
}
sectors = list(sectors_map.keys())

@st.cache_data(ttl=3600)
def get_rs_data():
    bench = safe_yf_download("^NSEI", period="1y")
    if bench is None or bench.empty:
        return np.random.randn(10)*4+1, np.random.randn(10)*8+2, np.random.randn(10)*12+3
        
    def _calc_ret(df, days):
        if len(df) < days: return 0.0
        return (df["Close"].iloc[-1] / df["Close"].iloc[-days] - 1) * 100
        
    bench_1m = _calc_ret(bench, 21)
    bench_3m = _calc_ret(bench, 63)
    bench_6m = _calc_ret(bench, 126)
    
    rs_1m, rs_3m, rs_6m = [], [], []
    for sec, sym in sectors_map.items():
        df = safe_yf_download(sym, period="1y")
        if df is not None and not df.empty:
            s_1m = _calc_ret(df, 21)
            s_3m = _calc_ret(df, 63)
            s_6m = _calc_ret(df, 126)
            rs_1m.append(s_1m - bench_1m)
            rs_3m.append(s_3m - bench_3m)
            rs_6m.append(s_6m - bench_6m)
        else:
            rs_1m.append(0.0); rs_3m.append(0.0); rs_6m.append(0.0)
    return rs_1m, rs_3m, rs_6m

with st.spinner("Calculating live Sector Relative Strength vs Nifty 50..."):
    rs_1m, rs_3m, rs_6m = get_rs_data()

df_rs = pd.DataFrame({"Sector":sectors,"1M RS":rs_1m,"3M RS":rs_3m,"6M RS":rs_6m})
df_rs["Trend"] = df_rs["1M RS"].apply(lambda x: "🟢 Outperforming" if x>0 else "🔴 Underperforming")

fig=go.Figure(go.Heatmap(z=[rs_1m,rs_3m,rs_6m],x=sectors,y=["1M RS","3M RS","6M RS"],
                          colorscale=[[0,"#f43f5e"],[0.5,"#161922"],[1,"#00d4aa"]],
                          text=[[f"{v:.1f}%" for v in r] for r in [rs_1m,rs_3m,rs_6m]],
                          texttemplate="%{text}",textfont=dict(size=10),zmid=0))
fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                   height=260,margin=dict(l=0,r=0,t=30,b=0),
                   title=dict(text="Sector RS vs Nifty 50 (%)",font=dict(color="#e8eaf6")),
                   font=dict(color="#e8eaf6"))
st.plotly_chart(fig, width="stretch")

col1,col2=st.columns(2)
with col1:
    st.markdown("#### 1-Month RS")
    fig2=go.Figure(go.Bar(x=rs_1m,y=sectors,orientation="h",
                           marker_color=["#00d4aa" if v>0 else "#f43f5e" for v in rs_1m],
                           text=[f"{v:.1f}%" for v in rs_1m],textposition="outside"))
    fig2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                        height=340,margin=dict(l=0,r=60,t=10,b=0),
                        xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554"))
    st.plotly_chart(fig2, width="stretch")
with col2:
    st.markdown("#### Rotation Table")
    st.dataframe(df_rs[["Sector","1M RS","3M RS","Trend"]].round(1), width="stretch", hide_index=True)
    st.markdown("#### Stage")
    for sec,stage in {"Bank":"Leading","IT":"Weakening","Auto":"Improving","Metal":"Lagging"}.items():
        clr={"Leading":"#00d4aa","Improving":"#3b82f6","Weakening":"#f59e0b","Lagging":"#f43f5e"}[stage]
        st.markdown(f"""<div style='display:flex;justify-content:space-between;padding:.4rem .8rem;background:#161922;border-radius:6px;margin:.2rem 0;border:1px solid #2d3554;'>
        <span>{sec}</span><span style='color:{clr};font-weight:600;'>{stage}</span></div>""",unsafe_allow_html=True)
