"""
Feedback Loop Scheduler — APScheduler Cron Jobs
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint:
  APScheduler: daily accuracy check, weekly drift detection, monthly retrain

Schedule (IST):
  - 18:30 daily    → accuracy_tracker.run() — resolve T+N outcomes
  - 18:45 daily    → drift_detector.detect() — check rolling accuracy
  - 19:00 daily    → if drift detected → retrain_trigger.trigger_retrain()
  - 09:00 Monday   → weekly summary log to MLflow

Uses APScheduler BackgroundScheduler with AsyncIO job execution.
All times in IST (Asia/Kolkata = UTC+5:30).
"""
from __future__ import annotations

import datetime
import structlog
from typing import Optional

logger = structlog.get_logger(__name__)

# Schedule timings (IST expressed as hour, minute in Asia/Kolkata)
ACCURACY_TRACKER_HOUR   = 18
ACCURACY_TRACKER_MINUTE = 30
DRIFT_CHECKER_HOUR      = 18
DRIFT_CHECKER_MINUTE    = 45
RETRAIN_TRIGGER_HOUR    = 19
RETRAIN_TRIGGER_MINUTE  = 0
WEEKLY_SUMMARY_DAY      = "mon"
WEEKLY_SUMMARY_HOUR     = 9


def _run_daily_accuracy(
    prediction_logger,
    retrain_fn=None,
) -> None:
    """
    APScheduler job: full daily feedback cycle.
    1. Resolve pending T+N outcomes
    2. Compute rolling 30-day accuracy
    3. Check for drift
    4. Trigger retrain if needed
    5. Log everything to MLflow
    """
    from feedback.accuracy_tracker import AccuracyTracker
    from feedback.drift_detector import DriftDetector
    from feedback.retrain_trigger import trigger_retrain, log_accuracy_to_mlflow

    today = datetime.date.today()
    logger.info("scheduler.daily_cycle.start", date=str(today))

    # Step 1 + 2: resolve + accuracy
    tracker = AccuracyTracker(prediction_logger)
    summary = tracker.run(as_of_date=today)

    # Step 3: drift detection
    detector = DriftDetector(prediction_logger)
    report   = detector.detect(window_days=30)

    # Step 4: retrain if recommended
    retrain_result = trigger_retrain(report, retrain_fn=retrain_fn)

    # Step 5: MLflow logging
    try:
        log_accuracy_to_mlflow(
            accuracy=summary.directional_accuracy,
            avg_pct_error=summary.avg_pct_error,
            n_resolved=summary.n_resolved,
            drift_detected=report.overall_drift,
            ticker=summary.ticker,
        )
    except Exception as e:
        logger.warning("scheduler.mlflow_log_failed", error=str(e))

    logger.info(
        "scheduler.daily_cycle.done",
        accuracy=summary.directional_accuracy,
        drift=report.overall_drift,
        retrain_triggered=retrain_result.triggered,
        model_swapped=retrain_result.model_swapped,
    )


def build_scheduler(
    prediction_logger,
    retrain_fn=None,
    timezone: str = "Asia/Kolkata",
) -> "APScheduler.BackgroundScheduler":
    """
    Build and return a configured APScheduler BackgroundScheduler.

    Args:
        prediction_logger: PredictionLogger instance
        retrain_fn:        Optional retrain callable (passed to trigger_retrain)
        timezone:          Scheduler timezone (default IST)

    Returns:
        Configured apscheduler.schedulers.background.BackgroundScheduler
    """
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(timezone=timezone)

    # Daily accuracy + drift + retrain job (18:30 IST)
    scheduler.add_job(
        func=_run_daily_accuracy,
        trigger="cron",
        hour=ACCURACY_TRACKER_HOUR,
        minute=ACCURACY_TRACKER_MINUTE,
        kwargs={
            "prediction_logger": prediction_logger,
            "retrain_fn": retrain_fn,
        },
        id="daily_feedback_cycle",
        name="Daily Accuracy + Drift + Retrain",
        replace_existing=True,
    )

    logger.info(
        "scheduler.built",
        jobs=len(scheduler.get_jobs()),
        timezone=timezone,
    )
    return scheduler


def start_scheduler(
    prediction_logger,
    retrain_fn=None,
    timezone: str = "Asia/Kolkata",
) -> "APScheduler.BackgroundScheduler":
    """
    Build and start the scheduler. Call this from the FastAPI startup event.

    Returns:
        Running BackgroundScheduler instance (call .shutdown() on app teardown)
    """
    scheduler = build_scheduler(prediction_logger, retrain_fn, timezone)
    scheduler.start()
    logger.info("scheduler.started")
    return scheduler
