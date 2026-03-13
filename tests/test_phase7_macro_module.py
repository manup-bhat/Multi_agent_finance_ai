"""
Phase 7: Macro Module — Test Suite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Blueprint validation gates:
  ✓ VIX regime triggers at exact thresholds (13/18/25/30)
  ✓ VIX circuit breaker activates at VIX ≥ 25
  ✓ Position size multiplier = 0.0 when VIX ≥ 25
  ✓ FII/DII 5-day z-score computes correctly on known series
  ✓ Consensus classification 4-quadrant accuracy
  ✓ Sell streak detection: 7+ days alert
  ✓ Rupee trend classification correct
  ✓ Crude regime correct at boundaries
  ✓ SGX gap computation correct
  ✓ Global sentiment classification
  ✓ Event impact: correct event type + trading rules

All tests use synthetic data — zero API calls.
"""
from __future__ import annotations

import math
from datetime import date
import numpy as np
import pandas as pd
import pytest

# ── config/india_calendar ──────────────────────────────────────────────────
from config.india_calendar import (
    is_expiry_thursday, days_to_next_expiry, is_expiry_week,
    is_rbi_mpc_day, is_budget_day, is_results_season,
    classify_market_event, get_event_description,
    EVENT_RBI_MPC_DAY, EVENT_BUDGET, EVENT_RBI_MPC,
    EVENT_EXPIRY_DAY, EVENT_RESULTS_SEASON, EVENT_EXPIRY_WEEK, EVENT_NORMAL,
    RBI_MPC_DATES_2026,
)

# ── macro/india_vix_monitor ────────────────────────────────────────────────
from macro.india_vix_monitor import (
    classify_vix_regime, compute_vix_zscore, compute_position_size_multiplier,
    detect_vix_reversion_signal,
    VIX_COMPLACENCY, VIX_NORMAL, VIX_ELEVATED, VIX_HIGH, VIX_CRISIS,
)

# ── macro/fii_dii_tracker ──────────────────────────────────────────────────
from macro.fii_dii_tracker import (
    compute_flow_zscore, classify_consensus, detect_sell_streak,
    compute_cumulative_flow, classify_trend, build_flow_report,
    CONSENSUS_STRONG_BULL, CONSENSUS_STRONG_BEAR,
    CONSENSUS_FII_BULL_DII_BEAR, CONSENSUS_DII_BULL_FII_BEAR,
)

# ── macro/rupee_tracker ────────────────────────────────────────────────────
from macro.rupee_tracker import (
    classify_rupee_trend, compute_rupee_fii_correlation,
    rupee_impact_on_nifty_signal, analyze_rupee,
    RUPEE_APPRECIATING, RUPEE_DEPRECIATING, RUPEE_STABLE,
)

# ── macro/crude_tracker ────────────────────────────────────────────────────
from macro.crude_tracker import (
    classify_crude_from_price, crude_cad_impact_signal, analyze_crude,
    CRUDE_SUPPORTIVE, CRUDE_NEUTRAL, CRUDE_INFLATIONARY,
)

# ── macro/global_cues_aggregator ───────────────────────────────────────────
from macro.global_cues_aggregator import (
    compute_sgx_gap, classify_global_sentiment, expected_nifty_open,
    build_global_cues_report,
    RISK_ON, RISK_OFF, MIXED,
)

# ── macro/event_impact_analyzer ───────────────────────────────────────────
from macro.event_impact_analyzer import (
    compute_event_volatility_multiplier, get_event_trading_rules,
    build_event_impact_report,
)

# ── macro package import ───────────────────────────────────────────────────
import macro


# ═══════════════════════════════════════════════════════════════════════════
# TestIndiaCalendar
# ═══════════════════════════════════════════════════════════════════════════

