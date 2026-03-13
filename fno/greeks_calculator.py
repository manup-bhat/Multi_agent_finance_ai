"""
Black-Scholes Greeks Calculator — py_vollib Wrapper
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Computes all 5 Greeks (Delta, Gamma, Theta, Vega, Rho) and Implied Volatility
using the Black-Scholes-Merton model via py_vollib.

India-specific:
  - Risk-free rate defaults to RBI repo rate (~6.5% as of March 2026)
  - Handles NSE option chain DataFrame column conventions

Blueprint gate: py_vollib Greeks must match NSE website ±2% for 5 strikes.
"""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import structlog
from dataclasses import dataclass
from typing import Optional

from py_vollib.black_scholes_merton import black_scholes_merton as bsm_price
from py_vollib.black_scholes_merton.greeks.analytical import (
    delta as bsm_delta,
    gamma as bsm_gamma,
    theta as bsm_theta,
    vega as bsm_vega,
    rho as bsm_rho,
)
from py_vollib.black_scholes_merton.implied_volatility import (
    implied_volatility as bsm_iv,
)

logger = structlog.get_logger(__name__)

# India risk-free rate (RBI repo rate, March 2026)
DEFAULT_RISK_FREE_RATE = 0.065
# Dividend yield assumption for Nifty (approximate)
DEFAULT_DIVIDEND_YIELD = 0.012
# Minimum time to expiry (avoid division by zero)
MIN_TIME_TO_EXPIRY = 1e-6
# Trading days per year (India: ~252)
TRADING_DAYS_PER_YEAR = 252


@dataclass
class GreeksResult:
    """Greeks for a single option contract."""
    strike: float
    option_type: str        # 'c' or 'p'
    spot: float
    time_to_expiry: float   # in years
    iv: float               # annualised implied volatility
    delta: float
    gamma: float
    theta: float            # per day
    vega: float             # per 1% move in IV
    rho: float
    theoretical_price: float


def _flag(option_type: str) -> str:
    """Normalise option type to py_vollib flag: 'c' or 'p'."""
    ot = option_type.upper().strip()
    if ot in ("C", "CE", "CALL"):
        return "c"
    if ot in ("P", "PE", "PUT"):
        return "p"
    raise ValueError(f"Unknown option_type: {option_type!r}. Use CE/PE/C/P/CALL/PUT.")


def compute_greeks(
    S: float,
    K: float,
    T: float,
    r: float = DEFAULT_RISK_FREE_RATE,
    sigma: float = 0.20,
    option_type: str = "c",
    q: float = DEFAULT_DIVIDEND_YIELD,
) -> GreeksResult:
    """
    Compute all 5 Greeks for a single option.

    Args:
        S:     Spot price (underlying)
        K:     Strike price
        T:     Time to expiry in YEARS (e.g. 30 days = 30/365)
        r:     Risk-free rate (annualised, default = RBI repo rate 6.5%)
        sigma: Implied volatility (annualised, e.g. 0.20 = 20%)
        option_type: 'c'/'p' or 'CE'/'PE'/'CALL'/'PUT'
        q:     Dividend yield (annualised)

    Returns:
        GreeksResult dataclass
    """
    flag = _flag(option_type)
    T = max(T, MIN_TIME_TO_EXPIRY)

    price = bsm_price(flag, S, K, T, r, sigma, q)
    d = bsm_delta(flag, S, K, T, r, sigma, q)
    g = bsm_gamma(flag, S, K, T, r, sigma, q)
    t = bsm_theta(flag, S, K, T, r, sigma, q)
    v = bsm_vega(flag, S, K, T, r, sigma, q)
    rh = bsm_rho(flag, S, K, T, r, sigma, q)

    return GreeksResult(
        strike=K,
        option_type=flag,
        spot=S,
        time_to_expiry=T,
        iv=sigma,
        delta=round(d, 6),
        gamma=round(g, 6),
        theta=round(t / TRADING_DAYS_PER_YEAR, 6),   # convert annual → per day
        vega=round(v / 100, 6),                       # per 1% move
        rho=round(rh / 100, 6),                       # per 1% move in rate
        theoretical_price=round(price, 4),
    )


def compute_iv(
    S: float,
    K: float,
    T: float,
    r: float,
    market_price: float,
    option_type: str = "c",
    q: float = DEFAULT_DIVIDEND_YIELD,
) -> float:
    """
    Compute implied volatility from market price using BSM model.

    Returns:
        Annualised IV as a float (e.g. 0.20 = 20%)

    Raises:
        ValueError if IV cannot be computed (price out of BSM range)
    """
    flag = _flag(option_type)
    T = max(T, MIN_TIME_TO_EXPIRY)

    try:
        # py_vollib's implied_volatility signature: (price, S, K, t, r, q, flag)
        # NOTE: q comes BEFORE flag — different from bsm_price order
        iv = bsm_iv(market_price, S, K, T, r, q, flag)
        return round(iv, 6)
    except Exception as exc:
        logger.warning(
            "greeks.iv_computation_failed",
            S=S, K=K, T=T, market_price=market_price,
            option_type=flag, error=str(exc),
        )
        raise ValueError(
            f"Cannot compute IV: S={S}, K={K}, T={T:.4f}, "
            f"price={market_price}, type={flag}"
        ) from exc


def compute_chain_greeks(
    chain_df: pd.DataFrame,
    spot: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
    dividend_yield: float = DEFAULT_DIVIDEND_YIELD,
) -> pd.DataFrame:
    """
    Compute Greeks for an entire option chain DataFrame.

    Expected columns in chain_df:
        - strike_price: float
        - option_type: 'CE' or 'PE'
        - time_to_expiry: float (in years)
        - implied_volatility OR iv: float (annualised)

    Returns:
        DataFrame with added columns: delta, gamma, theta, vega, rho, theoretical_price
    """
    results = []
    iv_col = "implied_volatility" if "implied_volatility" in chain_df.columns else "iv"

    for _, row in chain_df.iterrows():
        K = float(row["strike_price"])
        ot = str(row["option_type"])
        T = float(row["time_to_expiry"])
        sigma = float(row.get(iv_col, 0.20))

        if sigma <= 0 or T <= 0:
            results.append({
                "delta": 0.0, "gamma": 0.0, "theta": 0.0,
                "vega": 0.0, "rho": 0.0, "theoretical_price": 0.0,
            })
            continue

        try:
            gr = compute_greeks(spot, K, T, risk_free_rate, sigma, ot, dividend_yield)
            results.append({
                "delta": gr.delta,
                "gamma": gr.gamma,
                "theta": gr.theta,
                "vega": gr.vega,
                "rho": gr.rho,
                "theoretical_price": gr.theoretical_price,
            })
        except Exception:
            results.append({
                "delta": 0.0, "gamma": 0.0, "theta": 0.0,
                "vega": 0.0, "rho": 0.0, "theoretical_price": 0.0,
            })

    greeks_df = pd.DataFrame(results, index=chain_df.index)
    return pd.concat([chain_df, greeks_df], axis=1)
