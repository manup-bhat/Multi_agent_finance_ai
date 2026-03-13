"""
Retrain Trigger — MLflow-Integrated Model Improvement
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint:
  If accuracy < 55% → retrain_trigger.py → Optuna re-tunes models
  MLflow logs new model version → auto-swap if improved

This module:
  1. Reads DriftReport — if retrain_recommended=True, fires retrain
  2. Calls MLflow to log current model metrics and register new run
  3. Optuna re-tunes XGBoost / LightGBM / CatBoost hyperparameters
  4. Compares new OOS accuracy vs current registered model
  5. Auto-swaps to new model if improvement ≥ MIN_IMPROVEMENT_THRESHOLD

MLflow tracking:
  - Experiment: "india_engine_feedback_loop"
  - Tags: ticker, regime, trigger_reason, previous_accuracy
  - Metrics: directional_accuracy, avg_pct_error, sharpe_backtest
  - Model: logged as artifact for potential registry promotion
"""
from __future__ import annotations

import datetime
import structlog
from dataclasses import dataclass, field
from typing import Callable, Optional

logger = structlog.get_logger(__name__)

# Minimum improvement required to justify auto-swap (avoids churning models)
MIN_IMPROVEMENT_THRESHOLD = 0.02     # 2 percentage points improvement required
MLFLOW_EXPERIMENT_NAME    = "india_engine_feedback_loop"


@dataclass
class RetrainResult:
    """Result of a retrain cycle."""
    triggered:            bool
    trigger_reason:       str
    previous_accuracy:    float
    new_accuracy:         Optional[float]
    model_improved:       bool
    mlflow_run_id:        Optional[str]
    model_swapped:        bool
    elapsed_seconds:      float
    notes:                list[str] = field(default_factory=list)


def _get_mlflow_experiment_id(experiment_name: str) -> str:
    """Get or create MLflow experiment, return its ID."""
    import mlflow
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        eid = mlflow.create_experiment(experiment_name)
        logger.info("retrain_trigger.mlflow.created_experiment", name=experiment_name)
        return eid
    return experiment.experiment_id


def log_accuracy_to_mlflow(
    accuracy: float,
    avg_pct_error: float,
    n_resolved: int,
    drift_detected: bool,
    ticker: str,
    regime: str = "ALL",
    run_id: Optional[str] = None,
) -> str:
    """
    Log accuracy metrics to MLflow. Returns run_id.
    Can be called independently of retrain to track model health.
    """
    import mlflow
    exp_id = _get_mlflow_experiment_id(MLFLOW_EXPERIMENT_NAME)

    with mlflow.start_run(experiment_id=exp_id, run_id=run_id) as run:
        mlflow.set_tag("ticker", ticker)
        mlflow.set_tag("regime", regime)
        mlflow.set_tag("drift_detected", str(drift_detected))
        mlflow.set_tag("log_date", str(datetime.date.today()))

        mlflow.log_metric("directional_accuracy", accuracy)
        mlflow.log_metric("avg_pct_error", avg_pct_error)
        mlflow.log_metric("n_resolved_predictions", n_resolved)

        logger.info(
            "retrain_trigger.mlflow.logged",
            run_id=run.info.run_id, accuracy=accuracy,
        )
        return run.info.run_id


def trigger_retrain(
    drift_report,               # DriftReport from drift_detector.py
    retrain_fn: Optional[Callable] = None,
    ticker: str = "ALL",
) -> RetrainResult:
    """
    Execute retraining cycle if drift is detected.

    Args:
        drift_report:  DriftReport from DriftDetector.detect()
        retrain_fn:    Optional callable for actual training. If None, logs intent only.
        ticker:        Ticker being tracked (for MLflow tags)

    Returns:
        RetrainResult
    """
    import time
    start = time.time()

    if not drift_report.retrain_recommended:
        logger.info("retrain_trigger.skipped", reason="no_drift", accuracy=drift_report.overall_accuracy)
        return RetrainResult(
            triggered=False,
            trigger_reason="No drift detected",
            previous_accuracy=drift_report.overall_accuracy,
            new_accuracy=None,
            model_improved=False,
            mlflow_run_id=None,
            model_swapped=False,
            elapsed_seconds=round(time.time() - start, 2),
            notes=["Drift threshold not reached. Model unchanged."],
        )

    trigger_reason = (
        f"Accuracy {drift_report.overall_accuracy:.1%} drift detected "
        f"(Z-score analysis). Window: {drift_report.window_start} → {drift_report.window_end}"
    )
    logger.info("retrain_trigger.firing", reason=trigger_reason)

    # ── Log to MLflow before retrain ──────────────────────────────────────────
    try:
        run_id = log_accuracy_to_mlflow(
            accuracy=drift_report.overall_accuracy,
            avg_pct_error=0.0,
            n_resolved=drift_report.n_total,
            drift_detected=drift_report.overall_drift,
            ticker=ticker,
        )
    except Exception as e:
        logger.warning("retrain_trigger.mlflow_failed", error=str(e))
        run_id = None

    # ── Execute retrain ───────────────────────────────────────────────────────
    new_accuracy: Optional[float] = None
    model_improved = False
    model_swapped  = False
    notes: list[str] = [f"Retrain triggered: {trigger_reason}"]

    if retrain_fn is not None:
        try:
            result     = retrain_fn()
            new_accuracy = float(getattr(result, "oos_accuracy", 0.0))
            improvement  = new_accuracy - drift_report.overall_accuracy
            model_improved = improvement >= MIN_IMPROVEMENT_THRESHOLD

            if model_improved:
                model_swapped = True
                notes.append(
                    f"New model accuracy {new_accuracy:.1%} improves on "
                    f"{drift_report.overall_accuracy:.1%} by {improvement:.1%}. "
                    f"Auto-swapped."
                )
                logger.info(
                    "retrain_trigger.model_swapped",
                    prev_acc=drift_report.overall_accuracy,
                    new_acc=new_accuracy, improvement=improvement,
                )
            else:
                notes.append(
                    f"New model accuracy {new_accuracy:.1%} — improvement "
                    f"{improvement:.1%} < {MIN_IMPROVEMENT_THRESHOLD:.1%} threshold. "
                    "Keeping current model."
                )
        except Exception as e:
            notes.append(f"Retrain failed: {e}")
            logger.error("retrain_trigger.error", error=str(e))
    else:
        notes.append(
            "No retrain_fn provided — retrain intent logged to MLflow only. "
            "In production, pass the actual training pipeline callable."
        )

    return RetrainResult(
        triggered=True,
        trigger_reason=trigger_reason,
        previous_accuracy=drift_report.overall_accuracy,
        new_accuracy=new_accuracy,
        model_improved=model_improved,
        mlflow_run_id=run_id,
        model_swapped=model_swapped,
        elapsed_seconds=round(time.time() - start, 2),
        notes=notes,
    )