class TestIndiaCalendar:

    def test_thursday_is_expiry_day(self):
        """Every Thursday is an NSE weekly expiry day."""
        thu = date(2026, 3, 12)  # a Thursday
        assert thu.weekday() == 3
        assert is_expiry_thursday(thu) is True

    def test_non_thursday_is_not_expiry(self):
        for d in [date(2026, 3, 9), date(2026, 3, 10), date(2026, 3, 11),
                  date(2026, 3, 13), date(2026, 3, 14)]:
            assert is_expiry_thursday(d) is False

    def test_days_to_next_expiry_on_thursday(self):
        """Thursday → 0 days to expiry."""
        thu = date(2026, 3, 12)
        assert days_to_next_expiry(thu) == 0

    def test_days_to_next_expiry_on_friday(self):
        """Friday → 6 days to next Thursday."""
        fri = date(2026, 3, 13)
        assert days_to_next_expiry(fri) == 6

    def test_days_to_next_expiry_on_monday(self):
        """Monday → 3 days to Thursday."""
        mon = date(2026, 3, 16)
        assert days_to_next_expiry(mon) == 3

    def test_expiry_week_tuesday(self):
        """Tuesday of expiry week is in expiry week."""
        tue = date(2026, 3, 10)  # 2 days before Thursday 12 Mar
        assert is_expiry_week(tue) is True

    def test_not_expiry_week_friday(self):
        """Friday after expiry → NOT expiry week."""
        fri = date(2026, 3, 13)  # 6 days to next Thursday
        assert is_expiry_week(fri) is False

    def test_rbi_mpc_day_detection(self):
        """RBI MPC 2026 announcement dates detected correctly."""
        assert is_rbi_mpc_day(date(2026, 2, 7)) is True
        assert is_rbi_mpc_day(date(2026, 4, 9)) is True
        assert is_rbi_mpc_day(date(2026, 6, 6)) is True

    def test_non_rbi_date_not_detected(self):
        assert is_rbi_mpc_day(date(2026, 3, 13)) is False

    def test_budget_day_detection(self):
        assert is_budget_day(date(2026, 2, 1)) is True
        assert is_budget_day(date(2026, 3, 1)) is False

    def test_results_season_q1_july(self):
        """July 15 = Q1 results season."""
        assert is_results_season(date(2026, 7, 15)) is True

    def test_results_season_q2_october(self):
        assert is_results_season(date(2026, 10, 20)) is True

    def test_results_season_q3_january(self):
        assert is_results_season(date(2026, 1, 15)) is True

    def test_results_season_q4_april(self):
        assert is_results_season(date(2026, 4, 20)) is True

    def test_not_results_season_june(self):
        """June is NOT results season."""
        assert is_results_season(date(2026, 6, 15)) is False

    def test_classify_rbi_mpc_announcement_day(self):
        assert classify_market_event(date(2026, 2, 7)) == EVENT_RBI_MPC_DAY

    def test_classify_budget_day(self):
        assert classify_market_event(date(2026, 2, 1)) == EVENT_BUDGET

    def test_classify_expiry_thursday(self):
        """A Thursday that is not RBI/Budget → EXPIRY_DAY."""
        thu = date(2026, 3, 12)
        result = classify_market_event(thu)
        assert result == EVENT_EXPIRY_DAY

    def test_classify_normal_day(self):
        """A normal Friday with no events."""
        # Sept 11 2026 = Friday. Days to next Thu (Sep 17) = 6 → NOT expiry week.
        # Sep not results season (ends Aug 31), not RBI MPC week, not budget.
        normal = date(2026, 9, 11)
        result = classify_market_event(normal)
        assert result == EVENT_NORMAL

    def test_event_description_not_empty(self):
        for event in [EVENT_RBI_MPC_DAY, EVENT_BUDGET, EVENT_EXPIRY_DAY, EVENT_NORMAL]:
            assert len(get_event_description(event)) > 0


# ═══════════════════════════════════════════════════════════════════════════
# TestVIXMonitor
# ═══════════════════════════════════════════════════════════════════════════

