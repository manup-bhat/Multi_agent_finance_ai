"""
India Multi-Agent Engine — Streamlit Main App
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Global ticker is stored in st.session_state["global_ticker"].
All pages read from this state — no need to re-enter ticker on each page.
"""
import streamlit as st
import datetime

st.set_page_config(
    page_title="India Multi-Agent Engine",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://github.com",
        "About": "India Multi-Agent Financial Prediction Engine v12.0",
    },
)

# ── Global CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
:root{--bg:#0d0f14;--card:#161922;--card2:#1c2130;--green:#00d4aa;--blue:#3b82f6;--red:#f43f5e;--gold:#f59e0b;--muted:#8892b0;--border:#2d3554;--text:#e8eaf6;}
.stApp{background:var(--bg);font-family:'Inter',sans-serif;color:var(--text);}
.main .block-container{max-width:1400px;padding-top:1.25rem;padding-bottom:2rem;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0f1117 0%,#161922 100%);border-right:1px solid var(--border);}
[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{color:var(--green)!important;font-size:.72rem!important;letter-spacing:.12em;text-transform:uppercase;font-weight:600;}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1rem 1.25rem;}
[data-testid="stMetricLabel"]{color:var(--muted)!important;font-size:.78rem!important;text-transform:uppercase;letter-spacing:.08em;}
[data-testid="stMetricValue"]{color:var(--text)!important;font-size:1.5rem!important;font-weight:700;line-height:1.2!important;}
[data-testid="stMetricLabel"],[data-testid="stMetricValue"],[data-testid="stMetricDelta"],[data-testid="stMetricDeltaDescription"]{overflow:visible!important;}
[data-testid="stMetricLabel"] *,[data-testid="stMetricValue"] *,[data-testid="stMetricDelta"] *,[data-testid="stMetricDeltaDescription"] *{white-space:normal!important;overflow:visible!important;text-overflow:clip!important;overflow-wrap:anywhere;word-break:break-word;}
.stButton>button{background:linear-gradient(135deg,var(--green),var(--blue));color:#0d0f14;font-weight:700;border:none;border-radius:8px;padding:.45rem 1.25rem;transition:opacity .2s,transform .15s;}
.stButton>button:hover{opacity:.85;transform:translateY(-1px);}
.stTextInput>div>div{background:var(--card)!important;border:1px solid var(--border)!important;color:var(--text)!important;border-radius:8px;}
.stSelectbox>div>div{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:8px;}
.stDataFrame{border:1px solid var(--border);border-radius:8px;}
.stDataFrame thead th{background:var(--card2)!important;color:var(--muted)!important;font-size:.78rem;text-transform:uppercase;}
.stTabs [data-baseweb="tab-list"]{background:var(--card);border-radius:10px;padding:4px;gap:4px;}
.stTabs [data-baseweb="tab"]{background:transparent;border-radius:8px;color:var(--muted);font-weight:500;font-size:.85rem;padding:8px 16px;}
.stTabs [aria-selected="true"]{background:var(--card2)!important;color:var(--green)!important;}
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px;}
/* Global ticker pill */
.ticker-pill{display:inline-flex;align-items:center;gap:8px;background:#1c2130;border:1.5px solid #3b82f6;border-radius:20px;padding:6px 14px;font-size:.85rem;font-weight:700;color:#3b82f6;margin-bottom:.5rem;}
/* Help popover trigger */
[data-testid="stPopover"]>div>button{background:transparent!important;border:1px solid #2d3554!important;color:#8892b0!important;font-size:.78rem!important;padding:4px 10px!important;border-radius:6px!important;}
[data-testid="stPopover"]>div>button:hover{border-color:#3b82f6!important;color:#3b82f6!important;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar — Global Ticker Search ─────────────────────────────────────────
with st.sidebar:
    # Logo / branding
    st.markdown("""
    <div style='text-align:center;padding:1rem 0 .75rem 0;'>
      <div style='font-size:2.2rem;'>📈</div>
      <div style='font-size:1rem;font-weight:800;color:#e8eaf6;letter-spacing:.04em;'>India Engine</div>
      <div style='font-size:.65rem;color:#8892b0;letter-spacing:.12em;text-transform:uppercase;'>Multi-Agent AI v12</div>
    </div>
    <hr style='border-color:#2d3554;margin:.5rem 0;'>
    """, unsafe_allow_html=True)

    # ── GLOBAL TICKER SEARCH ────────────────────────────────────────────────
    st.markdown("### 🔍 Global Stock Search")
    st.markdown(
        "<div style='font-size:.72rem;color:#8892b0;margin-bottom:.35rem;'>"
        "Enter ticker once — all pages update automatically</div>",
        unsafe_allow_html=True,
    )

    # Common NSE stocks quick-pick
    QUICK_PICKS = [
        "HDFCBANK.NS","RELIANCE.NS","TCS.NS","INFY.NS","ICICIBANK.NS",
        "KOTAKBANK.NS","SBIN.NS","AXISBANK.NS","BAJFINANCE.NS","WIPRO.NS",
        "LT.NS","ITC.NS","MARUTI.NS","SUNPHARMA.NS","TATAMOTORS.NS","TITAN.NS",
        "ZOMATO.NS","ADANIENT.NS","HINDUNILVR.NS","ASIANPAINT.NS",
    ]

    # Text input (manual)
    manual_ticker = st.text_input(
        "Ticker (NSE format)",
        value=st.session_state.get("global_ticker", "HDFCBANK.NS"),
        placeholder="e.g. RELIANCE.NS",
        key="_ticker_input",
        help="Use NSE symbol + .NS suffix. e.g. HDFCBANK → HDFCBANK.NS",
        label_visibility="collapsed",
    )

    # Quick-pick dropdown
    quick = st.selectbox(
        "Quick Pick",
        ["— Select popular stock —"] + QUICK_PICKS,
        index=0,
        key="_quick_pick",
        label_visibility="collapsed",
    )

    # Resolve ticker: quick-pick overrides text input if user selected one
    if quick and quick != "— Select popular stock —":
        resolved_ticker = quick
    else:
        resolved_ticker = manual_ticker.strip() or "HDFCBANK.NS"
        if resolved_ticker and not resolved_ticker.upper().endswith((".NS", ".BO", "^NSEI", "^NSEBANK")):
            resolved_ticker = resolved_ticker.upper() + ".NS"

    st.session_state["global_ticker"] = resolved_ticker

    # Show active ticker pill
    st.markdown(
        f"<div class='ticker-pill'>📊 {resolved_ticker}</div>",
        unsafe_allow_html=True,
    )

    # Horizon picker (shared)
    st.session_state["global_horizon"] = st.selectbox(
        "Forecast Horizon", [5, 10, 15, 30], index=0,
        help="Applied to Dashboard, Predictions, and Backtest pages",
    )

    st.markdown("<hr style='border-color:#2d3554;margin:.75rem 0;'>", unsafe_allow_html=True)

    # Nav guide
    st.markdown("### 🗺 Pages")
    st.markdown("""
<div style='font-size:.78rem;color:#8892b0;line-height:1.9;'>
📊 <b style='color:#e8eaf6;'>Dashboard</b> — Full 9-agent analysis<br>
📐 <b style='color:#e8eaf6;'>Technical</b> — OHLCV + SMC zones<br>
🔮 <b style='color:#e8eaf6;'>Predictions</b> — Chronos-2 forecast<br>
😨 <b style='color:#e8eaf6;'>Emotion</b> — FinBERT + F&G<br>
⚡ <b style='color:#e8eaf6;'>F&O</b> — Options chain<br>
🏦 <b style='color:#e8eaf6;'>FII/DII</b> — Fund flows<br>
🌏 <b style='color:#e8eaf6;'>Macro</b> — VIX + Crude + INR<br>
🔄 <b style='color:#e8eaf6;'>Sectors</b> — Rotation heatmap<br>
📰 <b style='color:#e8eaf6;'>News</b> — Sentiment feed<br>
🛡️ <b style='color:#e8eaf6;'>Risk</b> — Kelly + Drawdown<br>
📈 <b style='color:#e8eaf6;'>Backtest</b> — Walk-forward<br>
🎯 <b style='color:#e8eaf6;'>Model</b> — Accuracy tracker<br>
🔍 <b style='color:#e8eaf6;'>Audit</b> — Agent trace<br>
</div>
""", unsafe_allow_html=True)

    st.markdown("<hr style='border-color:#2d3554;margin:.75rem 0;'>", unsafe_allow_html=True)
    st.markdown(
        "<div style='font-size:.65rem;color:#8892b0;text-align:center;'>"
        "SEBI Compliant · 10 OPS · Static IP<br>⚠️ Not investment advice</div>",
        unsafe_allow_html=True,
    )

# ── Home landing page ───────────────────────────────────────────────────────
st.markdown(f"""
<div style='text-align:center;padding:2.5rem 0 1.5rem 0;'>
  <div style='font-size:3.5rem;margin-bottom:.5rem;'>📈</div>
  <h1 style='font-size:2.4rem;font-weight:800;
     background:linear-gradient(135deg,#00d4aa,#3b82f6);
     -webkit-background-clip:text;-webkit-text-fill-color:transparent;margin:0;'>
    India Multi-Agent Engine
  </h1>
  <p style='color:#8892b0;font-size:.95rem;margin-top:.75rem;'>
    9-Agent LangGraph · Chronos-2 TSFM · FinBERT · India VIX · SEBI Compliant
  </p>
  <div style='margin-top:1rem;background:#1c2130;display:inline-block;
       border:1.5px solid #3b82f6;border-radius:24px;padding:8px 24px;
       font-size:1rem;font-weight:700;color:#e8eaf6;'>
    📊 Active Ticker: <span style='color:#00d4aa;'>{resolved_ticker}</span>
  </div>
</div>
""", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Agents Online", "9", "All Active ✅")
with col2:
    st.metric("Models", "Chronos-2+3ML", "Ensemble")
with col3:
    st.metric("Data Sources", "9+", "Live")
with col4:
    st.metric("SEBI OPS", "10/s", "Compliant ✅")

st.markdown("<br>", unsafe_allow_html=True)
st.info(
    f"👈 **Active ticker: `{resolved_ticker}`** — set in sidebar. "
    "Navigate to any page — it will automatically use this ticker. "
    "Change the ticker in the sidebar to update all pages at once."
)

# Quick action buttons
b1, b2, b3, b4 = st.columns(4)
with b1:
    st.page_link("pages/1_Dashboard.py",    label="📊 Open Dashboard",   width="stretch")
with b2:
    st.page_link("pages/2_Technical.py",    label="📐 Technical Chart",  width="stretch")
with b3:
    st.page_link("pages/3_Predictions.py",  label="🔮 ML Predictions",   width="stretch")
with b4:
    st.page_link("pages/11_Backtest_Results.py", label="📈 Run Backtest", width="stretch")

# Live clock
st.markdown(
    f"<div style='text-align:right;color:#8892b0;font-size:.72rem;margin-top:1rem;'>"
    f"🕐 Last refreshed: {datetime.datetime.now().strftime('%H:%M:%S IST')}"
    f"</div>",
    unsafe_allow_html=True,
)
