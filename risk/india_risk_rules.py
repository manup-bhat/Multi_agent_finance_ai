"""
India-specific risk utility rules.
"""
from __future__ import annotations

from config.constants import MAX_OPS_PER_SECOND

_LOT_SIZE_MAP = {
    "NIFTY": 50,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 75,
    "SENSEX": 10,
}


def get_lot_size(ticker: str) -> int:
    symbol = (ticker or "").upper().replace(".NS", "").replace(".BO", "")
    return _LOT_SIZE_MAP.get(symbol, 100)


def get_equity_circuit_limits() -> tuple[int, int, int]:
    """Standard Indian broad-market circuit breaker thresholds."""
    return (10, 15, 20)


def get_max_ops_per_second() -> int:
    """SEBI-aligned operational throttle used across the project."""
    return MAX_OPS_PER_SECOND
