"""Page 13: Audit Trail — shows the latest real analysis artifacts available in-session."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pandas as pd
import streamlit as st

from ui_helpers import render_global_sidebar, flat_css, render_page_header, render_help_popover

st.set_page_config(page_title="Audit Trail · India Engine", page_icon="🔍", layout="wide")
flat_css(); st.session_state["_page_id"] = "audit"


def _extras():
    st.caption("This page uses the latest real analysis already loaded in the app session.")


ticker = render_global_sidebar(page_extra_fn=_extras)
render_page_header("🔍","Agent Audit Trail",f"{ticker} · Latest real session state")
render_help_popover("Audit Trail","""
This page no longer renders synthetic agent timelines.

What you see here:
- Latest real `dashboard_result` cached in this Streamlit session
- Current Phoenix endpoint, if configured
- Any risk notes and summaries returned by the live API
""")

phoenix_host = os.environ.get("PHOENIX_HOST", "localhost")
phoenix_port = os.environ.get("PHOENIX_PORT", "6006")
phoenix_url = f"http://{phoenix_host}:{phoenix_port}"

st.markdown(f"""<div style='background:#161922;border:1px solid #3b82f6;border-radius:10px;padding:.9rem 1.5rem;margin-bottom:1rem;'>
<div style='font-weight:600;color:#e8eaf6;'>Phoenix Observability</div>
<div style='font-size:.82rem;color:#8892b0;'>Configured endpoint: <a href='{phoenix_url}' target='_blank' style='color:#3b82f6;'>{phoenix_url}</a></div>
</div>""", unsafe_allow_html=True)

dashboard_result = st.session_state.get("dashboard_result")
dashboard_ticker = st.session_state.get("dashboard_ticker")

if not dashboard_result or dashboard_ticker != ticker:
    st.info("Run a live analysis for this ticker from the Dashboard page to populate the audit trail.")
    st.stop()

summary_rows = [
    ("Ticker", dashboard_result.get("ticker")),
    ("Verdict", dashboard_result.get("verdict")),
    ("Confidence", f"{dashboard_result.get('confidence', 0.0) * 100:.1f}%"),
    ("Regime", dashboard_result.get("regime")),
    ("Risk Level", dashboard_result.get("risk_level")),
    ("Circuit Breaker", dashboard_result.get("circuit_breaker_active")),
]

st.markdown("#### Latest Analysis Snapshot")
st.dataframe(pd.DataFrame(summary_rows, columns=["Field", "Value"]), width="stretch", hide_index=True)

st.markdown("#### Returned Summaries")
sections = [
    ("Quant Summary", dashboard_result.get("quant_summary", "")),
    ("Macro Summary", dashboard_result.get("macro_summary", "")),
    ("Emotion Summary", dashboard_result.get("emotion_summary", "")),
    ("F&O Summary", dashboard_result.get("fno_summary", "")),
]
for label, value in sections:
    st.markdown(f"**{label}**")
    st.write(value or "Unavailable")

st.markdown("#### Key Risks")
risks = dashboard_result.get("key_risks", [])
if risks:
    st.dataframe(pd.DataFrame({"risk": risks}), width="stretch", hide_index=True)
else:
    st.write("No risk notes returned.")
