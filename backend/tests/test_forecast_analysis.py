"""
Unit and integration tests for Task 4:
Forecast selection policies, temporal alignment, accuracy metrics, and the analysis endpoint.

Covers all 15 required test dimensions:
 1. Forecast published exactly at the cutoff is eligible.
 2. Forecast published one second after the cutoff is rejected.
 3. A later forecast after the cutoff is never selected.
 4. Multiple forecast revisions are selected correctly (latest eligible; tie-break by highest generation).
 5. Rolling lead-time selection works at interval level.
 6. Latest-before-delivery policy never selects a post-delivery forecast.
 7. Two half-hourly actuals produce the correct hourly arithmetic mean.
 8. Missing one half-hourly actual makes that hourly actual incomplete.
 9. MW values are not summed or doubled.
10. Positive bias means over-forecasting.
11. MAE, RMSE, bias and MAPE match hand-calculated examples.
12. Zero actual values are excluded from MAPE without breaking other metrics.
13. No valid pairs produce null metrics rather than zero.
14. Coverage and missing counts are correct.
15. Invalid policy, date range and lead-time inputs are rejected (service ValueError and HTTP 400).
"""

import math
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app
from schemas import (
    ActualWindRecord,
    ForecastPolicy,
    ForecastWindRecord,
    IntervalStatus,
)
from services.elexon_client import ElexonAPIError, ElexonConnectionError
from services.forecast_analysis import (
    align_hourly_actual,
    analyze_wind_forecasts,
    calculate_accuracy_metrics,
    compute_interval_cutoff,
    parse_day_ahead_cutoff_time,
    select_forecast_for_interval,
)


# ===========================================================================
# Fixtures and Helpers
# ===========================================================================

def make_forecast(
    start_time: datetime,
    publish_time: datetime,
    generation: int,
) -> ForecastWindRecord:
    """Helper to construct a validated ForecastWindRecord."""
    return ForecastWindRecord(
        dataset="WINDFOR",
        start_time=start_time,
        publish_time=publish_time,
        generation=generation,
    )


def make_actual(
    start_time: datetime,
    settlement_date: str,
    settlement_period: int,
    generation: int,
) -> ActualWindRecord:
    """Helper to construct a validated ActualWindRecord."""
    return ActualWindRecord(
        dataset="FUELHH",
        start_time=start_time,
        settlement_date=settlement_date,
        settlement_period=settlement_period,
        fuel_type="WIND",
        generation=generation,
    )


# ===========================================================================
# 1. Forecast Selection Policy Unit Tests (Tests 1 - 6)
# ===========================================================================

