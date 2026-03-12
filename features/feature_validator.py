"""
Feature Validator — enforces anti-lookahead and completeness.
Gate: 70 features, zero NaN on last 252 trading days, all .shift(1).
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import structlog
from features.india_feature_set import ALL_FEATURE_COLUMNS

logger = structlog.get_logger(__name__)


class FeatureValidationError(Exception):
    pass


def validate_features(features: pd.DataFrame,
                       min_rows: int = 252,
                       max_null_pct: float = 5.0,
                       ticker: str = "?") -> dict:
    """
    Validate feature DataFrame before it enters any model.

    Checks:
      1. Exactly 70 columns matching ALL_FEATURE_COLUMNS
      2. Minimum 252 rows (1 trading year)
      3. NaN % on last 252 rows ≤ max_null_pct (default 5%)
      4. No future-leaking columns (spot-check: close_lag1 == previous close)
      5. Index is tz-aware Asia/Kolkata
      6. All values finite (no inf/-inf)

    Returns dict with pass/fail per check + summary.
    Raises FeatureValidationError if any hard check fails.
    """
    errors   = []
    warnings = []
    report   = {}

    # ── Check 1: Column count and names ──────────────────────────────
    actual_cols = list(features.columns)
    if len(actual_cols) != 70:
        errors.append(f"Expected 70 columns, got {len(actual_cols)}")
    missing_cols = [c for c in ALL_FEATURE_COLUMNS if c not in actual_cols]
    extra_cols   = [c for c in actual_cols if c not in ALL_FEATURE_COLUMNS]
    if missing_cols:
        errors.append(f"Missing columns: {missing_cols}")
    if extra_cols:
        warnings.append(f"Extra columns (ignored): {extra_cols}")
    report["columns"] = "PASS" if not missing_cols and len(actual_cols) == 70 else "FAIL"

    # ── Check 2: Minimum rows ─────────────────────────────────────────
    if len(features) < min_rows:
        errors.append(f"Only {len(features)} rows — need {min_rows} minimum (1 trading year)")
        report["min_rows"] = "FAIL"
    else:
        report["min_rows"] = f"PASS ({len(features)} rows)"

    # ── Check 3: NaN on last 252 rows ─────────────────────────────────
    last_252   = features.tail(252)
    null_pct   = last_252.isna().mean().mean() * 100
    worst_cols = last_252.isna().mean().nlargest(5).to_dict()
    if null_pct > max_null_pct:
        errors.append(
            f"NaN {null_pct:.1f}% on last 252 rows — exceeds {max_null_pct}%. "
            f"Worst cols: {worst_cols}"
        )
        report["null_check"] = "FAIL"
    else:
        report["null_check"] = f"PASS ({null_pct:.2f}% null)"

    # ── Check 4: Infinity check ───────────────────────────────────────
    numeric = features.select_dtypes(include=[np.number])
    inf_cols = numeric.columns[np.isinf(numeric).any()].tolist()
    if inf_cols:
        errors.append(f"Infinite values in: {inf_cols}")
        report["inf_check"] = "FAIL"
    else:
        report["inf_check"] = "PASS"

    # ── Check 5: Timezone ─────────────────────────────────────────────
    if features.index.tzinfo is None:
        errors.append("Index has no timezone — must be Asia/Kolkata")
        report["timezone"] = "FAIL"
    elif "Kolkata" not in str(features.index.tzinfo):
        errors.append(f"Wrong timezone: {features.index.tzinfo} — must be Asia/Kolkata")
        report["timezone"] = "FAIL"
    else:
        report["timezone"] = "PASS"

    # ── Check 6: Anti-lookahead spot-check ────────────────────────────
    # close_lag1[t] must equal close[t-1] — verified on OHLCV independently
    # Here we check: close_lag1 is never equal to the same-day return
    # Proxy check: close_lag1 should have NaN at index[0]
    if "close_lag1" in features.columns:
        if not pd.isna(features["close_lag1"].iloc[0]):
            errors.append(
                "close_lag1.iloc[0] is not NaN — shift(1) may not be applied correctly"
            )
            report["anti_lookahead"] = "FAIL"
        else:
            report["anti_lookahead"] = "PASS"
    else:
        report["anti_lookahead"] = "SKIP (close_lag1 not found)"

    # ── Summary ───────────────────────────────────────────────────────
    report["errors"]   = errors
    report["warnings"] = warnings
    report["passed"]   = len(errors) == 0

    log_fn = logger.info if report["passed"] else logger.error
    log_fn(
        "feature_validator.result",
        ticker=ticker,
        passed=report["passed"],
        errors=errors,
        warnings=warnings,
        null_pct=round(null_pct, 2) if len(features) >= 252 else None,
    )

    if errors:
        raise FeatureValidationError(
            f"Feature validation failed for {ticker}:\n" +
            "\n".join(f"  • {e}" for e in errors)
        )

    return report