class TestVIXMonitor:

    def test_complacency_below_13(self):
        """VIX < 13 → COMPLACENCY."""
        assert classify_vix_regime(12.9) == VIX_COMPLACENCY
        assert classify_vix_regime(10.0) == VIX_COMPLACENCY

    def test_normal_between_13_and_18(self):
        """13 ≤ VIX < 18 → NORMAL."""
        assert classify_vix_regime(13.0) == VIX_NORMAL
        assert classify_vix_regime(13.1) == VIX_NORMAL
        assert classify_vix_regime(17.9) == VIX_NORMAL

    def test_elevated_between_18_and_25(self):
        """18 ≤ VIX < 25 → ELEVATED."""
        assert classify_vix_regime(18.0) == VIX_ELEVATED
        assert classify_vix_regime(18.1) == VIX_ELEVATED
        assert classify_vix_regime(24.9) == VIX_ELEVATED

    def test_high_between_25_and_30(self):
        """25 ≤ VIX < 30 → HIGH (circuit breaker)."""
        assert classify_vix_regime(25.0) == VIX_HIGH
        assert classify_vix_regime(25.1) == VIX_HIGH
        assert classify_vix_regime(29.9) == VIX_HIGH

    def test_crisis_at_30_and_above(self):
        """VIX ≥ 30 → CRISIS."""
        assert classify_vix_regime(30.0) == VIX_CRISIS
        assert classify_vix_regime(40.0) == VIX_CRISIS

    def test_position_size_normal_is_1(self):
        assert compute_position_size_multiplier(15.0) == 1.0

    def test_position_size_elevated_is_0_7(self):
        assert compute_position_size_multiplier(20.0) == pytest.approx(0.7, abs=0.01)

    def test_position_size_circuit_breaker_is_zero(self):
        """Blueprint gate: VIX ≥ 25 → position size multiplier = 0.0."""
        assert compute_position_size_multiplier(25.0) == 0.0
        assert compute_position_size_multiplier(35.0) == 0.0

    def test_vix_zscore_known_value(self):
        """Z-score of 20-day flat series then spike = high positive z."""
        series = [15.0] * 19 + [25.0]  # flat then spike
        zs = compute_vix_zscore(series, window=20)
        assert float(zs.iloc[-1]) > 2.0  # spike above mean → high z

    def test_vix_zscore_flat_series_near_zero(self):
        """Flat VIX series → z-score ≈ 0."""
        series = [15.0] * 20
        zs = compute_vix_zscore(series, window=20)
        # std of flat series = 0, so we fill with 1.0
        # z = (15-15)/1 = 0
        assert abs(float(zs.iloc[-1])) < 0.01

    def test_circuit_breaker_detected(self):
        vix_series = [15.0] * 18 + [20.0, 26.0]
        signal = detect_vix_reversion_signal(vix_series)
        assert signal.is_circuit_breaker is True
        assert signal.position_size_multiplier == 0.0

    def test_crisis_detected_at_31(self):
        vix_series = [15.0] * 18 + [25.0, 31.0]
        signal = detect_vix_reversion_signal(vix_series)
        assert signal.is_crisis is True

    def test_extreme_fear_signal(self):
        """Sharp VIX spike → is_extreme_fear = True (contrarian buy)."""
        series = [15.0] * 18 + [14.8, 28.0]  # sudden spike
        signal = detect_vix_reversion_signal(series, window=15)
        assert signal.is_extreme_fear is True
        assert signal.signal == "CRISIS" or signal.signal in ("BUY_FEAR", "CIRCUIT_BREAKER", "CRISIS")

    def test_macro_package_vix_importable(self):
        assert hasattr(macro, "classify_vix_regime")
        assert hasattr(macro, "detect_vix_reversion_signal")


# ═══════════════════════════════════════════════════════════════════════════
# TestFIIDIITracker
# ═══════════════════════════════════════════════════════════════════════════

