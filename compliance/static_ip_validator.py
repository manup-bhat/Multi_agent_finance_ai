"""
Static IP Validator — SEBI Mandated IP Registration Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint (Correction #10):
  Static IP mandatory. Two IPs per API key. Weekly IP change only.

SEBI Algo Trading Rules (April 2026):
  - All algorithmic orders must originate from a REGISTERED static IP.
  - Max 2 IP addresses per API key.
  - IP changes allowed only once per week (else broker must reject).
  - The system must verify that the current outbound IP matches one
    of the registered IPs before placing any order.

This module:
  1. Loads registered IPs from environment (.env / settings)
  2. Detects current outbound IP (via ipify.org or configurable resolver)
  3. Validates current IP is in registered list
  4. Caches result for CACHE_TTL seconds to avoid repeated HTTP calls
  5. Raises ComplianceError if IP mismatch detected

Note: In production, IP should be a reserved static on cloud/VPS.
      In dev/testing, localhost or LAN IP can be allowlisted.
"""
from __future__ import annotations

import os
import socket
import time
import threading
import structlog
from dataclasses import dataclass
from typing import Optional

logger = structlog.get_logger(__name__)

# IP resolution endpoint (public IP)
IP_RESOLVER_URL    = "https://api.ipify.org"
CACHE_TTL_SECONDS  = 300         # re-check outbound IP every 5 minutes
MAX_REGISTERED_IPS = 2           # SEBI: max 2 IPs per API key


class ComplianceError(Exception):
    """Raised when a SEBI compliance check fails."""
    pass


@dataclass
class IPValidationResult:
    passed:        bool
    current_ip:    str
    registered_ips: list[str]
    reason:        str
    cached:        bool = False


class StaticIPValidator:
    """
    Validates that all API orders originate from a SEBI-registered static IP.

    Configuration via environment variables:
        SEBI_REGISTERED_IPS=192.168.1.100,10.0.0.5

    Usage:
        validator = StaticIPValidator()
        result    = validator.validate()
        if not result.passed:
            raise ComplianceError(result.reason)
    """

    def __init__(
        self,
        registered_ips: Optional[list[str]] = None,
        allow_loopback: bool = True,     # Allow 127.0.0.1 in dev
        allow_private:  bool = True,     # Allow 192.168.x.x, 10.x.x.x in dev
        ip_resolver: Optional[str] = None,
    ):
        self._registered = registered_ips or self._load_from_env()
        self._allow_loopback = allow_loopback
        self._allow_private  = allow_private
        self._ip_resolver    = ip_resolver or IP_RESOLVER_URL

        self._cache_ip:  Optional[str] = None
        self._cache_ts:  float         = 0.0
        self._lock = threading.Lock()

        if len(self._registered) > MAX_REGISTERED_IPS:
            logger.warning(
                "static_ip.too_many_ips",
                registered=len(self._registered),
                max=MAX_REGISTERED_IPS,
            )

        logger.info(
            "static_ip.init",
            registered_count=len(self._registered),
            allow_loopback=allow_loopback,
        )

    @staticmethod
    def _load_from_env() -> list[str]:
        """Load registered IPs from SEBI_REGISTERED_IPS env var."""
        raw = os.getenv("SEBI_REGISTERED_IPS", "")
        if not raw:
            logger.warning(
                "static_ip.no_registered_ips",
                hint="Set SEBI_REGISTERED_IPS=ip1,ip2 in .env",
            )
            return []
        return [ip.strip() for ip in raw.split(",") if ip.strip()]

    def _get_current_ip(self) -> str:
        """
        Determine current outbound IP. Tries:
          1. Cached value (if < CACHE_TTL_SECONDS old)
          2. HTTP call to ipify.org (public IP)
          3. Fallback: socket local address
        """
        with self._lock:
            now = time.monotonic()
            if self._cache_ip and (now - self._cache_ts) < CACHE_TTL_SECONDS:
                return self._cache_ip

        # Try HTTP resolver
        try:
            import urllib.request
            with urllib.request.urlopen(self._ip_resolver, timeout=5) as resp:
                ip = resp.read().decode().strip()
                with self._lock:
                    self._cache_ip = ip
                    self._cache_ts = time.monotonic()
                return ip
        except Exception as e:
            logger.warning("static_ip.resolver_failed", error=str(e))

        # Fallback: socket
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            with self._lock:
                self._cache_ip = ip
                self._cache_ts = time.monotonic()
            return ip
        except Exception as e:
            logger.warning("static_ip.socket_failed", error=str(e))
            return "0.0.0.0"

    @staticmethod
    def _is_loopback(ip: str) -> bool:
        return ip.startswith("127.") or ip == "::1"

    @staticmethod
    def _is_private(ip: str) -> bool:
        return (
            ip.startswith("192.168.")
            or ip.startswith("10.")
            or ip.startswith("172.16.")
        )

    def validate(self, use_cache: bool = True) -> IPValidationResult:
        """
        Validate current IP against registered list.

        Args:
            use_cache: Use cached IP if available (default True)

        Returns:
            IPValidationResult
        """
        if not use_cache:
            with self._lock:
                self._cache_ts = 0.0   # force refresh

        current_ip = self._get_current_ip()
        cached     = bool(self._cache_ip)

        # Loopback bypass (dev)
        if self._allow_loopback and self._is_loopback(current_ip):
            logger.info("static_ip.loopback_allowed", ip=current_ip)
            return IPValidationResult(
                passed=True,
                current_ip=current_ip,
                registered_ips=self._registered,
                reason="Loopback IP allowed in dev mode.",
                cached=cached,
            )

        # Private network bypass (local dev)
        if self._allow_private and self._is_private(current_ip):
            logger.info("static_ip.private_allowed", ip=current_ip)
            return IPValidationResult(
                passed=True,
                current_ip=current_ip,
                registered_ips=self._registered,
                reason="Private network IP allowed in dev mode.",
                cached=cached,
            )

        # If no registered IPs configured, warn but allow (set-up mode)
        if not self._registered:
            logger.warning("static_ip.no_registered_ips_configured", current_ip=current_ip)
            return IPValidationResult(
                passed=True,
                current_ip=current_ip,
                registered_ips=[],
                reason="⚠️ No registered IPs configured — set SEBI_REGISTERED_IPS in .env",
                cached=cached,
            )

        # In-list check
        if current_ip in self._registered:
            logger.info("static_ip.validated", ip=current_ip)
            return IPValidationResult(
                passed=True,
                current_ip=current_ip,
                registered_ips=self._registered,
                reason=f"IP {current_ip} is registered. ✅",
                cached=cached,
            )

        # FAIL
        reason = (
            f"SEBI VIOLATION: Current IP {current_ip!r} is not in registered list "
            f"{self._registered}. All algo orders must originate from a registered static IP."
        )
        logger.error("static_ip.failed", current_ip=current_ip, registered=self._registered)
        return IPValidationResult(
            passed=False,
            current_ip=current_ip,
            registered_ips=self._registered,
            reason=reason,
            cached=cached,
        )

    def add_registered_ip(self, ip: str) -> None:
        """Add IP to the registered list (for testing or runtime update)."""
        if len(self._registered) >= MAX_REGISTERED_IPS:
            raise ComplianceError(
                f"Cannot register more than {MAX_REGISTERED_IPS} IPs per SEBI rules."
            )
        self._registered.append(ip)
        logger.info("static_ip.added", ip=ip)
