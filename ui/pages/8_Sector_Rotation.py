"""Page 8: Sector Rotation — live sector relative strength versus Nifty."""
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
render_page_header("🔄","Sector Rotation","Live NSE sector relative strength vs Nifty 50")
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
sectors_map = {
    "Bank": "^NSEBANK", "IT": "^CNXIT", "Pharma": "^CNXPHARMA", 
    "FMCG": "^CNXFMCG", "Auto": "^CNXAUTO", "Metal": "^CNXMETAL", 
    "Realty": "^CNXREALTY", "Energy": "^CNXENERGY", "Infra": "^CNXINFRA", "Media": "^CNXMEDIA"
}
@st.cache_data(ttl=3600)
def get_rs_data():
    bench = safe_yf_download("^NSEI", period="1y")
    if bench is None or bench.empty:
        return pd.DataFrame(), ["NIFTY benchmark unavailable"]

    def _calc_ret(df, days):
        if len(df) < days:
            return np.nan
        return (df["Close"].iloc[-1] / df["Close"].iloc[-days] - 1) * 100

    bench_1m = _calc_ret(bench, 21)
    bench_3m = _calc_ret(bench, 63)
    bench_6m = _calc_ret(bench, 126)

    rows = []
    missing = []
    for sec, sym in sectors_map.items():
        df = safe_yf_download(sym, period="1y")
        if df is not None and not df.empty:
            s_1m = _calc_ret(df, 21)
            s_3m = _calc_ret(df, 63)
            s_6m = _calc_ret(df, 126)
            rows.append(
                {
                    "Sector": sec,
                    "1M RS": s_1m - bench_1m,
                    "3M RS": s_3m - bench_3m,
                    "6M RS": s_6m - bench_6m,
                }
            )
        else:
            missing.append(sec)

    df_rs = pd.DataFrame(rows)
    return df_rs, missing

with st.spinner("Calculating live Sector Relative Strength vs Nifty 50..."):
    df_rs, missing_sectors = get_rs_data()

if df_rs.empty:
    st.warning("Live sector data unavailable right now.")
    st.stop()

if missing_sectors:
    st.info(f"Skipped sectors with unavailable live data: {', '.join(missing_sectors)}")

period_column = {"1M": "1M RS", "3M": "3M RS", "6M": "6M RS", "1Y": "6M RS"}[period_sel]
df_rs["Momentum"] = df_rs["1M RS"] - df_rs["3M RS"]
df_rs["Trend"] = df_rs[period_column].apply(lambda x: "🟢 Outperforming" if x > 0 else "🔴 Underperforming")

def classify_stage(row):
    rs_value = float(row[period_column])
    momentum = float(row["Momentum"])
    if rs_value >= 0 and momentum >= 0:
        return "Leading"
    if rs_value >= 0 and momentum < 0:
        return "Weakening"
    if rs_value < 0 and momentum >= 0:
        return "Improving"
    return "Lagging"

df_rs["Stage"] = df_rs.apply(classify_stage, axis=1)
df_rs = df_rs.sort_values(period_column, ascending=False).reset_index(drop=True)

fig=go.Figure(go.Heatmap(z=[df_rs["1M RS"],df_rs["3M RS"],df_rs["6M RS"]],x=df_rs["Sector"],y=["1M RS","3M RS","6M RS"],
                          colorscale=[[0,"#f43f5e"],[0.5,"#161922"],[1,"#00d4aa"]],
                          text=[[f"{v:.1f}%" for v in r] for r in [df_rs["1M RS"],df_rs["3M RS"],df_rs["6M RS"]]],
                          texttemplate="%{text}",textfont=dict(size=10),zmid=0))
fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                   height=260,margin=dict(l=0,r=0,t=30,b=0),
                   title=dict(text="Sector RS vs Nifty 50 (%)",font=dict(color="#e8eaf6")),
                   font=dict(color="#e8eaf6"))
st.plotly_chart(fig, width="stretch")

col1,col2=st.columns(2)
with col1:
    st.markdown(f"#### {period_column}")
    fig2=go.Figure(go.Bar(x=df_rs[period_column],y=df_rs["Sector"],orientation="h",
                           marker_color=["#00d4aa" if v>0 else "#f43f5e" for v in df_rs[period_column]],
                           text=[f"{v:.1f}%" for v in df_rs[period_column]],textposition="outside"))
    fig2.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                        height=340,margin=dict(l=0,r=60,t=10,b=0),
                        xaxis=dict(gridcolor="#2d3554"),yaxis=dict(gridcolor="#2d3554"))
    st.plotly_chart(fig2, width="stretch")
with col2:
    st.markdown("#### Rotation Table")
    st.dataframe(df_rs[["Sector","1M RS","3M RS","6M RS","Trend","Stage"]].round(1), width="stretch", hide_index=True)
    st.markdown("#### Stage")
    for _, row in df_rs.iterrows():
        sec = row["Sector"]
        stage = row["Stage"]
        clr={"Leading":"#00d4aa","Improving":"#3b82f6","Weakening":"#f59e0b","Lagging":"#f43f5e"}[stage]
        st.markdown(f"""<div style='display:flex;justify-content:space-between;padding:.4rem .8rem;background:#161922;border-radius:6px;margin:.2rem 0;border:1px solid #2d3554;'>
        <span>{sec}</span><span style='color:{clr};font-weight:600;'>{stage}</span></div>""",unsafe_allow_html=True)
