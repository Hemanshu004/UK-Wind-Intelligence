"""
Tests for the UK Wind Forecast Analytics backend.

Covers:
  - Existing /health endpoint (regression)
  - Elexon client with mocked HTTP responses
  - Wind data validation and normalisation
  - API endpoints with mocked Elexon data
  - Error handling (invalid dates, Elexon errors, timeouts)

All tests use mocked HTTP responses so they do NOT depend on the live
Elexon API.  Live integration checks are separate (see test_live_integration
at the bottom — only runs when explicitly requested).
"""

import sys
import os
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import httpx

# Ensure the backend directory is on the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from services.wind_data import (
    normalise_actual_record,
    normalise_forecast_record,
    normalise_actuals,
    normalise_forecasts,
    parse_utc_timestamp,
    parse_generation,
    ValidationError,
)
from services.elexon_client import (
    ElexonClient,
    ElexonAPIError,
    ElexonConnectionError,
)


# ---------------------------------------------------------------------------
# Test client fixture
# ---------------------------------------------------------------------------

client = TestClient(app)


# ---------------------------------------------------------------------------
# Sample data matching verified Elexon response structure
# (from docs/elexon-api-investigation.md §4.3 and §5.3)
# ---------------------------------------------------------------------------

SAMPLE_FUELHH_RECORDS = [
    {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T00:30:00Z",
        "startTime": "2026-01-01T00:00:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 1,
        "fuelType": "WIND",
        "generation": 13756,
    },
    {
        "dataset": "FUELHH",
        "publishTime": "2026-01-01T01:00:00Z",
        "startTime": "2026-01-01T00:30:00Z",
        "settlementDate": "2026-01-01",
        "settlementPeriod": 2,
        "fuelType": "WIND",
        "generation": 13873,
    },
]

SAMPLE_WINDFOR_RECORDS = [
    {
        "dataset": "WINDFOR",
        "publishTime": "2025-12-30T02:30:00Z",
        "startTime": "2026-01-01T12:00:00Z",
        "generation": 19192,
    },
    {
        "dataset": "WINDFOR",
        "publishTime": "2025-12-30T04:30:00Z",
        "startTime": "2026-01-01T12:00:00Z",
        "generation": 19227,
    },
    {
        "dataset": "WINDFOR",
        "publishTime": "2025-12-31T11:30:00Z",
        "startTime": "2026-01-01T12:00:00Z",
        "generation": 19725,
    },
    {
        "dataset": "WINDFOR",
        "publishTime": "2026-01-01T07:30:00Z",
        "startTime": "2026-01-01T12:00:00Z",
        "generation": 20127,
    },
]


# ===================================================================
# 1. HEALTH ENDPOINT (regression from Task 1)
# ===================================================================

class TestHealthEndpoint:
    """Verify that the existing /health endpoint still works."""

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_body(self):
        response = client.get("/health")
        body = response.json()
        assert body["status"] == "ok"
        assert body["service"] == "UK Wind Forecast Analytics API"
        assert body["version"] == "0.1.0"


# ===================================================================
# 2. WIND DATA VALIDATION — parse_utc_timestamp
# ===================================================================

class TestParseUtcTimestamp:
    """Test timestamp parsing for Elexon ISO-8601 UTC strings."""

    def test_valid_z_suffix(self):
        result = parse_utc_timestamp("2026-01-01T00:00:00Z", "test")
        assert result == datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_valid_offset_suffix(self):
        result = parse_utc_timestamp("2026-01-01T12:30:00+00:00", "test")
        assert result == datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc)

    def test_none_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            parse_utc_timestamp(None, "startTime")
        assert exc_info.value.field == "startTime"

    def test_not_a_string_raises(self):
        with pytest.raises(ValidationError):
            parse_utc_timestamp(12345, "test")

    def test_invalid_format_raises(self):
        with pytest.raises(ValidationError):
            parse_utc_timestamp("not-a-date", "test")

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError):
            parse_utc_timestamp("", "test")


