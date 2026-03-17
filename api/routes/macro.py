"""GET /macro/india-cues — India macro indicators."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter
import structlog

from api.schemas import MacroResponse
from api.routes.fii_dii import fii_dii_latest
from config.constants import VIX_CIRCUIT_BREAKER, VIX_ELEVATED_MAX, VIX_NORMAL_MAX
from data.adapters.yfinance_client import YFinanceClient

logger = structlog.get_logger(__name__)
router = APIRouter()


def _classify_vix_regime(vix: float | None) -> str:
    if vix is None:
        return "UNKNOWN"
    if vix >= VIX_CIRCUIT_BREAKER:
        return "EXTREME"
    if vix >= VIX_ELEVATED_MAX:
        return "ELEVATED"
    if vix >= VIX_NORMAL_MAX:
        return "NORMAL"
    return "COMPLACENCY"


@router.get("/india-cues", response_model=MacroResponse)
async def india_cues() -> MacroResponse:
    """Return consolidated live India macro indicators."""
    logger.info("api.macro.india_cues")
    try:
        yf = YFinanceClient()
        macro_df, fii = await asyncio.gather(
            yf.get_macro_snapshot(period="6mo"),
            fii_dii_latest(),
        )

        if macro_df.empty:
            raise ValueError("macro snapshot is empty")

        latest = macro_df.ffill().iloc[-1]
        vix = float(latest.get("india_vix")) if "india_vix" in latest and latest.get("india_vix") is not None else None
        usdinr = float(latest.get("usdinr")) if "usdinr" in latest and latest.get("usdinr") is not None else None
        brent = float(latest.get("brent_crude")) if "brent_crude" in latest and latest.get("brent_crude") is not None else None
        banknifty = float(latest.get("banknifty")) if "banknifty" in latest and latest.get("banknifty") is not None else None
        nifty50 = float(latest.get("nifty50")) if "nifty50" in latest and latest.get("nifty50") is not None else None
        sgx_proxy = round(banknifty / nifty50, 4) if banknifty and nifty50 else None
        vix_regime = _classify_vix_regime(vix)

        return MacroResponse(
            vix=round(vix, 2) if vix is not None else None,
            vix_regime=vix_regime,
            usdinr=round(usdinr, 4) if usdinr is not None else None,
            brent_crude=round(brent, 2) if brent is not None else None,
            fii_net_crore=fii.fii_net_crore,
            fii_trend=fii.fii_trend,
            sgx_nifty=sgx_proxy,
            global_cues="live_yfinance_snapshot",
            india_summary=(
                f"VIX={vix:.2f} ({vix_regime}), USDINR={usdinr:.2f}, Brent=${brent:.2f}/bbl, "
                f"FII={fii.fii_trend}"
                if vix is not None and usdinr is not None and brent is not None
                else "Live macro data available partially."
            ),
        )
    except Exception as exc:
        logger.warning("api.macro.unavailable", error=str(exc))
        return MacroResponse(
            vix=None,
            vix_regime="UNKNOWN",
            usdinr=None,
            brent_crude=None,
            fii_net_crore=None,
            fii_trend="UNKNOWN",
            sgx_nifty=None,
            global_cues="unavailable",
            india_summary="Live macro data unavailable.",
        )
