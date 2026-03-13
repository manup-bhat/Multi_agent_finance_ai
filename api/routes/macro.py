"""GET /macro/india-cues — India macro indicators."""
from fastapi import APIRouter
from api.schemas import MacroResponse
import structlog

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/india-cues", response_model=MacroResponse)
async def india_cues():
    """Return consolidated India macro indicators."""
    logger.info("api.macro.india_cues")
    try:
        import yfinance as yf
        import pandas as pd
        vix_data  = yf.download("^INDIAVIX", period="1d", progress=False, auto_adjust=True)
        inr_data  = yf.download("USDINR=X",  period="1d", progress=False, auto_adjust=True)
        brent_data= yf.download("BZ=F",      period="1d", progress=False, auto_adjust=True)
        
        for d in (vix_data, inr_data, brent_data):
            if isinstance(d.columns, pd.MultiIndex):
                d.columns = d.columns.get_level_values(0)

        vix   = float(vix_data["Close"].iloc[-1])  if not vix_data.empty  else None
        usdinr= float(inr_data["Close"].iloc[-1])  if not inr_data.empty  else None
        brent = float(brent_data["Close"].iloc[-1])if not brent_data.empty else None

        from config.constants import VIX_CIRCUIT_BREAKER, VIX_ELEVATED_MAX, VIX_NORMAL_MAX
        if vix is None:            vix_regime = "UNKNOWN"
        elif vix >= VIX_CIRCUIT_BREAKER: vix_regime = "EXTREME"
        elif vix >= VIX_ELEVATED_MAX:    vix_regime = "ELEVATED"
        elif vix >= VIX_NORMAL_MAX:      vix_regime = "NORMAL"
        else:                            vix_regime = "COMPLACENCY"

        return MacroResponse(
            vix=round(vix, 2) if vix else None,
            vix_regime=vix_regime,
            usdinr=round(usdinr, 4) if usdinr else None,
            brent_crude=round(brent, 2) if brent else None,
            fii_net_crore=None,
            fii_trend="NEUTRAL",
            sgx_nifty=None,
            global_cues="Data fetched via yfinance",
            india_summary=(
                f"VIX={vix:.1f} ({vix_regime}), USDINR={usdinr:.2f}, Brent=${brent:.1f}/bbl"
                if vix and usdinr and brent else "Live macro data (partial)"
            ),
        )
    except Exception as e:
        logger.warning("api.macro.fallback", error=str(e))
        return MacroResponse(
            vix=None, vix_regime="UNKNOWN", usdinr=None, brent_crude=None,
            fii_net_crore=None, fii_trend="UNKNOWN",
            sgx_nifty=None, global_cues="Error fetching live data",
            india_summary="Live macro data unavailable. Check network or APIs.",
        )