# ===================================================================
# 3. WIND DATA VALIDATION — parse_generation
# ===================================================================

class TestParseGeneration:
    """Test generation value validation."""

    def test_valid_integer(self):
        assert parse_generation(13756) == 13756

    def test_valid_integer_string(self):
        """API might return int or string; both should work."""
        assert parse_generation("13756") == 13756

    def test_zero_is_valid(self):
        assert parse_generation(0) == 0

    def test_none_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            parse_generation(None)
        assert exc_info.value.field == "generation"

    def test_negative_raises(self):
        with pytest.raises(ValidationError):
            parse_generation(-100)

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError):
            parse_generation("abc")


# ===================================================================
# 4. WIND DATA NORMALISATION — ActualWindRecord
# ===================================================================

class TestNormaliseActualRecord:
    """Test normalisation of raw FUELHH records."""

    def test_valid_record(self):
        record = normalise_actual_record(SAMPLE_FUELHH_RECORDS[0])
        assert record.dataset == "FUELHH"
        assert record.fuel_type == "WIND"
        assert record.generation == 13756
        assert record.settlement_period == 1
        assert record.settlement_date == "2026-01-01"
        assert record.start_time == datetime(
            2026, 1, 1, 0, 0, tzinfo=timezone.utc
        )

    def test_missing_dataset_raises(self):
        bad = {**SAMPLE_FUELHH_RECORDS[0]}
        del bad["dataset"]
        with pytest.raises(ValidationError) as exc_info:
            normalise_actual_record(bad)
        assert exc_info.value.field == "dataset"

    def test_missing_fuel_type_raises(self):
        bad = {**SAMPLE_FUELHH_RECORDS[0]}
        del bad["fuelType"]
        with pytest.raises(ValidationError):
            normalise_actual_record(bad)

    def test_missing_start_time_raises(self):
        bad = {**SAMPLE_FUELHH_RECORDS[0]}
        del bad["startTime"]
        with pytest.raises(ValidationError):
            normalise_actual_record(bad)

    def test_missing_generation_raises(self):
        bad = {**SAMPLE_FUELHH_RECORDS[0]}
        del bad["generation"]
        with pytest.raises(ValidationError):
            normalise_actual_record(bad)

    def test_invalid_settlement_period_raises(self):
        bad = {**SAMPLE_FUELHH_RECORDS[0], "settlementPeriod": 99}
        with pytest.raises(ValidationError) as exc_info:
            normalise_actual_record(bad)
        assert exc_info.value.field == "settlementPeriod"

    def test_missing_settlement_date_raises(self):
        bad = {**SAMPLE_FUELHH_RECORDS[0]}
        del bad["settlementDate"]
        with pytest.raises(ValidationError):
            normalise_actual_record(bad)

    def test_publish_time_optional(self):
        """publishTime can be missing — record should still validate."""
        raw = {**SAMPLE_FUELHH_RECORDS[0]}
        del raw["publishTime"]
        record = normalise_actual_record(raw)
        assert record.publish_time is None

    def test_batch_normalise(self):
        records = normalise_actuals(SAMPLE_FUELHH_RECORDS)
        assert len(records) == 2
        assert records[0].settlement_period == 1
        assert records[1].settlement_period == 2


# ===================================================================
# 5. WIND DATA NORMALISATION — ForecastWindRecord
# ===================================================================

