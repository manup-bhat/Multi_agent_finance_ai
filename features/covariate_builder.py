"""
Chronos-2 covariate builder.
Extracts the 8 India covariates from the full 70-feature set
and formats them for GluonTS / Chronos-2 multivariate input.
"""
from __future__ import annotations
import numpy as np
import pandas as pd
import structlog
from features.india_feature_set import CHRONOS_COVARIATES

logger = structlog.get_logger(__name__)


def build_chronos_covariates(features: pd.DataFrame,
                              target_series: pd.Series) -> dict:
    """
    Build Chronos-2 multivariate input dict.

    Returns:
        {
          "target": pd.Series,           # price series (unshifted — Chronos sees history)
          "past_dynamic_real": np.ndarray,  # shape (T, 8) — lagged covariates
          "feat_names": list[str],        # for logging / debugging
        }
    """
    missing = [c for c in CHRONOS_COVARIATES if c not in features.columns]
    if missing:
        raise ValueError(f"Missing Chronos covariates: {missing}")

    cov_df = features[CHRONOS_COVARIATES].copy()

    # Forward-fill then backfill any gaps
    cov_df = cov_df.ffill().bfill()

    # Replace remaining NaN with column median
    for col in cov_df.columns:
        median = cov_df[col].median()
        cov_df[col] = cov_df[col].fillna(median if not pd.isna(median) else 0.0)

    # Align target and covariates on same index
    aligned_target = target_series.reindex(cov_df.index)
    valid_mask     = aligned_target.notna() & cov_df.notna().all(axis=1)

    cov_clean    = cov_df[valid_mask]
    target_clean = aligned_target[valid_mask]

    null_pct = cov_df.isna().mean().mean() * 100
    if null_pct > 0:
        logger.warning("chronos.covariates_residual_null",
                        null_pct=round(null_pct, 2))

    logger.info("chronos.covariates_built",
                rows=len(cov_clean),
                features=CHRONOS_COVARIATES)

    return {
        "target":             target_clean,
        "past_dynamic_real":  cov_clean.values.astype(np.float32),
        "feat_names":         CHRONOS_COVARIATES,
        "covariate_df":       cov_clean,  # keep for debugging
    }