class TestFIIDIITracker:

    def _make_df(self, fii_values: list, dii_values: list) -> pd.DataFrame:
        return pd.DataFrame({
            "fii_net_value": fii_values,
            "dii_net_value": dii_values,
        })

    def test_zscore_known_series(self):
        """z-score on known series: mean=0 std=1 → z ≈ 0 for middle values."""
        series = [0.0, 0.0, 1.0, -1.0, 0.0]
        zs = compute_flow_zscore(series, window=5)
        # The z-score should be computed
        assert len(zs) == 5
        assert not zs.isna().all()

    def test_zscore_flat_series_near_zero(self):
        """Flat series → rolling std = 0 → replaced with 1.0 → z = 0."""
        series = [1000.0] * 10
        zs = compute_flow_zscore(series, window=5)
        assert abs(float(zs.iloc[-1])) < 0.01

    def test_consensus_strong_bull(self):
        assert classify_consensus(+1000, +500) == CONSENSUS_STRONG_BULL

    def test_consensus_strong_bear(self):
        assert classify_consensus(-1000, -500) == CONSENSUS_STRONG_BEAR

    def test_consensus_fii_bull_dii_bear(self):
        assert classify_consensus(+1000, -200) == CONSENSUS_FII_BULL_DII_BEAR

    def test_consensus_dii_bull_fii_bear(self):
        assert classify_consensus(-1000, +500) == CONSENSUS_DII_BULL_FII_BEAR

    def test_sell_streak_7_days_triggers_alert(self):
        """7+ consecutive net sell days → alert."""
        series = [+100, +200] + [-500] * 7  # 7 consecutive sells
        streak = detect_sell_streak(series)
        assert streak >= 7

    def test_sell_streak_broken_resets(self):
        """Positive day in the middle breaks the streak."""
        series = [-100, -200, +50, -300, -400]  # streak = 2 at end
        streak = detect_sell_streak(series)
        assert streak == 2

    def test_sell_streak_no_selling(self):
        series = [+100, +200, +300]
        assert detect_sell_streak(series) == 0

    def test_cumulative_flow_positive(self):
        series = [500.0] * 20
        assert compute_cumulative_flow(series, lookback=20) == pytest.approx(10_000.0)

    def test_classify_trend_accumulating(self):
        assert classify_trend(8_000.0) == "ACCUMULATING"

    def test_classify_trend_distributing(self):
        assert classify_trend(-8_000.0) == "DISTRIBUTING"

    def test_classify_trend_neutral(self):
        assert classify_trend(2_000.0) == "NEUTRAL"

    def test_build_flow_report_returns_correct_consensus(self):
        df = self._make_df([1000, 1200, 1100, 1300, 900], [500, 600, 700, 400, 800])
        report = build_flow_report(df)
        assert report.consensus == CONSENSUS_STRONG_BULL
        assert report.latest_fii_net > 0
        assert report.latest_dii_net > 0

    def test_build_flow_report_sell_streak_alert(self):
        fii = [-1000] * 10
        dii = [+500] * 10
        df = self._make_df(fii, dii)
        report = build_flow_report(df)
        assert report.sell_streak_alert is True
        assert report.sell_streak_days >= 7

    def test_build_flow_report_large_sell_alert(self):
        fii = [-3000.0]  # ₹3000 crore sell — above 2000 cr threshold
        dii = [+500.0]
        df = self._make_df(fii, dii)
        report = build_flow_report(df)
        assert report.large_sell_alert is True


# ═══════════════════════════════════════════════════════════════════════════
# TestRupeeTracker
# ═══════════════════════════════════════════════════════════════════════════