class TestNormaliseForecastRecord:
    """Test normalisation of raw WINDFOR records."""

    def test_valid_record(self):
        record = normalise_forecast_record(SAMPLE_WINDFOR_RECORDS[0])
        assert record.dataset == "WINDFOR"
        assert record.generation == 19192
        assert record.start_time == datetime(
            2026, 1, 1, 12, 0, tzinfo=timezone.utc
        )
        assert record.publish_time == datetime(
            2025, 12, 30, 2, 30, tzinfo=timezone.utc
        )

    def test_missing_publish_time_raises(self):
        bad = {**SAMPLE_WINDFOR_RECORDS[0]}
        del bad["publishTime"]
        with pytest.raises(ValidationError):
            normalise_forecast_record(bad)

    def test_missing_start_time_raises(self):
        bad = {**SAMPLE_WINDFOR_RECORDS[0]}
        del bad["startTime"]
        with pytest.raises(ValidationError):
            normalise_forecast_record(bad)

    def test_missing_generation_raises(self):
        bad = {**SAMPLE_WINDFOR_RECORDS[0]}
        del bad["generation"]
        with pytest.raises(ValidationError):
            normalise_forecast_record(bad)

    def test_multiple_revisions_preserved(self):
        """All forecast revisions for the same delivery interval are kept."""
        records = normalise_forecasts(SAMPLE_WINDFOR_RECORDS)
        assert len(records) == 4
        # All have the same startTime (delivery interval)
        start_times = {r.start_time for r in records}
        assert len(start_times) == 1
        # But different publish times
        publish_times = [r.publish_time for r in records]
        assert len(set(publish_times)) == 4

    def test_batch_normalise(self):
        records = normalise_forecasts(SAMPLE_WINDFOR_RECORDS)
        assert len(records) == 4


# ===================================================================
# 6. API ENDPOINT — /api/v1/wind/actuals (mocked Elexon)
# ===================================================================

