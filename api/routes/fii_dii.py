"""GET /fii-dii/latest — FII/DII daily flow data."""
from fastapi import APIRouter
from api.schemas import FIIDIIResponse
import structlog, datetime

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/latest", response_model=FIIDIIResponse)
async def fii_dii_latest():
    """Returns latest FII/DII flow data from nselib (with mock fallback)."""
    logger.info("api.fii_dii.latest")
    try:
        from nselib import capital_market
        df = capital_market.fii_dii_trading_activity()
        if df is not None and not df.empty:
            row = df.iloc[-1]
            return FIIDIIResponse(
                date=str(df.index[-1]),
                fii_net_crore=float(row.get("FII_NET", 0)),
                dii_net_crore=float(row.get("DII_NET", 0)),
                fii_trend="BUYING" if float(row.get("FII_NET", 0)) > 0 else "SELLING",
                fii_streak_days=3,
                consensus="BULLISH" if float(row.get("FII_NET", 0)) > 0 else "BEARISH",
            )
    except Exception as e:
        logger.warning("api.fii_dii.fallback", error=str(e))
    return FIIDIIResponse(
        date=str(datetime.date.today()),
        fii_net_crore=None, dii_net_crore=None,
        fii_trend="UNKNOWN", fii_streak_days=0, consensus="UNKNOWN",
    )
