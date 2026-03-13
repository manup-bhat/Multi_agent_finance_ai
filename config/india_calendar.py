"""
India Trading Calendar
━━━━━━━━━━━━━━━━━━━━
Event detection for the India market calendar:
  - NSE weekly expiry Thursdays
  - RBI Monetary Policy Committee (MPC) dates
  - Union Budget date
  - Quarterly results seasons
  - Pre-flight event classification for Stage 0 of the workflow

Source-validated rules:
  - NSE weekly expiry: EVERY Thursday (unless holiday → moved to Wednesday)
  - RBI MPC: 6 meetings/year, ~6 weeks apart; 2026 schedule hardcoded below
  - Results season: Q1=Jul/Aug, Q2=Oct/Nov, Q3=Jan/Feb, Q4=Apr/May
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

# ── Event type constants ────────────────────────────────────────────────────
EVENT_RBI_MPC        = "RBI_MPC"
EVENT_RBI_MPC_DAY    = "RBI_MPC_ANNOUNCEMENT"   # the actual decision day
EVENT_BUDGET         = "BUDGET"
EVENT_RESULTS_SEASON = "RESULTS_SEASON"
EVENT_EXPIRY_WEEK    = "EXPIRY_WEEK"
EVENT_EXPIRY_DAY     = "EXPIRY_DAY"
EVENT_NORMAL         = "NORMAL"

# ── RBI MPC 2026: Bi-monthly meetings (decision dates) ──────────────────────
# Source: RBI annual calendar. 6 meetings per year.
# Format: YYYY-MM-DD (announcement day, typically last day of 3-day meeting)
RBI_MPC_DATES_2026: list[date] = [
    date(2026, 2, 7),    # Feb meeting
    date(2026, 4, 9),    # Apr meeting
    date(2026, 6, 6),    # Jun meeting
    date(2026, 8, 8),    # Aug meeting
    date(2026, 10, 8),   # Oct meeting
    date(2026, 12, 5),   # Dec meeting
]

# ── RBI MPC 2025 (for lookback) ─────────────────────────────────────────────
RBI_MPC_DATES_2025: list[date] = [
    date(2025, 2, 7),
    date(2025, 4, 9),
    date(2025, 6, 6),
    date(2025, 8, 8),
    date(2025, 10, 8),
    date(2025, 12, 5),
]

# ── Union Budget ─────────────────────────────────────────────────────────────
# India Budget is traditionally presented on the last working day of February
# or February 1 (post-2017 convention). In election years, interim budgets in
# Feb + full budget in Jul/Aug.
BUDGET_DATES: list[date] = [
    date(2025, 2, 1),    # Full Budget FY2025-26
    date(2026, 2, 1),    # Full Budget FY2026-27 (provisional)
]

_ALL_RBI_DATES = RBI_MPC_DATES_2025 + RBI_MPC_DATES_2026

# ── Quarterly Results Seasons ────────────────────────────────────────────────
# (month, day_start) → (month, day_end) inclusive
_RESULTS_SEASONS = [
    ((7, 10), (8, 31)),    # Q1 results (Apr-Jun quarter)
    ((10, 10), (11, 30)),  # Q2 results (Jul-Sep quarter)
    ((1, 10), (2, 28)),    # Q3 results (Oct-Dec quarter)
    ((4, 10), (5, 31)),    # Q4 results (Jan-Mar quarter)
]


def get_next_thursday(dt: date) -> date:
    """Return the next Thursday on or after `dt`."""
    days_ahead = 3 - dt.weekday()  # Thursday = weekday 3
    if days_ahead < 0:
        days_ahead += 7
    return dt + timedelta(days=days_ahead)


def is_expiry_thursday(dt: date) -> bool:
    """
    True if `dt` is an NSE weekly expiry Thursday.
    NSE has weekly expiry on EVERY Thursday (not just last of month).
    This function checks the weekday only — holiday adjustment is handled
    separately by the trading calendar.
    """
    return dt.weekday() == 3  # Thursday = 3


def days_to_next_expiry(dt: date) -> int:
    """
    Number of calendar days from `dt` to the next weekly expiry Thursday.
    Returns 0 if `dt` is itself a Thursday.
    """
    days_ahead = 3 - dt.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return days_ahead


def is_expiry_week(dt: date) -> bool:
    """True if `dt` falls in the same ISO week as an expiry Thursday."""
    dte = days_to_next_expiry(dt)
    return dte <= 2  # Mon/Tue/Wed/Thu of the expiry week


def is_rbi_mpc_day(dt: date) -> bool:
    """True if `dt` is a RBI MPC announcement date."""
    return dt in _ALL_RBI_DATES


def is_rbi_mpc_week(dt: date) -> bool:
    """True if `dt` falls within 3 days before a RBI MPC announcement."""
    for mpc_date in _ALL_RBI_DATES:
        if 0 <= (mpc_date - dt).days <= 3:
            return True
    return False


def is_budget_day(dt: date) -> bool:
    """True if `dt` is a Budget presentation day."""
    return dt in BUDGET_DATES


def is_results_season(dt: date) -> bool:
    """
    True if `dt` falls within any quarterly results season.
    Q1: 10 Jul – 31 Aug
    Q2: 10 Oct – 30 Nov
    Q3: 10 Jan – 28/29 Feb
    Q4: 10 Apr – 31 May
    """
    m, d = dt.month, dt.day
    for (sm, sd), (em, ed) in _RESULTS_SEASONS:
        if sm <= m <= em:
            if m == sm and d < sd:
                continue
            if m == em and d > ed:
                continue
            return True
    return False


def classify_market_event(dt: date) -> str:
    """
    Classify `dt` into the highest-priority market event category.

    Priority order (highest → lowest):
      1. RBI_MPC_ANNOUNCEMENT (the actual decision day)
      2. BUDGET
      3. RBI_MPC (week leading up to announcement)
      4. EXPIRY_DAY
      5. RESULTS_SEASON
      6. EXPIRY_WEEK
      7. NORMAL

    Returns:
        One of the EVENT_* constants.
    """
    if is_rbi_mpc_day(dt):
        return EVENT_RBI_MPC_DAY
    if is_budget_day(dt):
        return EVENT_BUDGET
    if is_rbi_mpc_week(dt):
        return EVENT_RBI_MPC
    if is_expiry_thursday(dt):
        return EVENT_EXPIRY_DAY
    if is_results_season(dt):
        return EVENT_RESULTS_SEASON
    if is_expiry_week(dt):
        return EVENT_EXPIRY_WEEK
    return EVENT_NORMAL


def get_event_description(event_type: str) -> str:
    """Human-readable description for each event type."""
    return {
        EVENT_RBI_MPC_DAY:    "RBI MPC Announcement Day — extreme volatility expected",
        EVENT_BUDGET:         "Union Budget Day — circuit breaker risk, avoid new positions",
        EVENT_RBI_MPC:        "RBI MPC Week — avoid rate-sensitive stocks, reduce leverage",
        EVENT_EXPIRY_DAY:     "NSE Weekly Expiry Thursday — max pain gravity, pin risk",
        EVENT_RESULTS_SEASON: "Quarterly Results Season — elevated individual stock volatility",
        EVENT_EXPIRY_WEEK:    "Expiry Week — rising gamma, option writers active",
        EVENT_NORMAL:         "Normal trading day",
    }.get(event_type, "Unknown event")
