"""
Session Manager — Mandatory Daily Session Logout (SEBI Rule)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint (Correction #10):
  Mandatory daily session logout before next trading day.

SEBI algo trading rules (April 2026):
  - API session must be explicitly logged out at end of trading day.
  - Session cannot carry over across trading days.
  - Log all session start/end events for audit purposes.
  - NSE trading hours: 09:15–15:30 IST (config/constants.py)

This module:
  1. Tracks session start time (IST)
  2. Auto-schedules logout at 15:30 IST (NSE close) + LOGOUT_BUFFER_MINUTES
  3. Validates session is not active from previous trading day
  4. Logs all events for Phoenix/audit trail
  5. Provides SessionState (ACTIVE / LOGGED_OUT / EXPIRED)
"""
from __future__ import annotations

import datetime
import threading
import structlog
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable

import pytz

logger = structlog.get_logger(__name__)

MARKET_TZ           = pytz.timezone("Asia/Kolkata")
NSE_OPEN_HOUR       = 9
NSE_OPEN_MINUTE     = 15
NSE_CLOSE_HOUR      = 15
NSE_CLOSE_MINUTE    = 30
LOGOUT_BUFFER_MINUTES = 5    # 15:35 IST auto-logout (buffer after close)


class SessionState(str, Enum):
    ACTIVE     = "ACTIVE"
    LOGGED_OUT = "LOGGED_OUT"
    EXPIRED    = "EXPIRED"     # Previous day's session, not explicitly logged out


@dataclass
class SessionEvent:
    """Immutable session audit record."""
    event_type:  str           # LOGIN / LOGOUT / FORCE_LOGOUT / EXPIRED
    timestamp:   datetime.datetime
    trading_date: datetime.date
    reason:      str
    session_id:  str


@dataclass
class SessionInfo:
    """Current session details."""
    session_id:   str
    trading_date: datetime.date
    login_time:   datetime.datetime
    logout_time:  Optional[datetime.datetime]
    state:        SessionState
    events:       list[SessionEvent] = field(default_factory=list)


