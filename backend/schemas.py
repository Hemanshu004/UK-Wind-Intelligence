"""
Pydantic models for the UK Wind Forecast Analytics API.

These schemas define the shape of data returned by the API endpoints
and used internally to validate Elexon BMRS responses.

All timestamps are timezone-aware UTC (ISO-8601 with Z suffix).
Generation values are in Megawatts (MW).
"""

from datetime import datetime, date
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Internal record models — represent normalised Elexon data
# ---------------------------------------------------------------------------

class ActualWindRecord(BaseModel):
    """A single half-hourly actual wind generation record from FUELHH."""

    dataset: str = Field(
        description="Source dataset identifier, always 'FUELHH'.",
        examples=["FUELHH"],
    )
    start_time: datetime = Field(
        description="Start of the 30-minute settlement period (UTC).",
        examples=["2026-01-01T00:00:00Z"],
    )
    settlement_date: str = Field(
        description="Settlement date in YYYY-MM-DD format.",
        examples=["2026-01-01"],
    )
    settlement_period: int = Field(
        description="Half-hour settlement period number (1–48).",
        ge=1,
        le=48,
        examples=[1],
    )
    fuel_type: str = Field(
        description="Fuel type category, filtered to WIND.",
        examples=["WIND"],
    )
    generation: int = Field(
        description="Average power output during the period in MW.",
        examples=[13756],
    )
    publish_time: Optional[datetime] = Field(
        default=None,
        description="When this outturn record was published (UTC).",
    )


class ForecastWindRecord(BaseModel):
    """A single wind generation forecast record from WINDFOR."""

    dataset: str = Field(
        description="Source dataset identifier, always 'WINDFOR'.",
        examples=["WINDFOR"],
    )
    start_time: datetime = Field(
        description="Delivery interval start time (UTC, hourly resolution).",
        examples=["2026-01-01T12:00:00Z"],
    )
    publish_time: datetime = Field(
        description="When this forecast was published by the ESO (UTC).",
        examples=["2025-12-31T11:30:00Z"],
    )
    generation: int = Field(
        description="Forecast average power output during the interval in MW.",
        examples=[19725],
    )


# ---------------------------------------------------------------------------
# API response wrappers
# ---------------------------------------------------------------------------

class ActualsResponse(BaseModel):
    """Response wrapper for the wind actuals endpoint."""

    start_date: str = Field(
        description="Requested start date (inclusive), YYYY-MM-DD.",
    )
    end_date: str = Field(
        description="Requested end date (inclusive), YYYY-MM-DD.",
    )
    record_count: int = Field(
        description="Total number of records returned.",
    )
    records: List[ActualWindRecord] = Field(
        description="List of normalised actual wind generation records.",
    )


class ForecastsResponse(BaseModel):
    """Response wrapper for the wind forecasts endpoint."""

    start_date: str = Field(
        description="Requested delivery start date (inclusive), YYYY-MM-DD.",
    )
    end_date: str = Field(
        description="Requested delivery end date (inclusive), YYYY-MM-DD.",
    )
    publication_window_start: str = Field(
        description="Earliest publication datetime queried (UTC ISO-8601).",
    )
    publication_window_end: str = Field(
        description="Latest publication datetime queried (UTC ISO-8601).",
    )
    record_count: int = Field(
        description="Total number of forecast records returned.",
    )
    records: List[ForecastWindRecord] = Field(
        description="List of normalised forecast records, including all revisions.",
    )


# ---------------------------------------------------------------------------
# Analytics and temporal alignment schemas (Task 4)
# ---------------------------------------------------------------------------

class ForecastPolicy(str, Enum):
    """Supported forecast selection policies."""

    DAY_AHEAD = "day_ahead"
    ROLLING = "rolling"
    LATEST_BEFORE_DELIVERY = "latest_before_delivery"


class IntervalStatus(str, Enum):
    """Status of an hourly delivery interval comparison."""

    MATCHED = "MATCHED"
    MISSING_FORECAST = "MISSING_FORECAST"
    INCOMPLETE_ACTUAL = "INCOMPLETE_ACTUAL"
    MISSING_BOTH = "MISSING_BOTH"


