"""Health check endpoint."""
from fastapi import APIRouter
from api.schemas import HealthResponse

router = APIRouter()

@router.get("/health", response_model=HealthResponse)
async def health():
    """Service health check — verifies all key modules importable."""
    modules: dict[str, str] = {}
    checks = {
        "backtesting": "backtesting",
        "compliance":  "compliance",
        "feedback":    "feedback",
        "config":      "config.constants",
    }
    for name, mod in checks.items():
        try:
            __import__(mod)
            modules[name] = "ok"
        except Exception as e:
            modules[name] = f"error: {e}"

    overall = "healthy" if all(v == "ok" for v in modules.values()) else "degraded"
    return HealthResponse(status=overall, version="12.0.0", modules=modules)
