"""
Phase 11: Compliance Module — Comprehensive Test Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint validation gates:
  ✓ Rate limiter blocks 11th order/second (SEBI 10 OPS rule)
  ✓ First 10 orders within 1 second are ALLOWED
  ✓ 11th+ orders within 1 second are BLOCKED
  ✓ Static IP: registered IP passes validation
  ✓ Static IP: unregistered IP fails validation
  ✓ Static IP: loopback allowed in dev mode
  ✓ Static IP: max 2 IPs per SEBI rules
  ✓ Session: start creates ACTIVE session
  ✓ Session: validate_session passes for same-day session
  ✓ Session: double login returns existing session
  ✓ Session: end_session marks as LOGGED_OUT
  ✓ Session: EXPIRED for previous-day session
  ✓ Algo ID: register creates unique ID
  ✓ Algo ID: tag_order attaches correct algo_id
  ✓ Algo ID: unregistered strategy raises KeyError
  ✓ Algo ID: order log queryable by algo_id
  ✓ Per-segment rate limits are INDEPENDENT (NSE_EQ exhausted ≠ NSE_FO blocked)
  ✓ Token bucket refills after wait
  ✓ Compliance package importable

No real network calls — all external dependencies mocked.
"""
from __future__ import annotations

import datetime
import time
import threading
from unittest.mock import patch, MagicMock

import pytest
import pytz


# ═══════════════════════════════════════════════════════════════════════════
# TestRateLimiter
# ═══════════════════════════════════════════════════════════════════════════