class AnalysisIntervalRecord(BaseModel):
    """Per-interval evaluation record pairing forecast with aligned actual."""

    delivery_start_time: datetime = Field(
        description="Delivery interval start time (UTC, hourly resolution).",
        examples=["2026-01-01T14:00:00Z"],
    )
    settlement_date: str = Field(
        description="Settlement date in YYYY-MM-DD format.",
        examples=["2026-01-01"],
    )
    settlement_period_start: int = Field(
        description="First half-hourly settlement period in this hour (1-47).",
        examples=[29],
    )
    settlement_period_end: int = Field(
        description="Second half-hourly settlement period in this hour (2-48).",
        examples=[30],
    )
    cutoff_time: datetime = Field(
        description="Exact decision cutoff datetime applied for this interval (UTC).",
        examples=["2025-12-31T12:00:00Z"],
    )
    forecast_generation: Optional[float] = Field(
        default=None,
        description="Selected forecast generation at decision cutoff in MW (None if missing).",
        examples=[14250.0],
    )
    forecast_publish_time: Optional[datetime] = Field(
        default=None,
        description="Publication timestamp of the selected forecast (UTC).",
        examples=["2025-12-31T11:45:00Z"],
    )
    actual_generation: Optional[float] = Field(
        default=None,
        description="Arithmetic mean of the two half-hourly actual readings in MW (None if incomplete/missing).",
        examples=[13800.0],
    )
    half_hourly_actuals: List[Optional[float]] = Field(
        default_factory=list,
        description="Underlying half-hourly generation readings [period_start, period_end] in MW.",
        examples=[[13600.0, 14000.0]],
    )
    error: Optional[float] = Field(
        default=None,
        description="Signed forecast error in MW: forecast - actual. Positive means over-forecasting.",
        examples=[450.0],
    )
    absolute_error: Optional[float] = Field(
        default=None,
        description="Absolute forecast error in MW: |forecast - actual|.",
        examples=[450.0],
    )
    status: IntervalStatus = Field(
        description="Comparison status: MATCHED, MISSING_FORECAST, INCOMPLETE_ACTUAL, or MISSING_BOTH.",
        examples=[IntervalStatus.MATCHED],
    )


class AnalysisMetrics(BaseModel):
    """Aggregate forecast accuracy metrics calculated over MATCHED intervals."""

    mae: Optional[float] = Field(
        default=None,
        description="Mean Absolute Error in MW (null if no valid matched pairs).",
        examples=[1150.25],
    )
    rmse: Optional[float] = Field(
        default=None,
        description="Root Mean Squared Error in MW (null if no valid matched pairs).",
        examples=[1420.80],
    )
    bias: Optional[float] = Field(
        default=None,
        description="Mean Signed Forecast Bias in MW: mean(forecast - actual). Positive = over-forecasting.",
        examples=[320.10],
    )
    mape: Optional[float] = Field(
        default=None,
        description="Mean Absolute Percentage Error (%), excluding zero actual values. Null if no eligible actuals.",
        examples=[9.45],
    )
    unit: str = Field(
        default="MW",
        description="Unit of measurement for generation, MAE, RMSE, and bias.",
    )
    bias_interpretation: str = Field(
        default="Positive bias indicates over-forecasting (forecast > actual); negative indicates under-forecasting.",
        description="Interpretation guide for signed error / bias.",
    )


class AnalysisResponse(BaseModel):
    """Complete analytics response evaluating forecast accuracy against actuals."""

    start_date: str = Field(
        description="Requested delivery start date (inclusive), YYYY-MM-DD.",
        examples=["2026-01-01"],
    )
    end_date: str = Field(
        description="Requested delivery end date (inclusive), YYYY-MM-DD.",
        examples=["2026-01-02"],
    )
    policy: str = Field(
        description="Applied forecast selection policy ('day_ahead', 'rolling', 'latest_before_delivery').",
        examples=["day_ahead"],
    )
    cutoff_rule: str = Field(
        description="Description of the cutoff rule and operational assumptions.",
        examples=["Day-ahead D-1 at 12:00 UTC (provisional project assumption)"],
    )
    lead_time_hours: Optional[float] = Field(
        default=None,
        description="Configured rolling lead time in hours (only populated when policy is 'rolling').",
        examples=[24.0],
    )
    expected_interval_count: int = Field(
        description="Total expected hourly intervals in requested delivery range (24 * days).",
        examples=[48],
    )
    matched_interval_count: int = Field(
        description="Total intervals successfully matched with both forecast and complete actual.",
        examples=[48],
    )
    missing_forecast_count: int = Field(
        description="Count of intervals where no eligible forecast was published before cutoff.",
        examples=[0],
    )
    missing_actual_count: int = Field(
        description="Count of intervals with missing or incomplete actual generation readings.",
        examples=[0],
    )
    coverage_ratio: float = Field(
        description="Coverage fraction: matched_interval_count / expected_interval_count (0.0 to 1.0).",
        examples=[1.0],
    )
    coverage_percentage: float = Field(
        description="Coverage as a percentage (0.0 to 100.0).",
        examples=[100.0],
    )
    metrics: AnalysisMetrics = Field(
        description="Aggregate accuracy metrics over matched intervals.",
    )
    records: List[AnalysisIntervalRecord] = Field(
        description="Per-interval detailed comparison records.",
    )
    data_notes: Optional[str] = Field(
        default=None,
        description="Contextual notes on data availability, alignment, or missing intervals.",
    )

