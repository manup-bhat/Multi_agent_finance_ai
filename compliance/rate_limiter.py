"""
SEBI-Compliant Rate Limiter — Token Bucket Algorithm
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint (Part 0 – Correction #10):
  SEBI algo trading 10 OPS rule: Enforcement from April 1, 2026.
  Static IP mandatory. Two IPs per API key.
  Weekly IP change only. Mandatory daily session logout.

Blueprint validation gate (Phase 11):
  "Rate limiter blocks 11th order/second; static IP check passes"
  Check #17: "Fire 15 orders/second → limiter blocks orders 11-15"

This module implements a **Token Bucket** rate limiter:
  - Capacity:  MAX_OPS_PER_SECOND = 10 tokens
  - Refill:    10 tokens/second (1 per 100ms)
  - Per-segment: Each exchange segment (NSE_EQ, NSE_FO, NSE_CDS) has
                 its own independent bucket (SEBI counts per segment)

Thread-safe via threading.Lock() — safe for concurrent agent calls.

Reference:
  SEBI Circular SEBI/HO/MRD/MRD-PoD-3/P/CIR/2024/108 (April 2026)
  https://www.sebi.gov.in/legal/circulars/
"""
from __future__ import annotations

import threading
import time
import structlog
from dataclasses import dataclass, field
from typing import Optional

logger = structlog.get_logger(__name__)

# SEBI hard limit (config/constants.py: MAX_OPS_PER_SECOND = 10)
try:
    from config.constants import MAX_OPS_PER_SECOND, RATE_LIMIT_WINDOW_S
except ImportError:
    MAX_OPS_PER_SECOND = 10
    RATE_LIMIT_WINDOW_S = 1  # seconds

# NSE market segments (SEBI counts per segment independently)
class Segment:
    NSE_EQ  = "NSE_EQ"    # Equity cash
    NSE_FO  = "NSE_FO"    # Futures & Options
    NSE_CDS = "NSE_CDS"   # Currency Derivatives
    BSE_EQ  = "BSE_EQ"    # BSE Equity
    ALL     = "ALL"        # Aggregate across all segments


@dataclass
class RateLimitResult:
    allowed:   bool
    segment:   str
    tokens_remaining: float
    wait_ms:   float        # 0 if allowed, else ms to wait before retry
    reason:    str


class TokenBucket:
    """
    Thread-safe token bucket for a single market segment.
    Refills at `rate_per_second` tokens/second, up to `capacity` max.
    """

    def __init__(
        self,
        capacity: float = float(MAX_OPS_PER_SECOND),
        rate_per_second: float = float(MAX_OPS_PER_SECOND),
        segment: str = Segment.ALL,
    ):
        self.capacity       = capacity
        self.rate           = rate_per_second       # tokens added per second
        self.tokens         = capacity              # start full
        self.last_refill    = time.monotonic()
        self.segment        = segment
        self._lock          = threading.Lock()
        self.total_allowed  = 0
        self.total_blocked  = 0

    def _refill(self) -> None:
        """Add elapsed-time tokens (called under lock)."""
        now     = time.monotonic()
        elapsed = now - self.last_refill
        gained  = elapsed * self.rate
        self.tokens      = min(self.capacity, self.tokens + gained)
        self.last_refill = now

    def consume(self, cost: float = 1.0) -> RateLimitResult:
        """
        Attempt to consume `cost` tokens.

        Returns:
            RateLimitResult(allowed=True) if tokens available,
            RateLimitResult(allowed=False, wait_ms=X) if bucket empty.
        """
        with self._lock:
            self._refill()
            if self.tokens >= cost:
                self.tokens      -= cost
                self.total_allowed += 1
                return RateLimitResult(
                    allowed=True,
                    segment=self.segment,
                    tokens_remaining=round(self.tokens, 3),
                    wait_ms=0.0,
                    reason="OK",
                )
            else:
                # Time needed to fill `cost` tokens
                deficit  = cost - self.tokens
                wait_s   = deficit / self.rate
                wait_ms  = round(wait_s * 1000, 1)
                self.total_blocked += 1
                logger.warning(
                    "rate_limiter.blocked",
                    segment=self.segment,
                    tokens=round(self.tokens, 3),
                    wait_ms=wait_ms,
                )
                return RateLimitResult(
                    allowed=False,
                    segment=self.segment,
                    tokens_remaining=round(self.tokens, 3),
                    wait_ms=wait_ms,
                    reason=(
                        f"SEBI 10 OPS limit exceeded on {self.segment}. "
                        f"Wait {wait_ms:.0f}ms before retrying."
                    ),
                )


class SEBIRateLimiter:
    """
    Multi-segment SEBI rate limiter.

    Maintains independent TokenBucket per segment.
    A single order call on NSE_EQ does NOT consume NSE_FO quota.

    Usage:
        limiter = SEBIRateLimiter()
        result  = limiter.check_order(segment="NSE_FO")
        if not result.allowed:
            raise ComplianceError(result.reason)
    """

    def __init__(
        self,
        ops_limit: int = MAX_OPS_PER_SECOND,
        segments: Optional[list[str]] = None,
    ):
        self.ops_limit = ops_limit
        self._segments: list[str] = segments or [
            Segment.NSE_EQ, Segment.NSE_FO, Segment.NSE_CDS,
        ]
        self._buckets: dict[str, TokenBucket] = {
            seg: TokenBucket(
                capacity=float(ops_limit),
                rate_per_second=float(ops_limit),
                segment=seg,
            )
            for seg in self._segments
        }
        logger.info(
            "rate_limiter.init",
            ops_limit=ops_limit,
            segments=self._segments,
        )

    def check_order(self, segment: str = Segment.NSE_FO) -> RateLimitResult:
        """
        Check if an order on `segment` is within the SEBI OPS limit.
        Returns RateLimitResult (caller must check .allowed before proceeding).
        """
        if segment not in self._buckets:
            # Auto-create bucket for unknown segment
            self._buckets[segment] = TokenBucket(
                capacity=float(self.ops_limit),
                rate_per_second=float(self.ops_limit),
                segment=segment,
            )
        return self._buckets[segment].consume()

    def get_stats(self) -> dict[str, dict]:
        """Return allowed/blocked counts per segment."""
        return {
            seg: {
                "allowed": b.total_allowed,
                "blocked": b.total_blocked,
                "tokens":  round(b.tokens, 3),
            }
            for seg, b in self._buckets.items()
        }

    def reset(self, segment: Optional[str] = None) -> None:
        """Reset bucket(s) to full capacity. Useful for testing."""
        targets = [segment] if segment else list(self._buckets.keys())
        for seg in targets:
            if seg in self._buckets:
                with self._buckets[seg]._lock:
                    self._buckets[seg].tokens = self._buckets[seg].capacity
                    self._buckets[seg].last_refill = time.monotonic()