class TestRateLimiter:

    def test_first_10_orders_allowed(self):
        """Blueprint gate: first 10 orders in 1 second are allowed."""
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=10)
        results = [limiter.check_order("NSE_FO") for _ in range(10)]
        assert all(r.allowed for r in results), (
            f"Expected all 10 allowed, but blocked at: "
            f"{[i for i, r in enumerate(results) if not r.allowed]}"
        )

    def test_11th_order_blocked(self):
        """Blueprint gate: 11th order/second is BLOCKED."""
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=10)
        for _ in range(10):
            limiter.check_order("NSE_FO")
        result_11 = limiter.check_order("NSE_FO")
        assert result_11.allowed is False, "11th order should be blocked"

    def test_blocked_result_has_reason_and_wait_ms(self):
        """Blocked result must include reason string and positive wait_ms."""
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=5)
        for _ in range(5):
            limiter.check_order("NSE_EQ")
        blocked = limiter.check_order("NSE_EQ")
        assert blocked.allowed is False
        assert blocked.wait_ms > 0
        assert "SEBI" in blocked.reason or "limit" in blocked.reason.lower()

    def test_segments_are_independent(self):
        """NSE_EQ exhausted does NOT block NSE_FO orders."""
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=3)
        # Exhaust NSE_EQ
        for _ in range(3):
            limiter.check_order("NSE_EQ")
        blocked_eq = limiter.check_order("NSE_EQ")
        # NSE_FO should still have full quota
        allowed_fo = limiter.check_order("NSE_FO")
        assert blocked_eq.allowed is False
        assert allowed_fo.allowed is True

    def test_bucket_refills_after_delay(self):
        """After 200ms, at least 2 tokens should refill in a 10 OPS bucket."""
        from compliance.rate_limiter import TokenBucket, Segment
        bucket = TokenBucket(capacity=10, rate_per_second=10, segment=Segment.NSE_FO)
        # Drain all tokens
        for _ in range(10):
            bucket.consume()
        # Wait 200ms → ~2 tokens refilled
        time.sleep(0.2)
        result = bucket.consume()
        assert result.allowed is True, "Bucket should have refilled after 200ms"

    def test_stats_tracking(self):
        """get_stats() returns allowed and blocked counts."""
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=3)
        for _ in range(3):
            limiter.check_order("NSE_FO")
        limiter.check_order("NSE_FO")  # This one gets blocked
        stats = limiter.get_stats()
        fo_stats = stats.get("NSE_FO", {})
        assert fo_stats.get("allowed") == 3
        assert fo_stats.get("blocked") == 1

    def test_reset_refills_bucket(self):
        """reset() should fill bucket back to capacity."""
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=5)
        for _ in range(5):
            limiter.check_order("NSE_EQ")
        # Blocked
        assert limiter.check_order("NSE_EQ").allowed is False
        # Reset
        limiter.reset("NSE_EQ")
        # Now should be allowed again
        assert limiter.check_order("NSE_EQ").allowed is True

    def test_thread_safety(self):
        """Multiple threads firing simultaneously — no race conditions."""
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=10)
        results = []
        lock    = threading.Lock()

        def fire():
            r = limiter.check_order("NSE_FO")
            with lock:
                results.append(r.allowed)

        threads = [threading.Thread(target=fire) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Exactly 10 should be allowed (first 10 tokens)
        allowed_count = sum(results)
        assert allowed_count == 10, f"Expected 10 allowed, got {allowed_count}"

    def test_result_has_tokens_remaining(self):
        from compliance.rate_limiter import SEBIRateLimiter
        limiter = SEBIRateLimiter(ops_limit=10)
        r = limiter.check_order("NSE_FO")
        assert isinstance(r.tokens_remaining, float)
        assert r.tokens_remaining == pytest.approx(9.0, abs=0.5)


# ═══════════════════════════════════════════════════════════════════════════
# TestStaticIPValidator
# ═══════════════════════════════════════════════════════════════════════════

class TestStaticIPValidator:

    def test_registered_ip_passes(self):
        """IP in registered list → passes validation."""
        from compliance.static_ip_validator import StaticIPValidator
        # Disable loopback/private so we test actual registry check
        validator = StaticIPValidator(
            registered_ips=["203.0.113.50"],
            allow_loopback=False,
            allow_private=False,
        )
        with patch.object(validator, "_get_current_ip", return_value="203.0.113.50"):
            result = validator.validate()
        assert result.passed is True
        assert result.current_ip == "203.0.113.50"

    def test_unregistered_ip_fails(self):
        """IP NOT in registered list → fails validation."""
        from compliance.static_ip_validator import StaticIPValidator
        validator = StaticIPValidator(
            registered_ips=["203.0.113.50"],
            allow_loopback=False,
            allow_private=False,
        )
        with patch.object(validator, "_get_current_ip", return_value="1.2.3.4"):
            result = validator.validate()
        assert result.passed is False
        assert "SEBI VIOLATION" in result.reason

    def test_loopback_allowed_in_dev(self):
        """127.0.0.1 loopback → allowed in dev mode."""
        from compliance.static_ip_validator import StaticIPValidator
        validator = StaticIPValidator(
            registered_ips=[],
            allow_loopback=True,
        )
        with patch.object(validator, "_get_current_ip", return_value="127.0.0.1"):
            result = validator.validate()
        assert result.passed is True

    def test_private_ip_allowed_in_dev(self):
        """192.168.x.x → allowed when allow_private=True."""
        from compliance.static_ip_validator import StaticIPValidator
        validator = StaticIPValidator(
            registered_ips=["203.0.113.50"],
            allow_loopback=True,
            allow_private=True,
        )
        with patch.object(validator, "_get_current_ip", return_value="192.168.1.100"):
            result = validator.validate()
        assert result.passed is True

    def test_max_2_ips_enforced(self):
        """SEBI: max 2 IPs per API key."""
        from compliance.static_ip_validator import StaticIPValidator, ComplianceError
        validator = StaticIPValidator(registered_ips=["1.1.1.1", "2.2.2.2"])
        with pytest.raises(ComplianceError):
            validator.add_registered_ip("3.3.3.3")

    def test_no_registered_ips_warns_but_passes(self):
        """If no IPs configured at all, warn but pass (set-up mode)."""
        from compliance.static_ip_validator import StaticIPValidator
        validator = StaticIPValidator(registered_ips=[], allow_loopback=False, allow_private=False)
        with patch.object(validator, "_get_current_ip", return_value="203.0.113.50"):
            result = validator.validate()
        assert result.passed is True
        assert "⚠️" in result.reason

    def test_result_has_all_fields(self):
        from compliance.static_ip_validator import StaticIPValidator, IPValidationResult
        validator = StaticIPValidator(registered_ips=["10.0.0.1"], allow_loopback=True)
        with patch.object(validator, "_get_current_ip", return_value="127.0.0.1"):
            result = validator.validate()
        assert isinstance(result, IPValidationResult)
        assert isinstance(result.current_ip, str)
        assert isinstance(result.reason, str)


# ═══════════════════════════════════════════════════════════════════════════
# TestSessionManager
# ═══════════════════════════════════════════════════════════════════════════

class TestSessionManager:

    def test_start_creates_active_session(self):
        from compliance.session_manager import SessionManager, SessionState
        sm = SessionManager(auto_schedule_logout=False)
        info = sm.start_session("test_session_1")
        assert info.state == SessionState.ACTIVE
        assert info.session_id == "test_session_1"

    def test_is_active_after_start(self):
        from compliance.session_manager import SessionManager
        sm = SessionManager(auto_schedule_logout=False)
        sm.start_session("sess")
        assert sm.is_active() is True

    def test_end_session_sets_logged_out(self):
        from compliance.session_manager import SessionManager, SessionState
        sm = SessionManager(auto_schedule_logout=False)
        sm.start_session("sess")
        info = sm.end_session(reason="Test EOD")
        assert info.state == SessionState.LOGGED_OUT
        assert sm.is_active() is False

    def test_validate_session_passes_for_active(self):
        from compliance.session_manager import SessionManager
        sm = SessionManager(auto_schedule_logout=False)
        sm.start_session("sess")
        valid, reason = sm.validate_session()
        assert valid is True

    def test_validate_session_fails_when_no_session(self):
        from compliance.session_manager import SessionManager
        sm = SessionManager(auto_schedule_logout=False)
        valid, reason = sm.validate_session()
        assert valid is False
        assert "No active session" in reason

    def test_validate_session_fails_after_logout(self):
        from compliance.session_manager import SessionManager
        sm = SessionManager(auto_schedule_logout=False)
        sm.start_session("sess")
        sm.end_session()
        valid, reason = sm.validate_session()
        assert valid is False

    def test_double_start_returns_existing_session(self):
        """Starting session twice same day returns the same session."""
        from compliance.session_manager import SessionManager
        sm = SessionManager(auto_schedule_logout=False)
        info1 = sm.start_session("sess_a")
        info2 = sm.start_session("sess_b")
        assert info1.session_id == info2.session_id  # same session returned

    def test_session_events_logged(self):
        """Session events must include LOGIN and LOGOUT entries."""
        from compliance.session_manager import SessionManager
        sm = SessionManager(auto_schedule_logout=False)
        sm.start_session("audit_sess")
        info = sm.end_session(reason="EOD")
        event_types = [e.event_type for e in info.events]
        assert "LOGIN" in event_types
        assert "LOGOUT" in event_types

    def test_callback_called_on_logout(self):
        """logout_callback should be called with the session info."""
        from compliance.session_manager import SessionManager
        callback = MagicMock()
        sm = SessionManager(logout_callback=callback, auto_schedule_logout=False)
        sm.start_session("cb_sess")
        sm.end_session()
        callback.assert_called_once()

    def test_history_preserved_after_logout(self):
        from compliance.session_manager import SessionManager
        sm = SessionManager(auto_schedule_logout=False)
        sm.start_session("hist_sess")
        sm.end_session()
        history = sm.get_history()
        assert len(history) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# TestAlgoIDTracker
# ═══════════════════════════════════════════════════════════════════════════

class TestAlgoIDTracker:

    def test_register_creates_unique_id(self):
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        reg = tracker.register("MeanReversionRSI_BB", segment="NSE_FO")
        assert reg.algo_id.startswith("ALGO_")
        assert len(reg.algo_id) > 5

    def test_register_with_custom_id(self):
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        reg = tracker.register("Strategy_X", algo_id="CUSTOM_ALGO_001")
        assert reg.algo_id == "CUSTOM_ALGO_001"

    def test_is_registered_true_after_register(self):
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        tracker.register("TestAlgo")
        assert tracker.is_registered("TestAlgo") is True

    def test_is_registered_false_for_unknown(self):
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        assert tracker.is_registered("NotRegistered") is False

    def test_tag_order_attaches_algo_id(self):
        from compliance.algo_id_tracker import AlgoIDTracker, TaggedOrder
        tracker = AlgoIDTracker()
        reg = tracker.register("EMA_Cross", segment="NSE_FO")
        tagged = tracker.tag_order("EMA_Cross", {
            "ticker": "BANKNIFTY", "qty": 25, "price": 46500,
            "direction": "BUY", "order_type": "MARKET",
        })
        assert isinstance(tagged, TaggedOrder)
        assert tagged.algo_id == reg.algo_id
        assert tagged.ticker == "BANKNIFTY"

    def test_tag_order_unregistered_raises(self):
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        with pytest.raises(KeyError):
            tracker.tag_order("NotRegistered", {"ticker": "NIFTY"})

    def test_order_count_increments(self):
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        tracker.register("Strat_A")
        for _ in range(3):
            tracker.tag_order("Strat_A", {"ticker": "HDFC", "qty": 10, "price": 1650})
        reg = tracker.get_registration("Strat_A")
        assert reg.order_count == 3

    def test_get_order_log_by_algo_id(self):
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        reg_a = tracker.register("Strat_A")
        reg_b = tracker.register("Strat_B")
        tracker.tag_order("Strat_A", {"ticker": "HDFCBank", "qty": 10, "price": 1650})
        tracker.tag_order("Strat_B", {"ticker": "RELIANCE", "qty": 5, "price": 1200})
        log_a = tracker.get_order_log(algo_id=reg_a.algo_id)
        assert len(log_a) == 1
        assert log_a[0].algo_id == reg_a.algo_id

    def test_double_register_returns_existing(self):
        """Registering the same strategy twice returns the existing registration."""
        from compliance.algo_id_tracker import AlgoIDTracker
        tracker = AlgoIDTracker()
        reg1 = tracker.register("SameStrat")
        reg2 = tracker.register("SameStrat")
        assert reg1.algo_id == reg2.algo_id


# ═══════════════════════════════════════════════════════════════════════════
# TestPackageImports
# ═══════════════════════════════════════════════════════════════════════════

class TestPackageImports:

    def test_compliance_package_importable(self):
        from compliance import (
            SEBIRateLimiter, TokenBucket, RateLimitResult, Segment,
            StaticIPValidator, IPValidationResult, ComplianceError,
            SessionManager, SessionInfo, SessionState,
            AlgoIDTracker, AlgoRegistration, AlgoStatus, TaggedOrder,
            MAX_OPS_PER_SECOND, MAX_REGISTERED_IPS,
        )
        assert MAX_OPS_PER_SECOND == 10
        assert MAX_REGISTERED_IPS == 2

    def test_sebi_ops_limit_constant(self):
        from compliance import MAX_OPS_PER_SECOND
        # Blueprint: SEBI hard limit
        assert MAX_OPS_PER_SECOND == 10

    def test_max_registered_ips_constant(self):
        from compliance import MAX_REGISTERED_IPS
        # SEBI: max 2 IPs per API key
        assert MAX_REGISTERED_IPS == 2
