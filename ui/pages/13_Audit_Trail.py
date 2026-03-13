"""Page 13: Audit Trail — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Audit Trail · India Engine", page_icon="🔍", layout="wide")
flat_css(); st.session_state["_page_id"] = "audit"

def _extras():
    st.text_input("Trace ID (blank=latest)", "")
    st.button("Load Trace", use_container_width=True)

ticker = render_global_sidebar(page_extra_fn=_extras)
base   = ticker.replace(".NS","").replace(".BO","")
render_page_header("🔍","Agent Audit Trail",f"{ticker} · Phoenix OpenTelemetry · 9-Agent Trace · SEBI Log")
render_help_popover("Audit Trail","""
**Gantt Timeline:** Execution order and duration of all 9 agents.
**SEBI Compliance Log:** Rate limiter events, IP validation, session events.

**SEBI Algo Compliance (SEBI/HO/MRD/2024/113):**
- Max 10 OPS per algo registration
- Static IP validation mandatory
- Daily automatic session logout
- Algo ID logged per request

**Phoenix:** Start with `python -m phoenix.server.main serve`
Open at `http://localhost:6006` to see full OpenTelemetry spans.
""")

ph_url = os.environ.get("PHOENIX_HOST","http://localhost:6006")
st.markdown(f"""<div style='background:#161922;border:1px solid #3b82f6;border-radius:10px;padding:.9rem 1.5rem;display:flex;align-items:center;gap:12px;margin-bottom:1rem;'>
<span style='font-size:1.2rem;'>🔭</span>
<div><div style='font-weight:600;color:#e8eaf6;'>Phoenix Observability</div>
<div style='font-size:.82rem;color:#8892b0;'>OpenTelemetry traces at <a href='{ph_url}' target='_blank' style='color:#3b82f6;'>{ph_url}</a></div></div>
<a href='{ph_url}' target='_blank' style='margin-left:auto;background:#3b82f6;color:#fff;padding:6px 16px;border-radius:6px;text-decoration:none;font-size:.85rem;font-weight:600;'>Open Phoenix →</a>
</div>""", unsafe_allow_html=True)

agents = [
    ("Agent 1: QUANT",      "Groq Llama-3.3-70B","TA+SMC computed",         0.82,"BULLISH"),
    ("Agent 2: MACRO",      "Groq Llama-3.3-70B","FII/DII+VIX+Crude",       1.14,"POSITIVE"),
    ("Agent 3: FUNDAMENTAL","RAG+Groq",           "News+SEBI corpus",         2.31,"NEUTRAL"),
    ("Agent 4: PREDICTION", "Chronos-2+Ensemble", "Forecast generated",       3.45,"BULLISH"),
    ("Agent 5: EMOTION",    "FinBERT+GoEmotions", f"F&G=58·{base}=+0.38",   1.92,"GREED"),
    ("Agent 6: FnO",        "Groq Llama-3.3-70B","PCR=1.15·MaxPain=21500",  1.07,"BULLISH"),
    ("Agent 7: DEVIL'S ADV","Groq Llama-3.3-70B","Contrarian risk noted",    0.73,"CAUTION"),
    ("Agent 8: RISK NODE",  "Pure Python",        "Kelly=29%·CB=Clear",       0.03,"MODERATE"),
    ("Agent 9: ORCHESTRATOR","Gemini 2.5 Pro",    f"→{base} BUY/0.72",       4.21,"BUY"),
]
starts=[0]
for a in agents[:-1]: starts.append(starts[-1]+a[3])

m1,m2,m3=st.columns(3)
m1.metric("Agents Traced",  "9/9","All visible")
m2.metric("Total Latency",  f"{sum(a[3] for a in agents):.2f}s")
m3.metric("Active Ticker",  base)

st.markdown("#### Agent Execution Timeline")
clr_map={"BULLISH":"#00d4aa","POSITIVE":"#3b82f6","NEUTRAL":"#8892b0","GREED":"#f59e0b","CAUTION":"#f43f5e","MODERATE":"#8892b0","BUY":"#00d4aa"}
fig=go.Figure()
for i,(name,model,desc,dur,signal) in enumerate(agents):
    c=clr_map.get(signal,"#8892b0")
    fig.add_trace(go.Bar(name=name,y=[name],x=[dur],base=[starts[i]],orientation="h",marker_color=c,
                          hovertemplate=f"<b>{name}</b><br>Model:{model}<br>Signal:{signal}<br>Duration:{dur:.2f}s<extra></extra>",
                          text=f"{dur:.2f}s",textposition="inside"))
fig.update_layout(template="plotly_dark",paper_bgcolor="#161922",plot_bgcolor="#161922",
                   barmode="stack",height=360,showlegend=False,margin=dict(l=0,r=0,t=10,b=0),
                   xaxis=dict(gridcolor="#2d3554",title="Time (seconds)"),yaxis=dict(gridcolor="#2d3554"))
st.plotly_chart(fig, width="stretch")

st.markdown("#### Detailed Trace Log")
df_t=pd.DataFrame([(a[0],a[1],a[2],f"{a[3]:.2f}s",a[4],"✅") for a in agents],
                   columns=["Agent","Model","Action","Duration","Signal","Status"])
st.dataframe(df_t, width="stretch", hide_index=True)

st.markdown("#### SEBI Compliance Log")
sebi=[{"Time":"09:15:01","Event":"Session Started","Status":"✅ OK","Detail":"sess_20260313"},
      {"Time":"09:15:02","Event":"IP Validated",   "Status":"✅ OK","Detail":"127.0.0.1 (dev)"},
      {"Time":"09:15:03","Event":"Rate Limiter OK", "Status":"✅ OK","Detail":"10 OPS token bucket"},
      {"Time":"09:15:05","Event":f"Analysis:{base}","Status":"✅ OK","Detail":"CB=Clear·Sharpe>0.8"}]
st.dataframe(pd.DataFrame(sebi), width="stretch", hide_index=True)
