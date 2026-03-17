"""GET /fii-dii/latest — latest real FII/DII flow data."""
from __future__ import annotations

from fastapi import APIRouter
import structlog

from api.schemas import FIIDIIResponse
from data.adapters.nselib_client import NSELibClient
from macro.fii_dii_tracker import build_flow_report

logger = structlog.get_logger(__name__)
router = APIRouter()


@router.get("/latest", response_model=FIIDIIResponse)
async def fii_dii_latest() -> FIIDIIResponse:
    """Return the latest FII/DII flow snapshot without fabricated values."""
    logger.info("api.fii_dii.latest")
    try:
        df = await NSELibClient().get_fii_dii()
        if df.empty:
            raise ValueError("FII/DII dataset is empty")

        report = build_flow_report(df)
        latest_dt = df.index[-1]
        fii_trend = "BUYING" if report.latest_fii_net > 0 else "SELLING" if report.latest_fii_net < 0 else "NEUTRAL"

        return FIIDIIResponse(
            date=latest_dt.date().isoformat() if hasattr(latest_dt, "date") else str(latest_dt),
            fii_net_crore=report.latest_fii_net,
            dii_net_crore=report.latest_dii_net,
            fii_trend=fii_trend,
            fii_streak_days=report.sell_streak_days,
            consensus=report.consensus,
        )
    except Exception as exc:
        logger.warning("api.fii_dii.unavailable", error=str(exc))
        return FIIDIIResponse(
            date="",
            fii_net_crore=None,
            dii_net_crore=None,
            fii_trend="UNKNOWN",
            fii_streak_days=0,
            consensus="UNKNOWN",
        )
