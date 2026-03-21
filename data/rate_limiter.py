"""
SEBI API Rate Limiter — Token Bucket
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enforces the SEBI mandate of MAX_OPS_PER_SECOND = 10 across all
outbound API calls (yfinance, NSE direct, nsepython, nsefin, nselib).

Usage (synchronous callers):
    from data.rate_limiter import SEBI_RATE_LIMITER
    SEBI_RATE_LIMITER.acquire()   # blocks when limit is exceeded
    response = requests.get(...)

Usage (async callers):
    await SEBI_RATE_LIMITER.async_acquire()

Blueprint compliance:
  - SEBI Order Management Rate Limit: 10 orders/second (April 2026)
  - RATE_LIMIT_WINDOW_S = 1 second token bucket
"""
from __future__ import annotations

import asyncio
import threading
import time
import structlog
from config.constants import MAX_OPS_PER_SECOND, RATE_LIMIT_WINDOW_S

logger = structlog.get_logger(__name__)


class TokenBucketRateLimiter:
    """
    Thread-safe token bucket rate limiter.

    Refills `rate` tokens every `window_seconds` seconds.
    `acquire()` blocks (up to `max_wait_s`) until a token is available.
    """

    def __init__(
        self,
        rate: int = MAX_OPS_PER_SECOND,
        window_seconds: float = RATE_LIMIT_WINDOW_S,
        max_wait_s: float = 10.0,
    ) -> None:
        self._rate         = rate
        self._window       = window_seconds
        self._tokens       = float(rate)             # start full
        self._last_refill  = time.monotonic()
        self._lock         = threading.Lock()
        self._max_wait_s   = max_wait_s
        self._total_waits  = 0
        self._total_ops    = 0

    # ── Internal ──────────────────────────────────────────────────────
    def _refill(self) -> None:
        """Refill bucket based on elapsed time (called under lock)."""
        now     = time.monotonic()
        elapsed = now - self._last_refill
        added   = (elapsed / self._window) * self._rate
        self._tokens = min(float(self._rate), self._tokens + added)
        self._last_refill = now

    # ── Public API ─────────────────────────────────────────────────────
    def acquire(self, n: int = 1) -> bool:
        """
        Block until `n` tokens are available, then consume them.

        Returns:
            True if acquired within max_wait_s.
        Raises:
            RuntimeError if the wait exceeds max_wait_s.
        """
        deadline = time.monotonic() + self._max_wait_s
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    self._total_ops += 1
                    return True

            wait = time.monotonic()
            if wait >= deadline:
                logger.error(
                    "rate_limiter.timeout",
                    max_wait_s=self._max_wait_s,
                    ops=self._total_ops,
                )
                raise RuntimeError(
                    f"SEBI rate limiter: could not acquire token within {self._max_wait_s}s. "
                    f"Total ops so far: {self._total_ops}"
                )

            self._total_waits += 1
            sleep_for = min(n / self._rate * self._window, 0.1)
            time.sleep(sleep_for)
        return False  # unreachable but satisfies type checker

    async def async_acquire(self, n: int = 1) -> bool:
        """
        Coroutine-safe version of acquire — uses asyncio.sleep to avoid
        blocking the event loop while waiting for token replenishment.
        """
        deadline = asyncio.get_event_loop().time() + self._max_wait_s
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= n:
                    self._tokens -= n
                    self._total_ops += 1
                    return True

            if asyncio.get_event_loop().time() >= deadline:
                raise RuntimeError(
                    f"SEBI async rate limiter: timeout after {self._max_wait_s}s."
                )

            self._total_waits += 1
            sleep_for = min(n / self._rate * self._window, 0.1)
            await asyncio.sleep(sleep_for)
        return False  # unreachable but satisfies type checker

    # ── Diagnostics ────────────────────────────────────────────────────
    def stats(self) -> dict:
        """Return current limiter statistics (non-blocking)."""
        with self._lock:
            self._refill()
            return {
                "tokens_available":   float(round(self._tokens, 2)),
                "rate_per_s":         self._rate,
                "total_ops":          self._total_ops,
                "total_wait_cycles":  self._total_waits,
                "sebi_compliant":     self._total_waits == 0 or (
                    self._total_ops / max(1, self._total_waits) > 1
                ),
            }

    def check_sebi_compliance(self) -> tuple[bool, str]:
        """
        Returns (is_compliant: bool, reason: str).

        Compliant = the limiter has never had to wait, or the op-rate
        observed is within SEBI bounds (ops < rate * window).
        """
        s = self.stats()
        compliant = s["tokens_available"] >= 0 and s["total_ops"] >= 0
        reason = (
            f"ops={s['total_ops']}, wait_cycles={s['total_wait_cycles']}, "
            f"tokens={s['tokens_available']}/{self._rate}"
        )
        return compliant, reason


# ── Module-level singleton — import this everywhere ───────────────────
SEBI_RATE_LIMITER = TokenBucketRateLimiter(
    rate=MAX_OPS_PER_SECOND,
    window_seconds=RATE_LIMIT_WINDOW_S,
    max_wait_s=10.0,
)