class SessionManager:
    """
    Tracks trading session lifecycle per SEBI requirements.

    Usage:
        sm = SessionManager()
        info = sm.start_session(session_id="breeze_20260313")
        # ... trading ...
        sm.end_session(reason="EOD")

    Integration:
        Call start_session() at trading start (e.g. 09:15 IST).
        The manager will auto-logout at 15:35 IST via background timer.
        FastAPI startup/shutdown events should call start/end accordingly.
    """

    def __init__(
        self,
        logout_callback: Optional[Callable] = None,
        auto_schedule_logout: bool = True,
    ):
        self._lock                 = threading.Lock()
        self._current:             Optional[SessionInfo] = None
        self._history:             list[SessionInfo]     = []
        self._logout_timer:        Optional[threading.Timer] = None
        self._logout_callback      = logout_callback
        self._auto_schedule        = auto_schedule_logout
        logger.info("session_manager.init")

    # ── Public API ────────────────────────────────────────────────────────────

    def start_session(self, session_id: str = "default") -> SessionInfo:
        """
        Start a new trading session. Validates no carryover from previous day.

        Args:
            session_id: Broker-assigned API session token identifier

        Returns:
            SessionInfo for the new session
        """
        with self._lock:
            now_ist      = datetime.datetime.now(MARKET_TZ)
            trading_date = now_ist.date()

            # Check for carryover session from a previous trading day
            if self._current is not None:
                if self._current.trading_date < trading_date:
                    logger.warning(
                        "session_manager.stale_session",
                        old_date=str(self._current.trading_date),
                        current_date=str(trading_date),
                    )
                    self._force_expire(reason="Carryover session from previous trading day")
                elif self._current.state == SessionState.ACTIVE:
                    # Already active same-day — just return it
                    logger.info("session_manager.already_active", session_id=self._current.session_id)
                    return self._current

            login_event = SessionEvent(
                event_type="LOGIN",
                timestamp=now_ist,
                trading_date=trading_date,
                reason="Session started",
                session_id=session_id,
            )
            info = SessionInfo(
                session_id=session_id,
                trading_date=trading_date,
                login_time=now_ist,
                logout_time=None,
                state=SessionState.ACTIVE,
                events=[login_event],
            )
            self._current = info

        logger.info(
            "session_manager.started",
            session_id=session_id, trading_date=str(trading_date),
        )

        if self._auto_schedule:
            self._schedule_auto_logout(now_ist, trading_date)

        return info

    def end_session(self, reason: str = "EOD") -> Optional[SessionInfo]:
        """
        Explicitly end the current session (mandatory SEBI requirement).

        Args:
            reason: Logout reason for audit log

        Returns:
            Completed SessionInfo, or None if no active session.
        """
        with self._lock:
            if self._current is None or self._current.state != SessionState.ACTIVE:
                logger.warning("session_manager.no_active_session")
                return self._current

            self._cancel_timer()
            now_ist = datetime.datetime.now(MARKET_TZ)
            self._current.logout_time = now_ist
            self._current.state       = SessionState.LOGGED_OUT
            self._current.events.append(SessionEvent(
                event_type="LOGOUT",
                timestamp=now_ist,
                trading_date=self._current.trading_date,
                reason=reason,
                session_id=self._current.session_id,
            ))
            self._history.append(self._current)

        logger.info(
            "session_manager.ended",
            session_id=self._current.session_id, reason=reason,
        )

        if self._logout_callback:
            try:
                self._logout_callback(self._current)
            except Exception as e:
                logger.warning("session_manager.callback_error", error=str(e))

        return self._current

    def get_current(self) -> Optional[SessionInfo]:
        """Return current session info (None if no session)."""
        with self._lock:
            return self._current

    def is_active(self) -> bool:
        """True if a session is currently active."""
        with self._lock:
            return (
                self._current is not None
                and self._current.state == SessionState.ACTIVE
            )

    def validate_session(self) -> tuple[bool, str]:
        """
        Validate current session for compliance before any API order.
        Returns (valid: bool, reason: str).
        """
        with self._lock:
            if self._current is None:
                return False, "No active session. Call start_session() first."
            if self._current.state == SessionState.EXPIRED:
                return False, "Session expired (previous day carryover). Start a new session."
            if self._current.state == SessionState.LOGGED_OUT:
                return False, "Session is logged out. Start a new session."
            # Check for same-day
            now_ist = datetime.datetime.now(MARKET_TZ)
            if self._current.trading_date != now_ist.date():
                return False, f"Session is for {self._current.trading_date}, not today ({now_ist.date()})."
            return True, "Session valid."

    def get_history(self) -> list[SessionInfo]:
        """Return all past sessions (for audit trail)."""
        with self._lock:
            return list(self._history)

    # ── Private helpers ───────────────────────────────────────────────────────

    def _schedule_auto_logout(
        self,
        login_time: datetime.datetime,
        trading_date: datetime.date,
    ) -> None:
        """Schedule auto-logout at NSE close + buffer."""
        self._cancel_timer()
        logout_time = MARKET_TZ.localize(datetime.datetime.combine(
            trading_date,
            datetime.time(NSE_CLOSE_HOUR, NSE_CLOSE_MINUTE + LOGOUT_BUFFER_MINUTES),
        ))
        delay_s = (logout_time - login_time).total_seconds()
        if delay_s > 0:
            self._logout_timer = threading.Timer(
                delay_s,
                self._auto_logout,
                args=["Auto-logout: NSE session closed at 15:30 IST + buffer"],
            )
            self._logout_timer.daemon = True
            self._logout_timer.start()
            logger.info(
                "session_manager.auto_logout_scheduled",
                at=str(logout_time),
                in_seconds=round(delay_s, 0),
            )

    def _auto_logout(self, reason: str) -> None:
        logger.info("session_manager.auto_logout_fired", reason=reason)
        self.end_session(reason=reason)

    def _cancel_timer(self) -> None:
        if self._logout_timer and self._logout_timer.is_alive():
            self._logout_timer.cancel()
            self._logout_timer = None

    def _force_expire(self, reason: str) -> None:
        """Mark current session as EXPIRED (under lock)."""
        if self._current:
            self._current.state = SessionState.EXPIRED
            self._current.events.append(SessionEvent(
                event_type="EXPIRED",
                timestamp=datetime.datetime.now(MARKET_TZ),
                trading_date=self._current.trading_date,
                reason=reason,
                session_id=self._current.session_id,
            ))
            self._history.append(self._current)
            self._current = None
        self._cancel_timer()
