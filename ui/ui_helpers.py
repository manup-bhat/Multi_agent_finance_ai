"""
Shared UI helpers for India Multi-Agent Engine Streamlit pages.

KEY ARCHITECTURE NOTE:
  In Streamlit multipage (pages/ folder), app.py runs ONLY on the home page.
  Each sub-page must define its own sidebar.
  render_global_sidebar() renders the full ticker picker on EVERY page
  and writes the result back to session_state["global_ticker"] so it persists
  across all pages.
"""
from __future__ import annotations
import io, contextlib
import streamlit as st

# ── Verified NSE tickers on Yahoo Finance ─────────────────────────────────
QUICK_PICKS = [
    "HDFCBANK.NS", "RELIANCE.NS", "TCS.NS", "INFY.NS", "ICICIBANK.NS",
    "KOTAKBANK.NS", "SBIN.NS",    "AXISBANK.NS", "BAJFINANCE.NS", "WIPRO.NS",
    "LT.NS",        "ITC.NS",     "MARUTI.NS",   "SUNPHARMA.NS",  "TATAMOTORS.NS",
    "TITAN.NS",     "ADANIENT.NS","HINDUNILVR.NS","ASIANPAINT.NS","BAJAJFINSV.NS",
    "ULTRACEMCO.NS","NESTLEIND.NS","POWERGRID.NS","NTPC.NS",      "ONGC.NS",
]


def render_global_sidebar(page_extra_fn=None) -> str:
    """Render the full global ticker search in the sidebar and return the active ticker.

    This must be called inside `with st.sidebar:` block (or it opens its own).
    Reads AND writes st.session_state["global_ticker"] so the choice persists
    across all pages.

    Args:
        page_extra_fn: Optional callable that renders extra page-specific sidebar widgets.
    Returns:
        str: The resolved NSE ticker (e.g. "RELIANCE.NS").
    """
    with st.sidebar:
        # ── Branding ─────────────────────────────────────────────────────
        st.markdown("""
<div style='text-align:center;padding:.75rem 0 .5rem 0;'>
  <div style='font-size:2rem;'>📈</div>
  <div style='font-size:.95rem;font-weight:800;color:#e8eaf6;'>India Engine</div>
  <div style='font-size:.6rem;color:#8892b0;letter-spacing:.12em;text-transform:uppercase;'>Multi-Agent AI v12</div>
</div>
<hr style='border-color:#2d3554;margin:.4rem 0;'>
""", unsafe_allow_html=True)

        st.markdown("### 🔍 Global Stock Search")
        st.markdown(
            "<div style='font-size:.7rem;color:#8892b0;margin-bottom:.25rem;'>"
            "Enter ticker once — all pages update automatically</div>",
            unsafe_allow_html=True,
        )

        def _on_quick_pick():
            qp = st.session_state.get(f"_gquick_{st.session_state.get('_page_id','home')}")
            if qp and qp != "— Select popular stock —":
                st.session_state[f"_gticker_{st.session_state.get('_page_id','home')}"] = qp

        current = st.session_state.get("global_ticker", "RELIANCE.NS")
        
        manual = st.text_input(
            "Ticker (NSE .NS format)",
            value=current,
            placeholder="e.g. RELIANCE.NS",
            key=f"_gticker_{st.session_state.get('_page_id','home')}",
            help="NSE symbol + .NS suffix. Indices: ^NSEI (Nifty 50), ^NSEBANK",
            label_visibility="collapsed",
        )

        quick = st.selectbox(
            "Or pick from popular:",
            ["— Select popular stock —"] + QUICK_PICKS,
            index=0,
            key=f"_gquick_{st.session_state.get('_page_id','home')}",
            on_change=_on_quick_pick,
            label_visibility="collapsed",
        )

        raw = (st.session_state.get(f"_gticker_{st.session_state.get('_page_id','home')}", current)).strip().upper()
        if raw and not any(raw.endswith(s) for s in (".NS", ".BO", "^NSEI", "^NSEBANK", "^INDIAVIX", "^NSEMDCP50")):
            raw += ".NS"
        resolved = raw or "RELIANCE.NS"

        # Write back
        st.session_state["global_ticker"] = resolved

        # Active ticker pill
        st.markdown(
            f"<div style='display:inline-flex;align-items:center;gap:6px;"
            f"background:#1c2130;border:1.5px solid #3b82f6;border-radius:16px;"
            f"padding:5px 12px;font-size:.8rem;font-weight:700;color:#3b82f6;margin:.3rem 0;'>"
            f"📊 {resolved}</div>",
            unsafe_allow_html=True,
        )

        # Shared horizon
        st.session_state["global_horizon"] = st.selectbox(
            "Forecast Horizon", [5, 10, 15, 30],
            index=[5, 10, 15, 30].index(st.session_state.get("global_horizon", 5)),
            help="Shared across Dashboard, Predictions, Backtest",
        )

        st.markdown("<hr style='border-color:#2d3554;margin:.5rem 0;'>", unsafe_allow_html=True)

        # Optional page-specific extras
        if page_extra_fn:
            page_extra_fn()

        st.markdown(
            "<div style='font-size:.65rem;color:#8892b0;text-align:center;margin-top:.5rem;'>"
            "⚠️ Not investment advice</div>", unsafe_allow_html=True
        )

    return resolved