class TestForecastSelectionPolicies:
    """Tests for policy-based cutoff calculation and forecast selection."""

    def test_forecast_published_exactly_at_cutoff_is_eligible(self):
        """Test 1: A forecast published exactly at the cutoff (<= cutoff) must be eligible."""
        interval_start = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        cutoff = datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)

        f_exact = make_forecast(interval_start, cutoff, 12000)
        selected = select_forecast_for_interval([f_exact], cutoff)

        assert selected is not None
        assert selected.publish_time == cutoff
        assert selected.generation == 12000

    def test_forecast_published_one_second_after_cutoff_is_rejected(self):
        """Test 2: A forecast published one second after cutoff (> cutoff) must be rejected."""
        interval_start = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        cutoff = datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)

        f_late = make_forecast(
            interval_start,
            cutoff + timedelta(seconds=1),
            15000,
        )
        selected = select_forecast_for_interval([f_late], cutoff)

        assert selected is None

    def test_later_forecast_after_cutoff_is_never_selected(self):
        """Test 3: When eligible and late forecasts exist, the late forecast is never chosen."""
        interval_start = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        cutoff = datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)

        f_eligible = make_forecast(
            interval_start,
            datetime(2025, 12, 31, 11, 0, 0, tzinfo=timezone.utc),
            10000,
        )
        f_late = make_forecast(
            interval_start,
            datetime(2025, 12, 31, 13, 0, 0, tzinfo=timezone.utc),
            18000,  # even if newer/higher, must be ignored
        )

        selected = select_forecast_for_interval([f_eligible, f_late], cutoff)

        assert selected is not None
        assert selected.publish_time == f_eligible.publish_time
        assert selected.generation == 10000

    def test_multiple_revisions_selected_correctly(self):
        """Test 4: Out of multiple revisions prior to cutoff, the latest one is selected."""
        interval_start = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        cutoff = datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)

        r1 = make_forecast(interval_start, datetime(2025, 12, 30, 9, 0, tzinfo=timezone.utc), 8000)
        r2 = make_forecast(interval_start, datetime(2025, 12, 31, 6, 0, tzinfo=timezone.utc), 11000)
        r3 = make_forecast(interval_start, datetime(2025, 12, 31, 11, 30, tzinfo=timezone.utc), 13500)
        r4_post_cutoff = make_forecast(interval_start, datetime(2025, 12, 31, 14, 0, tzinfo=timezone.utc), 16000)

        selected = select_forecast_for_interval([r1, r2, r3, r4_post_cutoff], cutoff)

        assert selected is not None
        assert selected.publish_time == r3.publish_time
        assert selected.generation == 13500

    def test_deterministic_tie_breaking_same_publish_time(self):
        """Test 4b: If two forecasts share the exact same publishTime, tie-break by higher generation."""
        interval_start = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        cutoff = datetime(2025, 12, 31, 12, 0, 0, tzinfo=timezone.utc)
        same_time = datetime(2025, 12, 31, 11, 0, 0, tzinfo=timezone.utc)

        f_lower = make_forecast(interval_start, same_time, 12000)
        f_higher = make_forecast(interval_start, same_time, 14500)

        # Order independent
        sel1 = select_forecast_for_interval([f_lower, f_higher], cutoff)
        sel2 = select_forecast_for_interval([f_higher, f_lower], cutoff)

        assert sel1 is not None and sel2 is not None
        assert sel1.generation == 14500
        assert sel2.generation == 14500

    def test_rolling_lead_time_selection_at_interval_level(self):
        """Test 5: Rolling lead-time policy sets cutoff = interval_start - lead_time."""
        interval_start = datetime(2026, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
        lead_time = 4.0  # 4 hours lead time
        cutoff = compute_interval_cutoff(interval_start, "rolling", lead_time_hours=lead_time)

        expected_cutoff = datetime(2026, 1, 1, 11, 0, 0, tzinfo=timezone.utc)
        assert cutoff == expected_cutoff

        # Eligible: published at 10:59
        f_eligible = make_forecast(
            interval_start,
            datetime(2026, 1, 1, 10, 59, 0, tzinfo=timezone.utc),
            12000,
        )
        # Ineligible: published at 11:01 (only 3h59m lead time)
        f_ineligible = make_forecast(
            interval_start,
            datetime(2026, 1, 1, 11, 1, 0, tzinfo=timezone.utc),
            13000,
        )

        selected = select_forecast_for_interval([f_eligible, f_ineligible], cutoff)
        assert selected is not None
        assert selected.generation == 12000

    def test_latest_before_delivery_policy_never_selects_post_delivery(self):
        """Test 6: Latest-before-delivery policy rejects any forecast published after startTime."""
        interval_start = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        cutoff = compute_interval_cutoff(interval_start, "latest_before_delivery")

        assert cutoff == interval_start

        f_on_time = make_forecast(interval_start, datetime(2026, 1, 1, 9, 45, tzinfo=timezone.utc), 14000)
        f_at_delivery = make_forecast(interval_start, interval_start, 14200)
        f_post_delivery = make_forecast(interval_start, datetime(2026, 1, 1, 10, 15, tzinfo=timezone.utc), 15000)

        selected = select_forecast_for_interval([f_on_time, f_at_delivery, f_post_delivery], cutoff)
        assert selected is not None
        assert selected.publish_time == interval_start
        assert selected.generation == 14200


# ===========================================================================
# 2. Temporal Alignment Unit Tests (Tests 7 - 9)
# ===========================================================================

class TestTemporalAlignment:
    """Tests for aligning half-hourly actual FUELHH readings to hourly forecast intervals."""

    def test_two_half_hourly_actuals_produce_arithmetic_mean(self):
        """Test 7: Two half-hourly actuals produce their arithmetic mean (MW)."""
        interval_start = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        t1 = interval_start
        t2 = interval_start + timedelta(minutes=30)

        r1 = make_actual(t1, "2026-01-01", 29, 10000)
        r2 = make_actual(t2, "2026-01-01", 30, 12000)

        actuals_map = {t1: r1, t2: r2}
        hourly_actual, half_hourly_vals = align_hourly_actual(interval_start, actuals_map)

        assert hourly_actual == 11000.0
        assert half_hourly_vals == [10000.0, 12000.0]

    def test_missing_one_half_hourly_actual_makes_hour_incomplete(self):
        """Test 8: If either period 1 or period 2 is missing, hourly actual is None."""
        interval_start = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        t1 = interval_start
        t2 = interval_start + timedelta(minutes=30)

        # Case A: missing period 2
        r1 = make_actual(t1, "2026-01-01", 29, 10000)
        hourly_actual, vals = align_hourly_actual(interval_start, {t1: r1})
        assert hourly_actual is None
        assert vals == [10000.0, None]

        # Case B: missing period 1
        r2 = make_actual(t2, "2026-01-01", 30, 12000)
        hourly_actual_b, vals_b = align_hourly_actual(interval_start, {t2: r2})
        assert hourly_actual_b is None
        assert vals_b == [None, 12000.0]

    def test_mw_values_are_not_summed_or_doubled(self):
        """Test 9: Verify MW values are arithmetic mean, NOT summed (22000) or doubled."""
        interval_start = datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        t1 = interval_start
        t2 = interval_start + timedelta(minutes=30)

        r1 = make_actual(t1, "2026-01-01", 17, 10000)
        r2 = make_actual(t2, "2026-01-01", 18, 12000)

        hourly_actual, _ = align_hourly_actual(interval_start, {t1: r1, t2: r2})

        # MUST be (10000 + 12000) / 2 = 11000.0 MW
        assert hourly_actual != 22000.0  # Not summed
        assert hourly_actual != 24000.0  # Not doubled
        assert hourly_actual == 11000.0


# ===========================================================================
# 3. Accuracy Metrics Unit Tests (Tests 10 - 14)
# ===========================================================================

class TestAccuracyMetrics:
    """Tests for MAE, RMSE, bias, MAPE, coverage, and missing counts."""

    def test_positive_bias_means_over_forecasting(self):
        """Test 10: Signed error is forecast - actual. Positive bias = over-forecasting."""
        # Forecast 12,000 MW, Actual 10,000 MW -> Error = +2,000 MW (over-forecasting)
        pairs = [(12000.0, 10000.0)]
        metrics = calculate_accuracy_metrics(pairs)

        assert metrics.bias == 2000.0
        assert metrics.mae == 2000.0
        assert metrics.rmse == 2000.0

        # Under-forecasting case: Forecast 8,000 MW, Actual 10,000 MW -> Error = -2,000 MW
        pairs_under = [(8000.0, 10000.0)]
        metrics_under = calculate_accuracy_metrics(pairs_under)
        assert metrics_under.bias == -2000.0

    def test_metrics_match_hand_calculated_examples(self):
        """
        Test 11: Verify hand-calculated values.
        Pair 1: Forecast = 12000, Actual = 10000 -> error = +2000, abs = 2000, ape = 20.0%
        Pair 2: Forecast = 7000,  Actual = 8000  -> error = -1000, abs = 1000, ape = 12.5%

        Expected:
          MAE = (2000 + 1000) / 2 = 1500.0
          RMSE = sqrt((2000^2 + (-1000)^2) / 2) = sqrt(5000000 / 2) = sqrt(2500000) = 1581.14
          Bias = (+2000 - 1000) / 2 = +500.0
          MAPE = (20.0 + 12.5) / 2 = 16.25%
        """
        pairs = [
            (12000.0, 10000.0),
            (7000.0, 8000.0),
        ]
        metrics = calculate_accuracy_metrics(pairs)

        assert metrics.mae == 1500.0
        assert metrics.rmse == 1581.14
        assert metrics.bias == 500.0
        assert metrics.mape == 16.25

    def test_zero_actual_values_excluded_from_mape_without_breaking_other_metrics(self):
        """Test 12: Zero actual values are excluded from MAPE, other metrics remain valid."""
        pairs = [
            (500.0, 0.0),       # Actual is 0 -> excluded from MAPE denominator
            (1100.0, 1000.0),   # Error = 100, APE = 10.0%
        ]
        metrics = calculate_accuracy_metrics(pairs)

        # MAE: (|500 - 0| + |1100 - 1000|) / 2 = (500 + 100) / 2 = 300.0
        assert metrics.mae == 300.0
        # Bias: (500 + 100) / 2 = 300.0
        assert metrics.bias == 300.0
        # RMSE: sqrt((500^2 + 100^2) / 2) = sqrt(260000 / 2) = sqrt(130000) = 360.56
        assert metrics.rmse == 360.56
        # MAPE: evaluated ONLY on second pair -> 10.0%
        assert metrics.mape == 10.0

    def test_no_valid_pairs_produce_null_metrics(self):
        """Test 13: When there are no valid pairs, metrics return None (null), not 0.0."""
        empty_pairs = []
        metrics = calculate_accuracy_metrics(empty_pairs)

        assert metrics.mae is None
        assert metrics.rmse is None
        assert metrics.bias is None
        assert metrics.mape is None

    def test_coverage_and_missing_counts(self):
        """Test 14: analyze_wind_forecasts accurately tracks coverage and missing counts."""
        start_date = date(2026, 1, 1)
        end_date = date(2026, 1, 1)  # 1 day = 24 expected intervals

        # Create actuals for all 24 hours
        actual_records = []
        for h in range(24):
            t1 = datetime(2026, 1, 1, h, 0, tzinfo=timezone.utc)
            t2 = datetime(2026, 1, 1, h, 30, tzinfo=timezone.utc)
            actual_records.append(make_actual(t1, "2026-01-01", h * 2 + 1, 10000))
            if h != 23:  # Hour 23 has missing second half-hour -> incomplete actual!
                actual_records.append(make_actual(t2, "2026-01-01", h * 2 + 2, 10000))

        # Create forecasts for only hours 0..19 (hours 20..23 missing forecasts)
        cutoff = datetime(2025, 12, 31, 12, 0, tzinfo=timezone.utc)
        forecast_records = []
        for h in range(20):
            t = datetime(2026, 1, 1, h, 0, tzinfo=timezone.utc)
            forecast_records.append(make_forecast(t, cutoff - timedelta(hours=1), 10500))

        response = analyze_wind_forecasts(
            start_date=start_date,
            end_date=end_date,
            actual_records=actual_records,
            forecast_records=forecast_records,
            policy="day_ahead",
        )

        assert response.expected_interval_count == 24
        # Hours 0..19 are matched (20 hours)
        assert response.matched_interval_count == 20
        # Hours 20..23 have missing forecast (4 hours)
        assert response.missing_forecast_count == 4
        # Hour 23 has incomplete actual (1 hour)
        assert response.missing_actual_count == 1
        # Coverage: 20 / 24 = 0.8333
        assert response.coverage_ratio == 0.8333
        assert response.coverage_percentage == 83.33


# ===========================================================================
# 4. Input Validation & Error Handling (Test 15)
# ===========================================================================

class TestValidationAndErrorHandling:
    """Test 15: Validation rejections in service functions and API endpoints."""

    def test_service_rejects_invalid_date_range(self):
        """Service raises ValueError when start_date > end_date."""
        with pytest.raises(ValueError, match="start_date .* must not be after end_date"):
            analyze_wind_forecasts(
                start_date=date(2026, 1, 5),
                end_date=date(2026, 1, 1),
                actual_records=[],
                forecast_records=[],
            )

    def test_service_rejects_unknown_policy(self):
        """Service raises ValueError for unsupported policy name."""
        with pytest.raises(ValueError, match="Unsupported policy"):
            compute_interval_cutoff(
                datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
                policy="magical_policy",
            )

    def test_service_rejects_rolling_without_positive_lead_time(self):
        """Service raises ValueError when rolling policy has non-positive or None lead time."""
        dt = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        with pytest.raises(ValueError, match="lead_time_hours must be a positive number"):
            compute_interval_cutoff(dt, policy="rolling", lead_time_hours=None)

        with pytest.raises(ValueError, match="lead_time_hours must be a positive number"):
            compute_interval_cutoff(dt, policy="rolling", lead_time_hours=0.0)

        with pytest.raises(ValueError, match="lead_time_hours must be a positive number"):
            compute_interval_cutoff(dt, policy="rolling", lead_time_hours=-4.0)

    def test_service_rejects_invalid_cutoff_time(self):
        """Service raises ValueError for malformed or out-of-range day-ahead cutoff times."""
        with pytest.raises(ValueError, match="Invalid day-ahead cutoff time format"):
            parse_day_ahead_cutoff_time("noon")

        with pytest.raises(ValueError, match="Cutoff time out of range"):
            parse_day_ahead_cutoff_time("25:00")

        with pytest.raises(ValueError, match="Cutoff time out of range"):
            parse_day_ahead_cutoff_time("12:60")


# ===========================================================================
# 5. Full HTTP Endpoint Tests with Mocked Elexon Client
# ===========================================================================

class TestAnalysisEndpointHTTP:
    """HTTP integration tests for GET /api/v1/wind/analysis using FastAPI TestClient."""

    def test_analysis_endpoint_success(self):
        """Valid analysis request returns 200 with structured AnalysisResponse."""
        client = TestClient(app)

        mock_actuals = [
            {
                "dataset": "FUELHH",
                "startTime": "2026-01-01T00:00:00Z",
                "settlementDate": "2026-01-01",
                "settlementPeriod": 1,
                "fuelType": "WIND",
                "generation": 10000,
            },
            {
                "dataset": "FUELHH",
                "startTime": "2026-01-01T00:30:00Z",
                "settlementDate": "2026-01-01",
                "settlementPeriod": 2,
                "fuelType": "WIND",
                "generation": 12000,
            },
        ]
        mock_forecasts = [
            {
                "dataset": "WINDFOR",
                "startTime": "2026-01-01T00:00:00Z",
                "publishTime": "2025-12-31T11:00:00Z",
                "generation": 11500,
            }
        ]

        with patch("main.ElexonClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_wind_actuals.return_value = mock_actuals
            mock_client.get_wind_forecasts.return_value = mock_forecasts
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            resp = client.get(
                "/api/v1/wind/analysis?start_date=2026-01-01&end_date=2026-01-01&policy=day_ahead"
            )

            assert resp.status_code == 200
            body = resp.json()
            assert body["start_date"] == "2026-01-01"
            assert body["end_date"] == "2026-01-01"
            assert body["policy"] == "day_ahead"
            assert body["expected_interval_count"] == 24
            assert body["matched_interval_count"] == 1
            assert len(body["records"]) == 24

            # First hour: forecast = 11500, actual = (10000 + 12000)/2 = 11000
            # error = 11500 - 11000 = +500.0 (over-forecasting)
            r0 = body["records"][0]
            assert r0["status"] == "MATCHED"
            assert r0["forecast_generation"] == 11500.0
            assert r0["actual_generation"] == 11000.0
            assert r0["error"] == 500.0
            assert r0["absolute_error"] == 500.0

            # Metrics
            assert body["metrics"]["mae"] == 500.0
            assert body["metrics"]["bias"] == 500.0
            assert body["metrics"]["rmse"] == 500.0

    def test_analysis_endpoint_rolling_policy(self):
        """Rolling policy with lead_time_hours is accepted."""
        client = TestClient(app)

        with patch("main.ElexonClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_wind_actuals.return_value = []
            mock_client.get_wind_forecasts.return_value = []
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            resp = client.get(
                "/api/v1/wind/analysis?start_date=2026-01-01&end_date=2026-01-01"
                "&policy=rolling&lead_time_hours=24"
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["policy"] == "rolling"
            assert body["lead_time_hours"] == 24.0

    def test_analysis_endpoint_invalid_policy_returns_400(self):
        """Unknown policy name returns 400 Bad Request."""
        client = TestClient(app)
        resp = client.get(
            "/api/v1/wind/analysis?start_date=2026-01-01&end_date=2026-01-01&policy=invalid_pol"
        )
        assert resp.status_code == 400
        assert "Invalid policy 'invalid_pol'" in resp.json()["detail"]

    def test_analysis_endpoint_rolling_without_lead_time_returns_400(self):
        """Rolling policy without lead_time_hours returns 400 Bad Request."""
        client = TestClient(app)
        resp = client.get(
            "/api/v1/wind/analysis?start_date=2026-01-01&end_date=2026-01-01&policy=rolling"
        )
        assert resp.status_code == 400
        assert "lead_time_hours must be a positive number" in resp.json()["detail"]

    def test_analysis_endpoint_elexon_error_returns_502(self):
        """Upstream Elexon errors return 502 Bad Gateway without exposing stack trace."""
        client = TestClient(app)
        with patch("main.ElexonClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get_wind_actuals.side_effect = ElexonConnectionError("Network down")
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client_cls.return_value = mock_client

            resp = client.get(
                "/api/v1/wind/analysis?start_date=2026-01-01&end_date=2026-01-01"
            )
            assert resp.status_code == 502
            assert "Could not connect to Elexon API" in resp.json()["detail"]
