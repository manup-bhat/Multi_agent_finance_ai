"""Page 9: News Sentiment — global ticker via render_global_sidebar()."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streamlit as st, plotly.graph_objects as go, pandas as pd
from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="News Sentiment · India Engine", page_icon="📰", layout="wide")
flat_css(); st.session_state["_page_id"] = "news"

sources_sel = ["Moneycontrol","ET Markets","Business Standard"]
def _extras():
    global sources_sel
    sources_sel = st.multiselect("Sources",["Moneycontrol","ET Markets","Business Standard","SEBI","RBI","Reddit"],
                                  default=["Moneycontrol","ET Markets","Business Standard"])

ticker    = render_global_sidebar(page_extra_fn=_extras)
base_name = ticker.replace(".NS","").replace(".BO","")
render_page_header("📰","News Sentiment",f"{base_name} · FinBERT-scored feed · SEBI/RBI alerts")
render_help_popover("News Sentiment","""
**FinBERT scores** range -1 (bearish) to +1 (bullish). Composite = weighted average.

**Interpreting:**
- > +0.4 → Strong positive momentum
- -0.2 to +0.2 → Mixed/neutral
- < -0.4 → Negative catalysts → defensive stance

**SEBI/RBI articles** → act immediately (compliance impact).
**Reddit** → retail contrarian signal (contrary to headline sentiment).
""")

import requests

@st.cache_data(ttl=600)
def fetch_sentiment(ticker_str):
    try:
        r = requests.post("http://localhost:8000/sentiment", json={"ticker": ticker_str}, timeout=30)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

with st.spinner("Fetching live sentiment from FinBERT & Scraping News..."):
    res = fetch_sentiment(ticker)

if not res:
    st.warning("Sentiment API unavailable right now. Showing an empty fallback state.")
    res = {"composite_score": 0.0, "composite_label": "NEUTRAL", "articles": [], "warnings": ["Sentiment API request failed."]}

warnings = res.get("warnings") or []
if warnings:
    st.info(" | ".join(str(w) for w in warnings))

if not res.get("articles"):
    st.info("No recent articles matched this ticker in the active sentiment window.")
    df_news = pd.DataFrame(columns=["source", "headline", "sentiment", "label", "date"])
    avg = float(res.get("composite_score", 0.0))
    lbl = res.get("composite_label", "NEUTRAL")
else:
    news = res["articles"]
    df_news  = pd.DataFrame(news)
    avg = float(res.get("composite_score", 0.0))
    lbl = res.get("composite_label", "NEUTRAL")

source_map = {
    "Moneycontrol": "moneycontrol",
    "ET Markets": "et_markets",
    "Business Standard": "business_standard",
    "SEBI": "sebi",
    "RBI": "rbi",
    "Reddit": "reddit"
}
mapped_sources = [source_map.get(s, s.lower()) for s in sources_sel]
df_filt  = df_news[df_news["source"].isin(mapped_sources)] if sources_sel and not df_news.empty else df_news

col_dist, col_sum = st.columns([1.5,1])
with col_dist:
    if not df_news.empty:
        lc = df_news["label"].value_counts()
        pie = go.Figure(go.Pie(labels=lc.index, values=lc.values,
                                marker_colors=[{"POSITIVE":"#00d4aa","NEUTRAL":"#f59e0b","NEGATIVE":"#f43f5e"}.get(l,"#8892b0") for l in lc.index],
                                hole=0.5, textfont=dict(color="#e8eaf6")))
        pie.update_layout(paper_bgcolor="#161922",font=dict(color="#e8eaf6"),height=220,
                           margin=dict(l=0,r=0,t=30,b=0),
                           title=dict(text="Sentiment Distribution",font=dict(color="#e8eaf6",size=13)),
                           legend=dict(font=dict(color="#8892b0"),bgcolor="#161922"))
        st.plotly_chart(pie, width="stretch")
    else:
        st.write("No sentiment data to display.")

with col_sum:
    clr="#00d4aa" if avg>0.2 else ("#f43f5e" if avg<-0.2 else "#f59e0b")
    st.markdown(f"""<div style='background:#161922;border:1.5px solid {clr};border-radius:12px;padding:1.25rem;text-align:center;margin-top:.5rem;'>
    <div style='font-size:.72rem;color:#8892b0;'>Composite FinBERT · {base_name}</div>
    <div style='font-size:2rem;font-weight:800;color:{clr};'>{avg:+.2f}</div>
    <div style='color:{clr};font-weight:600;'>{lbl}</div>
    <div style='color:#8892b0;font-size:.8rem;'>{len(df_news)} articles</div></div>""",unsafe_allow_html=True)

st.markdown("#### Latest Articles")
for _,row in df_filt.iterrows():
    s_clr={"POSITIVE":"#00d4aa","NEUTRAL":"#f59e0b","NEGATIVE":"#f43f5e"}.get(row["label"],"#8892b0")
    s_icon={"POSITIVE":"↑","NEUTRAL":"~","NEGATIVE":"↓"}.get(row["label"],"?")
    st.markdown(f"""<div style='background:#161922;border:1px solid #2d3554;border-left:3px solid {s_clr};border-radius:8px;padding:.75rem 1rem;margin:.4rem 0;'>
      <div style='display:flex;justify-content:space-between;'>
        <span style='color:#e8eaf6;font-weight:500;'>{row["headline"]}</span>
        <span style='color:{s_clr};font-weight:700;'>{s_icon} {row["sentiment"]:+.2f}</span>
      </div>
      <div style='margin-top:4px;'>
        <span style='background:#2d3554;color:#8892b0;border-radius:4px;padding:2px 8px;font-size:.72rem;'>{row["source"]}</span>
        <span style='color:#8892b0;font-size:.72rem;margin-left:8px;'>{row["date"]}</span>
      </div></div>""",unsafe_allow_html=True)