def get_global_ticker(fallback: str = "HDFCBANK.NS") -> str:
    """Read-only access to the global ticker (use render_global_sidebar() on full pages)."""
    return st.session_state.get("global_ticker", fallback)


def flat_css() -> None:
    """Inject shared dark-mode CSS."""
    st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
.stApp{background:#0d0f14;font-family:'Inter',sans-serif;color:#e8eaf6;}
.main .block-container{max-width:1400px;padding-top:1.25rem;}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0f1117,#161922);border-right:1px solid #2d3554;}
[data-testid="stMetric"]{background:#161922;border:1px solid #2d3554;border-radius:12px;padding:1rem 1.25rem;}
[data-testid="stMetricLabel"]{color:#8892b0!important;font-size:.78rem!important;text-transform:uppercase;letter-spacing:.08em;}
[data-testid="stMetricValue"]{color:#e8eaf6!important;font-weight:700;}
.stButton>button{background:linear-gradient(135deg,#00d4aa,#3b82f6);color:#0d0f14;font-weight:700;border:none;border-radius:8px;transition:opacity .2s;}
.stButton>button:hover{opacity:.85;}
.stDataFrame{border:1px solid #2d3554;border-radius:8px;}
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-thumb{background:#2d3554;border-radius:3px;}
</style>""", unsafe_allow_html=True)


def render_page_header(icon: str, title: str, subtitle: str) -> None:
    """Render a consistent page header."""
    st.markdown(
        f"""<div style='display:flex;align-items:center;gap:12px;margin-bottom:1rem;'>
  <span style='font-size:2rem;'>{icon}</span>
  <div>
    <h1 style='margin:0;font-size:1.7rem;font-weight:800;color:#e8eaf6;'>{title}</h1>
    <p style='margin:0;color:#8892b0;font-size:.82rem;'>{subtitle}</p>
  </div>
</div>""", unsafe_allow_html=True
    )


def render_help_popover(title: str, content: str) -> None:
    """Render a ℹ️ How to Use popover button (Streamlit 1.31+)."""
    with st.popover("ℹ️ How to Use This Page", width="content"):
        st.markdown(f"### {title}")
        st.markdown(content)


@contextlib.contextmanager
def suppress_yf_print():
    """Context manager that swallows yfinance progress/error print output."""
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        yield


def safe_yf_download(ticker: str, period: str = "6mo", interval: str = "1d"):
    """Download yfinance data safely: suppress print noise + flatten multi-level cols.
    Returns empty DataFrame on failure.
    """
    import pandas as pd
    try:
        import yfinance as yf
        with suppress_yf_print():
            df = yf.download(ticker, period=period, interval=interval,
                             progress=False, auto_adjust=True)
        # Flatten multi-level columns (yfinance 0.2.x+ and 1.x.x)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).warning("safe_yf_download_failed", error=str(e), ticker=ticker)
        return pd.DataFrame()