class TestActualsEndpoint:
    """Test the actuals endpoint with mocked Elexon responses."""

    @patch("main.ElexonClient")
    def test_valid_request(self, MockClient):
        """A valid date range returns normalised records."""
        mock_instance = AsyncMock()
        mock_instance.get_wind_actuals.return_value = SAMPLE_FUELHH_RECORDS
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/actuals",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["start_date"] == "2026-01-01"
        assert body["end_date"] == "2026-01-01"
        assert body["record_count"] == 2
        assert len(body["records"]) == 2
        # Check record shape
        rec = body["records"][0]
        assert "start_time" in rec
        assert "generation" in rec
        assert "fuel_type" in rec
        assert "settlement_period" in rec

    def test_missing_start_date(self):
        response = client.get(
            "/api/v1/wind/actuals",
            params={"end_date": "2026-01-01"},
        )
        assert response.status_code == 422  # FastAPI validation

    def test_invalid_date_format(self):
        response = client.get(
            "/api/v1/wind/actuals",
            params={"start_date": "01-01-2026", "end_date": "2026-01-01"},
        )
        assert response.status_code == 400

    def test_start_after_end(self):
        response = client.get(
            "/api/v1/wind/actuals",
            params={"start_date": "2026-01-10", "end_date": "2026-01-01"},
        )
        assert response.status_code == 400

    @patch("main.ElexonClient")
    def test_elexon_api_error(self, MockClient):
        """If Elexon returns an error, we should get 502."""
        mock_instance = AsyncMock()
        mock_instance.get_wind_actuals.side_effect = ElexonAPIError(
            400, "Bad request"
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/actuals",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )
        assert response.status_code == 502

    @patch("main.ElexonClient")
    def test_elexon_connection_error(self, MockClient):
        """If Elexon cannot be reached, we should get 502."""
        mock_instance = AsyncMock()
        mock_instance.get_wind_actuals.side_effect = ElexonConnectionError(
            "Connection refused"
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/actuals",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )
        assert response.status_code == 502

    @patch("main.ElexonClient")
    def test_validation_error_in_response(self, MockClient):
        """If Elexon returns malformed data, we get 502 with detail."""
        bad_records = [{"dataset": "FUELHH"}]  # missing required fields
        mock_instance = AsyncMock()
        mock_instance.get_wind_actuals.return_value = bad_records
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/actuals",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )
        assert response.status_code == 502
        assert "invalid data" in response.json()["detail"].lower()


# ===================================================================
# 7. API ENDPOINT — /api/v1/wind/forecasts (mocked Elexon)
# ===================================================================

class TestForecastsEndpoint:
    """Test the forecasts endpoint with mocked Elexon responses."""

    @patch("main.ElexonClient")
    def test_valid_request(self, MockClient):
        """A valid date range returns normalised forecast records."""
        mock_instance = AsyncMock()
        mock_instance.get_wind_forecasts.return_value = SAMPLE_WINDFOR_RECORDS
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["start_date"] == "2026-01-01"
        assert body["end_date"] == "2026-01-01"
        assert body["record_count"] == 4
        assert len(body["records"]) == 4
        # All four revisions preserved
        rec = body["records"][0]
        assert "start_time" in rec
        assert "publish_time" in rec
        assert "generation" in rec

    @patch("main.ElexonClient")
    def test_multiple_revisions_preserved(self, MockClient):
        """Multiple forecasts for the same delivery hour are all returned."""
        mock_instance = AsyncMock()
        mock_instance.get_wind_forecasts.return_value = SAMPLE_WINDFOR_RECORDS
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )

        body = response.json()
        # All four records target the same delivery hour but have
        # different publish times
        publish_times = [r["publish_time"] for r in body["records"]]
        assert len(set(publish_times)) == 4

    @patch("main.ElexonClient")
    def test_sorted_by_delivery_then_publish(self, MockClient):
        """Records are sorted by (start_time, publish_time)."""
        mock_instance = AsyncMock()
        mock_instance.get_wind_forecasts.return_value = SAMPLE_WINDFOR_RECORDS
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )

        body = response.json()
        publish_times = [r["publish_time"] for r in body["records"]]
        assert publish_times == sorted(publish_times)

    def test_missing_end_date(self):
        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-01"},
        )
        assert response.status_code == 422

    def test_invalid_date_format(self):
        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026/01/01", "end_date": "2026-01-01"},
        )
        assert response.status_code == 400

    def test_start_after_end(self):
        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-31", "end_date": "2026-01-01"},
        )
        assert response.status_code == 400

    @patch("main.ElexonClient")
    def test_elexon_api_error(self, MockClient):
        mock_instance = AsyncMock()
        mock_instance.get_wind_forecasts.side_effect = ElexonAPIError(
            500, "Server error"
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )
        assert response.status_code == 502

    @patch("main.ElexonClient")
    def test_elexon_connection_error(self, MockClient):
        mock_instance = AsyncMock()
        mock_instance.get_wind_forecasts.side_effect = ElexonConnectionError(
            "Timed out"
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )
        assert response.status_code == 502


# ===================================================================
# 8. ELEXON CLIENT — unit tests with mocked httpx
# ===================================================================