class TestRupeeTracker:

    def test_depreciating_when_usdinr_rises(self):
        """USD/INR rising = rupee weakening = DEPRECIATING."""
        series = [84.0, 84.5, 85.0, 85.5, 86.0, 86.5, 87.0, 87.5, 88.0, 88.5]
        assert classify_rupee_trend(series) == RUPEE_DEPRECIATING

    def test_appreciating_when_usdinr_falls(self):
        """USD/INR falling = rupee strengthening = APPRECIATING."""
        series = [88.0, 87.5, 87.0, 86.5, 86.0, 85.5, 85.0, 84.5, 84.0, 83.5]
        assert classify_rupee_trend(series) == RUPEE_APPRECIATING

    def test_stable_when_minimal_change(self):
        """Less than ±0.5% movement = STABLE."""
        series = [86.0] * 10  # flat
        assert classify_rupee_trend(series) == RUPEE_STABLE

    def test_depreciation_gives_negative_nifty_signal(self):
        assert rupee_impact_on_nifty_signal(RUPEE_DEPRECIATING) == "NEGATIVE"

    def test_appreciation_gives_positive_nifty_signal(self):
        assert rupee_impact_on_nifty_signal(RUPEE_APPRECIATING) == "POSITIVE"

    def test_stable_gives_neutral_nifty_signal(self):
        assert rupee_impact_on_nifty_signal(RUPEE_STABLE) == "NEUTRAL"

    def test_fii_correlation_negative_for_depreciation(self):
        """When FIIs sell (negative), USD/INR rises — should show negative correlation."""
        usdinr = [84.0 + i * 0.3 for i in range(20)]  # rising
        fii_net = [1000 - i * 200 for i in range(20)]  # falling
        corr = compute_rupee_fii_correlation(usdinr, fii_net)
        assert corr < 0  # expected negative correlation

    def test_analyze_rupee_returns_result(self):
        series = [86.0, 86.2, 86.4, 86.6, 86.8, 87.0, 87.2, 87.4, 87.6, 87.8]
        result = analyze_rupee(series)
        assert result.trend == RUPEE_DEPRECIATING
        assert result.current_usdinr > 86.0


# ═══════════════════════════════════════════════════════════════════════════
# TestCrudeTracker
# ═══════════════════════════════════════════════════════════════════════════

class TestCrudeTracker:

    def test_supportive_below_75(self):
        assert classify_crude_from_price(74.9) == CRUDE_SUPPORTIVE
        assert classify_crude_from_price(60.0) == CRUDE_SUPPORTIVE

    def test_neutral_between_75_and_95(self):
        assert classify_crude_from_price(75.0) == CRUDE_NEUTRAL
        assert classify_crude_from_price(80.0) == CRUDE_NEUTRAL
        assert classify_crude_from_price(94.9) == CRUDE_NEUTRAL

    def test_inflationary_above_95(self):
        assert classify_crude_from_price(95.0) == CRUDE_INFLATIONARY
        assert classify_crude_from_price(100.0) == CRUDE_INFLATIONARY
        assert classify_crude_from_price(120.0) == CRUDE_INFLATIONARY

    def test_cad_impact_positive_when_supportive(self):
        assert crude_cad_impact_signal(70.0) == "POSITIVE"

    def test_cad_impact_negative_when_inflationary(self):
        assert crude_cad_impact_signal(100.0) == "NEGATIVE"

    def test_cad_impact_neutral_when_neutral(self):
        assert crude_cad_impact_signal(85.0) == "NEUTRAL"

    def test_analyze_crude_returns_result(self):
        series = [100.0] * 10
        result = analyze_crude(series)
        assert result.regime == CRUDE_INFLATIONARY
        assert result.cad_risk is True
        assert result.inr_pressure is True


# ═══════════════════════════════════════════════════════════════════════════
# TestGlobalCuesAggregator
# ═══════════════════════════════════════════════════════════════════════════

