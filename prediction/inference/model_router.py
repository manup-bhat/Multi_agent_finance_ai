"""
Model Router
━━━━━━━━━━━
Routes TSFM selection: Chronos-2 vs TimesFM vs Chronos-Bolt
based on task type, data availability, and regime.

Blueprint routing rules:
  - Zero-shot, covariate-rich → Chronos-2 (base)
  - Fine-tuned, VaR task      → TimesFM (when available)
  - Live dashboard refresh    → Chronos-Bolt (250x faster)
  - Crisis regime (VIX>30)    → Chronos-Bolt only (fast exit signal)

HARD RULE: Routing logic is deterministic Python. LLMs never decide which model to use.
"""
from __future__ import annotations

from enum import Enum
import structlog

from config.constants import VIX_CIRCUIT_BREAKER, VIX_CRISIS_THRESHOLD

logger = structlog.get_logger(__name__)


class TSFMRoute(str, Enum):
    CHRONOS2      = "chronos2"       # Full Chronos-2 (base/small) — accuracy
    CHRONOS_BOLT  = "chronos_bolt"   # Chronos-Bolt — speed (dashboard refresh)
    TIMESFM       = "timesfm"        # TimesFM — fine-tuned VaR tasks
    FALLBACK_STAT = "fallback_stat"  # Statistical fallback (ARIMA stub)


class TaskType(str, Enum):
    DIRECTIONAL_FORECAST  = "directional"    # 5-class direction prediction
    PRICE_PATH_FORECAST   = "price_path"     # Full probabilistic path
    VAR_ESTIMATION        = "var"            # Value-at-Risk estimation
    DASHBOARD_REFRESH     = "dashboard"      # Fast live refresh (< 2s budget)
    SCENARIO_SIMULATION   = "scenario"       # Monte Carlo paths


class ModelRouter:
    """
    Stateless routing engine.
    All decisions based on task type + VIX + TimesFM availability.
    """

    def __init__(self, timesfm_available: bool = False):
        """
        Args:
            timesfm_available: Set True if TimesFM is installed and fine-tuned
                               (timesfm 1.3.0 PyPI only; fine-tuning is optional)
        """
        self.timesfm_available = timesfm_available

    def route(
        self,
        task:        TaskType,
        vix_level:   float,
        regime_id:   int,
        n_data_rows: int,
    ) -> TSFMRoute:
        """
        Select the appropriate TSFM for this prediction task.

        Args:
            task:        What kind of forecast is needed
            vix_level:   Current India VIX
            regime_id:   HMM regime {0=Bear, 1=Sideways, 2=Bull}
            n_data_rows: Available historical rows for context

        Returns:
            TSFMRoute enum value
        """
        # ── Crisis → fastest model only ───────────────────────────────────────
        if vix_level >= VIX_CRISIS_THRESHOLD:
            logger.info("model_router.crisis_bolt", vix=vix_level)
            return TSFMRoute.CHRONOS_BOLT

        # ── Dashboard refresh → Bolt always ───────────────────────────────────
        if task == TaskType.DASHBOARD_REFRESH:
            return TSFMRoute.CHRONOS_BOLT

        # ── VaR estimation → TimesFM (if available and fine-tuned) ───────────
        if task == TaskType.VAR_ESTIMATION and self.timesfm_available:
            logger.info("model_router.timesfm_var")
            return TSFMRoute.TIMESFM

        # ── Insufficient data → Bolt (shorter context, faster) ────────────────
        if n_data_rows < 100:
            logger.warning("model_router.insufficient_data_bolt", n_rows=n_data_rows)
            return TSFMRoute.CHRONOS_BOLT

        # ── Default: full Chronos-2 with covariates ────────────────────────────
        logger.debug("model_router.chronos2", task=task, vix=vix_level, regime=regime_id)
        return TSFMRoute.CHRONOS2

    def get_model_description(self, route: TSFMRoute) -> str:
        """Human-readable description of routed model for Phoenix audit."""
        descriptions = {
            TSFMRoute.CHRONOS2:     "Amazon Chronos-2 (base, 200M params) — multivariate with 8 India covariates",
            TSFMRoute.CHRONOS_BOLT: "Amazon Chronos-Bolt (base) — fast inference, 250x speed vs Chronos-2",
            TSFMRoute.TIMESFM:      "Google TimesFM v1.3.0 (200M params) — fine-tuned on Indian equities",
            TSFMRoute.FALLBACK_STAT:"Statistical fallback — ARIMA stub (Chronos unavailable)",
        }
        return descriptions.get(route, "Unknown model")