class TestElexonClientMocked:
    """Unit tests for the ElexonClient with mocked httpx responses."""

    @pytest.mark.asyncio
    async def test_get_wind_actuals_success(self):
        """Successful fetch returns the parsed JSON list."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = SAMPLE_FUELHH_RECORDS

        async with ElexonClient() as elx:
            elx._client = AsyncMock()
            elx._client.get = AsyncMock(return_value=mock_response)

            from datetime import date
            result = await elx.get_wind_actuals(
                settlement_date_from=date(2026, 1, 1),
                settlement_date_to=date(2026, 1, 1),
            )

        assert len(result) == 2
        assert result[0]["fuelType"] == "WIND"

    @pytest.mark.asyncio
    async def test_api_error_raises(self):
        """Non-200 response raises ElexonAPIError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "title": "Bad request",
            "status": 400,
        }
        mock_response.text = "Bad request"

        async with ElexonClient() as elx:
            elx._client = AsyncMock()
            elx._client.get = AsyncMock(return_value=mock_response)

            from datetime import date
            with pytest.raises(ElexonAPIError) as exc_info:
                await elx.get_wind_actuals(
                    settlement_date_from=date(2026, 1, 1),
                    settlement_date_to=date(2026, 1, 1),
                )
            assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_connection_error_retries(self):
        """Connection errors are retried up to MAX_RETRIES times."""
        async with ElexonClient() as elx:
            elx._client = AsyncMock()
            elx._client.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )

            from datetime import date
            with pytest.raises(ElexonConnectionError):
                await elx.get_wind_actuals(
                    settlement_date_from=date(2026, 1, 1),
                    settlement_date_to=date(2026, 1, 1),
                )
            # Should have been called 1 + MAX_RETRIES = 3 times
            assert elx._client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_timeout_retries(self):
        """Timeout errors are retried."""
        async with ElexonClient() as elx:
            elx._client = AsyncMock()
            elx._client.get = AsyncMock(
                side_effect=httpx.ReadTimeout("Read timed out")
            )

            from datetime import date
            with pytest.raises(ElexonConnectionError):
                await elx.get_wind_actuals(
                    settlement_date_from=date(2026, 1, 1),
                    settlement_date_to=date(2026, 1, 1),
                )
            assert elx._client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_non_list_response_raises(self):
        """If stream endpoint returns a dict instead of list, error is raised."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}  # dict, not list

        async with ElexonClient() as elx:
            elx._client = AsyncMock()
            elx._client.get = AsyncMock(return_value=mock_response)

            from datetime import date
            with pytest.raises(ElexonAPIError) as exc_info:
                await elx.get_wind_actuals(
                    settlement_date_from=date(2026, 1, 1),
                    settlement_date_to=date(2026, 1, 1),
                )
            assert "Expected JSON array" in str(exc_info.value)


# ===================================================================
# 9. INCLUSIVE DATE HANDLING
# ===================================================================

class TestInclusiveDateHandling:
    """Verify that both start and end dates are inclusive."""

    @patch("main.ElexonClient")
    def test_actuals_inclusive_dates(self, MockClient):
        """Records on both start and end dates are included."""
        records_day1 = [
            {
                "dataset": "FUELHH",
                "publishTime": "2026-01-01T00:30:00Z",
                "startTime": "2026-01-01T00:00:00Z",
                "settlementDate": "2026-01-01",
                "settlementPeriod": 1,
                "fuelType": "WIND",
                "generation": 10000,
            },
        ]
        records_day2 = [
            {
                "dataset": "FUELHH",
                "publishTime": "2026-01-02T00:30:00Z",
                "startTime": "2026-01-02T00:00:00Z",
                "settlementDate": "2026-01-02",
                "settlementPeriod": 1,
                "fuelType": "WIND",
                "generation": 12000,
            },
        ]
        mock_instance = AsyncMock()
        mock_instance.get_wind_actuals.return_value = (
            records_day1 + records_day2
        )
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/actuals",
            params={"start_date": "2026-01-01", "end_date": "2026-01-02"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["record_count"] == 2
        dates = {r["settlement_date"] for r in body["records"]}
        assert "2026-01-01" in dates
        assert "2026-01-02" in dates

    @patch("main.ElexonClient")
    def test_forecasts_filters_to_delivery_dates(self, MockClient):
        """Only forecasts whose delivery interval falls within the
        requested date range are included in the response."""
        all_records = [
            # Delivery on 2026-01-01 (should be included)
            {
                "dataset": "WINDFOR",
                "publishTime": "2025-12-31T11:30:00Z",
                "startTime": "2026-01-01T12:00:00Z",
                "generation": 19725,
            },
            # Delivery on 2026-01-02 (should be excluded for single-day query)
            {
                "dataset": "WINDFOR",
                "publishTime": "2025-12-31T11:30:00Z",
                "startTime": "2026-01-02T12:00:00Z",
                "generation": 18000,
            },
        ]
        mock_instance = AsyncMock()
        mock_instance.get_wind_forecasts.return_value = all_records
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/v1/wind/forecasts",
            params={"start_date": "2026-01-01", "end_date": "2026-01-01"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["record_count"] == 1
        assert body["records"][0]["generation"] == 19725


# ---------------------------------------------------------------------------
# CORS Configuration Tests
# ---------------------------------------------------------------------------

class TestCorsConfiguration:
    """Tests for FastAPI CORS middleware configuration and response headers."""

    def test_cors_preflight_production_origin(self):
        """OPTIONS preflight from production origin returns 200 with CORS headers."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://uk-wind-intelligence.vercel.app",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://uk-wind-intelligence.vercel.app"
        )
        assert response.headers.get("access-control-allow-credentials") == "true"
        allow_methods = response.headers.get("access-control-allow-methods", "")
        assert "GET" in allow_methods or "*" in allow_methods

    def test_cors_normal_response_production_origin(self):
        """GET request from production origin includes appropriate CORS headers."""
        response = client.get(
            "/health",
            headers={"Origin": "https://uk-wind-intelligence.vercel.app"},
        )
        assert response.status_code == 200
        assert (
            response.headers.get("access-control-allow-origin")
            == "https://uk-wind-intelligence.vercel.app"
        )
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_cors_preflight_unapproved_origin_disallowed(self):
        """OPTIONS preflight from an unapproved origin does NOT receive allow-origin."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://malicious-or-unapproved.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None

    def test_cors_normal_response_unapproved_origin_disallowed(self):
        """GET request from an unapproved origin does NOT receive allow-origin."""
        response = client.get(
            "/health",
            headers={"Origin": "https://malicious-or-unapproved.example.com"},
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") is None

    def test_cors_preview_deployment_not_allowed_without_explicit_config(self):
        """Preview deployments are rejected unless explicitly configured (no wildcards)."""
        response = client.options(
            "/health",
            headers={
                "Origin": "https://uk-wind-intelligence-git-feature-preview.vercel.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.headers.get("access-control-allow-origin") is None

    def test_cors_get_allowed_origins_parsing(self):
        """Verify CORS_ORIGINS parser trims whitespace and respects preview configs."""
        from main import get_allowed_origins, PRODUCTION_ORIGIN, DEFAULT_DEV_ORIGINS

        # Default fallback when missing or empty
        defaults = get_allowed_origins(None)
        assert PRODUCTION_ORIGIN in defaults
        for dev_orig in DEFAULT_DEV_ORIGINS:
            assert dev_orig in defaults
        assert "*" not in defaults

        # Empty string fallback
        defaults_empty = get_allowed_origins("   ")
        assert PRODUCTION_ORIGIN in defaults_empty
        assert "*" not in defaults_empty

        # Comma-separated with whitespace trimming
        custom = get_allowed_origins(
            " https://preview-1.vercel.app ,  https://preview-2.vercel.app , "
        )
        assert "https://preview-1.vercel.app" in custom
        assert "https://preview-2.vercel.app" in custom
        assert PRODUCTION_ORIGIN in custom
        assert "" not in custom

    def test_cors_preview_deployment_allowed_when_explicitly_configured(self):
        """Preview deployment origin is allowed when explicitly included in CORS_ORIGINS."""
        from fastapi import FastAPI
        from fastapi.middleware.cors import CORSMiddleware
        from main import get_allowed_origins

        preview_origin = "https://uk-wind-intelligence-preview-123.vercel.app"
        origins = get_allowed_origins(preview_origin)
        assert preview_origin in origins

        preview_app = FastAPI()
        preview_app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @preview_app.get("/health")
        def health():
            return {"status": "ok"}

        test_client = TestClient(preview_app)
        res = test_client.options(
            "/health",
            headers={
                "Origin": preview_origin,
                "Access-Control-Request-Method": "GET",
            },
        )
        assert res.status_code == 200
        assert res.headers.get("access-control-allow-origin") == preview_origin

