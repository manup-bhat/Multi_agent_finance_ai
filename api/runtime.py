"""
Best-effort startup preloading for the API runtime.
"""
from __future__ import annotations

import asyncio
from functools import partial
from pathlib import Path

import structlog

from config.settings import get_settings
from prediction.inference.prediction_service import preload_prediction_services
from sentiment.composite_sentiment import get_composite_sentiment
from sentiment.finbert_analyzer import get_finbert_analyzer
from sentiment.finbert_india_analyzer import get_finbert_india_analyzer
from sentiment.finbert_tone_analyzer import get_finbert_tone_analyzer
from sentiment.goemotions_analyzer import get_goemotions_analyzer

logger = structlog.get_logger(__name__)


async def _preload_sentiment_models() -> None:
    engines = [
        get_finbert_analyzer(),
        get_finbert_india_analyzer(),
        get_finbert_tone_analyzer(),
        get_goemotions_analyzer(),
    ]
    get_composite_sentiment()

    for engine in engines:
        if not hasattr(engine, "_ensure_loaded"):
            continue
        try:
            await engine._ensure_loaded()  # type: ignore[attr-defined]
        except Exception as exc:
            logger.warning(
                "api.runtime.sentiment_prewarm_failed",
                engine=engine.__class__.__name__,
                error=str(exc),
            )


async def warm_app_runtime() -> None:
    settings = get_settings()
    tasks: list[asyncio.Future | asyncio.Task] = []
    loop = asyncio.get_event_loop()

    if settings.startup_preload_models:
        tasks.append(
            loop.run_in_executor(
                None,
                partial(
                    preload_prediction_services,
                    model_root=Path("models/saved"),
                    include_chronos=True,
                ),
            )
        )
    if settings.startup_preload_sentiment_models:
        tasks.append(asyncio.create_task(_preload_sentiment_models()))

    if not tasks:
        return

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, Exception):
            logger.warning("api.runtime.prewarm_failed", error=str(result))
        elif isinstance(result, list):
            logger.info("api.runtime.prediction_services_warmed", services=result)
