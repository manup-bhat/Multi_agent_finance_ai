"""POST /fno/analyze — live F&O analysis."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
import pandas as pd
import structlog

from api.schemas import FnORequest
from data.adapters.nsefin_client import MarketClosedError, NSEFinClient
from data.adapters.nselib_client import NSELibClient
from data.adapters.yfinance_client import YFinanceClient
from fno.fno_reporter import build_fno_report

logger = structlog.get_logger(__name__)
router = APIRouter()
INDEX_SPOT_MAP = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}


def _extract_atm_iv(chain_df: pd.DataFrame, spot: float) -> float | None:
    if chain_df.empty or "strike_price" not in chain_df.columns:
        return None
    iv_col = next((c for c in ["implied_volatility", "iv"] if c in chain_df.columns), None)
    if iv_col is None:
        return None
    nearest = chain_df.iloc[(chain_df["strike_price"] - spot).abs().argsort()[:2]]
    iv = pd.to_numeric(nearest[iv_col], errors="coerce").dropna()
    return float(iv.mean()) if not iv.empty else None


def _participant_oi_to_dict(df: pd.DataFrame | None) -> dict:
    base = {
        "FII": {"long": None, "short": None, "net": None},
        "DII": {"long": None, "short": None, "net": None},
        "Client": {"long": None, "short": None, "net": None},
    }
    if df is None or df.empty:
        return base

    name_col = next((c for c in df.columns if "client_type" in c or "category" in c), None)
    long_col = next((c for c in df.columns if "long" in c and "contracts" in c), None)
    short_col = next((c for c in df.columns if "short" in c and "contracts" in c), None)
    if not name_col or not long_col or not short_col:
        return base

    for _, row in df.iterrows():
        name = str(row.get(name_col, "")).upper()
        key = "FII" if "FII" in name or "FPI" in name else "DII" if "DII" in name else "Client" if "CLIENT" in name else None
        if not key:
            continue
        long_val = pd.to_numeric(row.get(long_col), errors="coerce")
        short_val = pd.to_numeric(row.get(short_col), errors="coerce")
        if pd.notna(long_val):
            base[key]["long"] = int(long_val)
        if pd.notna(short_val):
            base[key]["short"] = int(short_val)
        if pd.notna(long_val) and pd.notna(short_val):
            base[key]["net"] = int(long_val - short_val)
    return base


@router.post("/analyze")
async def fno_analyze(req: FnORequest):
    """Return live option-chain-derived F&O metrics without demo constants."""
    logger.info("api.fno.analyze", symbol=req.symbol)
    try:
        yf_client = YFinanceClient()
        nsefin = NSEFinClient()
        nselib = NSELibClient()

        symbol_clean = req.symbol.replace(".NS", "").replace(".BO", "")
        spot_symbol = INDEX_SPOT_MAP.get(symbol_clean, req.symbol if "." in req.symbol else f"{symbol_clean}.NS")
        spot_df, chain_df, participant_oi = await asyncio.gather(
            yf_client.get_ohlcv(spot_symbol, period="5d"),
            nsefin.get_option_chain(symbol_clean),
            nselib.get_participant_oi(),
            return_exceptions=True,
        )

        if isinstance(chain_df, Exception):
            raise chain_df
        if chain_df.empty:
            raise ValueError("empty option chain")

        if isinstance(spot_df, Exception) or spot_df is None or spot_df.empty:
            raise ValueError("spot price unavailable")

        spot = float(spot_df["close"].iloc[-1])
        report = build_fno_report(chain_df, spot=spot)
        atm_iv = _extract_atm_iv(chain_df, spot)

        return {
            "symbol": req.symbol,
            "expiry": report.get("expiry", req.expiry or ""),
            "pcr": round(report.get("pcr_oi", 0.0) or 0.0, 4),
            "pcr_signal": report.get("pcr_signal", "UNKNOWN"),
            "max_pain": report.get("max_pain_strike"),
            "iv_rank_pct": report.get("iv_rank"),
            "iv_percentile": report.get("iv_percentile"),
            "atm_iv": round(atm_iv, 4) if atm_iv is not None else None,
            "skew": report.get("iv_signal"),
            "fii_futures_net": "UNKNOWN",
            "participant_oi": _participant_oi_to_dict(None if isinstance(participant_oi, Exception) else participant_oi),
            "strategy_recommendation": (
                f"Support={report.get('support_strike')} | Resistance={report.get('resistance_strike')} | "
                f"OI={report.get('oi_buildup')}"
            ),
            "greeks_atm": {},
            "source": "live_fno_engine",
        }
    except MarketClosedError as exc:
        logger.warning("api.fno.market_closed", symbol=req.symbol, error=str(exc))
        return {
            "symbol": req.symbol,
            "expiry": req.expiry or "",
            "pcr": None,
            "pcr_signal": "MARKET_CLOSED",
            "max_pain": None,
            "iv_rank_pct": None,
            "iv_percentile": None,
            "atm_iv": None,
            "skew": None,
            "fii_futures_net": "UNKNOWN",
            "participant_oi": _participant_oi_to_dict(None),
            "strategy_recommendation": "Option chain unavailable outside live NSE option-chain hours.",
            "greeks_atm": {},
            "source": "market_closed",
        }
    except Exception as exc:
        logger.error("api.fno.error", symbol=req.symbol, error=str(exc))
        return {
            "symbol": req.symbol,
            "expiry": req.expiry or "",
            "pcr": None,
            "pcr_signal": "UNAVAILABLE",
            "max_pain": None,
            "iv_rank_pct": None,
            "iv_percentile": None,
            "atm_iv": None,
            "skew": None,
            "fii_futures_net": "UNKNOWN",
            "participant_oi": _participant_oi_to_dict(None),
            "strategy_recommendation": f"Live F&O data unavailable: {str(exc)[:120]}",
            "greeks_atm": {},
            "source": "unavailable",
        }