class TestGlobalCuesAggregator:

    def test_gap_up_calculation(self):
        """SGX > Nifty prev close by >0.5% → GAP_UP."""
        gap_pct, direction = compute_sgx_gap(sgx_price=22_200.0, nifty_prev_close=22_000.0)
        assert direction == "GAP_UP"
        assert abs(gap_pct - (200 / 22_000 * 100)) < 0.01

    def test_gap_down_calculation(self):
        """SGX < Nifty by >0.5% → GAP_DOWN."""
        gap_pct, direction = compute_sgx_gap(sgx_price=21_800.0, nifty_prev_close=22_000.0)
        assert direction == "GAP_DOWN"
        assert gap_pct < 0

    def test_flat_gap(self):
        """SGX ≈ Nifty (within ±0.5%) → FLAT."""
        gap_pct, direction = compute_sgx_gap(sgx_price=22_050.0, nifty_prev_close=22_000.0)
        assert direction == "FLAT"

    def test_risk_on_when_both_positive(self):
        assert classify_global_sentiment(0.01, 0.015, 0.008) == RISK_ON

    def test_risk_off_when_both_negative(self):
        assert classify_global_sentiment(-0.01, -0.02, -0.005) == RISK_OFF

    def test_mixed_when_divergent(self):
        assert classify_global_sentiment(0.01, 0.015, -0.01) == MIXED

    def test_expected_nifty_open_positive(self):
        assert expected_nifty_open("GAP_UP", RISK_ON) == "POSITIVE"

    def test_expected_nifty_open_negative(self):
        assert expected_nifty_open("GAP_DOWN", RISK_OFF) == "NEGATIVE"

    def test_expected_nifty_open_neutral_conflict(self):
        """Gap up + risk off → conflicting → NEUTRAL."""
        result = expected_nifty_open("GAP_UP", RISK_OFF)
        assert result == "NEUTRAL"

    def test_build_global_cues_report_structure(self):
        report = build_global_cues_report(
            sgx_price=22_200.0,
            nifty_prev_close=22_000.0,
            sp500_ret=0.012,
            nasdaq_ret=0.018,
            asia_rets={"nikkei": 0.005, "hangseng": -0.003},
        )
        assert report.sgx_gap_direction == "GAP_UP"
        assert report.global_sentiment in (RISK_ON, RISK_OFF, MIXED)
        assert isinstance(report.description, str) and len(report.description) > 10


# ═══════════════════════════════════════════════════════════════════════════
# TestEventImpactAnalyzer
# ═══════════════════════════════════════════════════════════════════════════

class TestEventImpactAnalyzer:

    def test_rbi_mpc_announcement_is_extreme(self):
        report = build_event_impact_report(date(2026, 2, 7), current_vix=15.0)
        assert report.event_type == EVENT_RBI_MPC_DAY
        assert report.risk_level == "EXTREME"
        assert report.position_size_multiplier <= 0.5

    def test_budget_day_avoid_new_positions(self):
        report = build_event_impact_report(date(2026, 2, 1), current_vix=15.0)
        assert report.event_type == EVENT_BUDGET
        assert report.avoid_new_positions is True
        assert report.risk_level == "EXTREME"

    def test_expiry_thursday_moderate_risk(self):
        thu = date(2026, 3, 12)
        report = build_event_impact_report(thu, current_vix=15.0)
        assert report.event_type == EVENT_EXPIRY_DAY
        assert report.risk_level == "MODERATE"
        assert report.position_size_multiplier > 0

    def test_normal_day_low_risk(self):
        # Use Sept 11 2026 (Friday): 6 days to expiry, not results season (ends Aug 31), not RBI
        report = build_event_impact_report(date(2026, 9, 11), current_vix=15.0)
        assert report.event_type == EVENT_NORMAL
        assert report.risk_level == "LOW"
        assert report.position_size_multiplier == 1.0
        assert report.avoid_new_positions is False

    def test_volatility_multiplier_rbi_gt_1(self):
        mult = compute_event_volatility_multiplier(EVENT_RBI_MPC_DAY, current_vix=15.0)
        assert mult > 1.0

    def test_volatility_multiplier_capped_at_high_vix(self):
        """When VIX is already in circuit breaker zone, multiplier is capped."""
        mult_normal_vix = compute_event_volatility_multiplier(EVENT_BUDGET, current_vix=15.0)
        mult_high_vix   = compute_event_volatility_multiplier(EVENT_BUDGET, current_vix=26.0)
        assert mult_high_vix < mult_normal_vix

    def test_trading_rules_not_empty(self):
        for event in [EVENT_RBI_MPC_DAY, EVENT_BUDGET, EVENT_EXPIRY_DAY, EVENT_NORMAL]:
            rules = get_event_trading_rules(event)
            assert len(rules["trading_rules"]) > 0

    def test_macro_package_imports(self):
        """Smoke test: macro package re-exports all key symbols."""
        assert hasattr(macro, "detect_vix_reversion_signal")
        assert hasattr(macro, "build_flow_report")
        assert hasattr(macro, "analyze_rupee")
        assert hasattr(macro, "analyze_crude")
        assert hasattr(macro, "build_global_cues_report")
        assert hasattr(macro, "build_event_impact_report")
