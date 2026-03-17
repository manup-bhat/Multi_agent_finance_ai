"""
Workflow validation node for orchestrator safety.

Ensures the orchestrator does not synthesize a confident report from missing
agent outputs. When inputs are incomplete, the graph degrades to HOLD with a
deterministic report instead of calling the final LLM.
"""
from __future__ import annotations

import structlog

from agents.state import IndiaEngineState, validate_state_payload

logger = structlog.get_logger(__name__)

REQUIRED_ANALYSIS_KEYS = (
    "quant_analysis",
    "macro_analysis",
    "fundamental_analysis",
    "prediction_analysis",
    "emotion_analysis",
    "fno_analysis",
)


def run_validation_node(state: IndiaEngineState) -> dict:
    """
    Validate orchestrator prerequisites after DA and risk evaluation.

    Missing analyses are surfaced explicitly in state instead of letting the
    orchestrator infer over empty strings.
    """
    try:
        normalized_state = validate_state_payload(dict(state))
    except Exception as exc:
        logger.warning("validation_node.state_invalid", error=str(exc))
        errors = list(state.get("errors", []))
        errors.append(f"STATE_VALIDATION: {exc}")
        validation = {
            "ready": False,
            "missing_keys": [],
            "checked_keys": list(REQUIRED_ANALYSIS_KEYS) + ["devils_advocate_analysis"],
            "blocking_errors": [f"STATE_VALIDATION: {exc}"],
        }
        return {
            "workflow_validation": validation,
            "errors": errors,
            "warnings": list(state.get("warnings", [])),
            "confidence": 0.0,
            "verdict": "HOLD",
        }

    missing = [
        key for key in REQUIRED_ANALYSIS_KEYS
        if not str(normalized_state.get(key, "") or "").strip()
    ]
    missing_da = not str(normalized_state.get("devils_advocate_analysis", "") or "").strip()
    if missing_da:
        missing.append("devils_advocate_analysis")

    blocking_errors = [str(err) for err in normalized_state.get("errors", []) if str(err).strip()]
    ready = not missing and not blocking_errors
    validation = {
        "ready": ready,
        "missing_keys": missing,
        "checked_keys": list(REQUIRED_ANALYSIS_KEYS) + ["devils_advocate_analysis"],
        "blocking_errors": blocking_errors,
    }

    if ready:
        logger.info("validation_node.ready")
        return {"workflow_validation": validation}

    warning = (
        "Workflow validation blocked final orchestration because required "
        f"agent outputs were missing: {', '.join(missing) if missing else 'none'}."
    )
    if blocking_errors:
        warning += f" Blocking errors: {' | '.join(blocking_errors)}."
    errors = list(state.get("errors", []))
    warnings = list(state.get("warnings", []))
    errors.append(f"WORKFLOW_VALIDATION: {warning}")
    warnings.append(warning)

    logger.warning("validation_node.blocked", missing_keys=missing)
    return {
        "workflow_validation": validation,
        "errors": errors,
        "warnings": warnings,
        "confidence": 0.0,
        "verdict": "HOLD",
    }
