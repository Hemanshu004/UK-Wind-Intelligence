"""
UK Wind Forecast Analytics — FastAPI application.

Endpoints:
    GET /               Service info
    GET /health         Health check
    GET /api/v1/wind/actuals     Actual wind generation (FUELHH, fuelType=WIND)
    GET /api/v1/wind/forecasts   Wind generation forecasts (WINDFOR)

All dates in query parameters use YYYY-MM-DD format.
Both start_date and end_date are INCLUSIVE.
Timestamps in responses are ISO-8601 UTC.
Generation values are in Megawatts (MW).
"""

import asyncio
import math
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Optional

# Ensure the backend directory is in sys.path regardless of execution CWD
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from schemas import (
    ActualsResponse,
    ForecastsResponse,
    AnalysisResponse,
    ForecastPolicy,
)
from services.elexon_client import (
    ElexonClient,
    ElexonAPIError,
    ElexonConnectionError,
)
from services.wind_data import (
    normalise_actuals,
    normalise_forecasts,
    ValidationError,
)
from services.forecast_analysis import (
    analyze_wind_forecasts,
    parse_day_ahead_cutoff_time,
)

# Load environment variables from .env if present
load_dotenv()

app = FastAPI(
    title="UK Wind Forecast Analytics API",
    description="Backend API for UK Wind Forecast Analytics",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS Configuration
# ---------------------------------------------------------------------------

DEFAULT_DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
PRODUCTION_ORIGIN = "https://uk-wind-intelligence.vercel.app"


def get_allowed_origins(cors_origins_env: Optional[str] = None) -> list[str]:
    """
    Parse allowed CORS origins from the CORS_ORIGINS environment variable or argument.

    - Reads CORS_ORIGINS as a comma-separated list and trims whitespace.
    - If CORS_ORIGINS is missing or empty, provides safe development defaults for localhost.
    - Ensures the production Vercel origin (https://uk-wind-intelligence.vercel.app) is allowed.
    - Does NOT use wildcards for production.
    - Supports preview deployments only when their exact origins are explicitly configured.
    """
    if cors_origins_env is None:
        cors_origins_env = os.getenv("CORS_ORIGINS")

    if cors_origins_env is not None and cors_origins_env.strip():
        origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]
    else:
        origins = list(DEFAULT_DEV_ORIGINS)

    if PRODUCTION_ORIGIN not in origins:
        origins.append(PRODUCTION_ORIGIN)

    # Return deduplicated list while preserving order
    return list(dict.fromkeys(origins))


allowed_origins = get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Existing endpoints (preserved from Task 1)
# ---------------------------------------------------------------------------

@app.get("/")
def read_root():
    """Root endpoint returning basic service info."""
    return {
        "message": "UK Wind Forecast Analytics API",
        "docs_url": "/docs",
        "health_check_url": "/health",
    }


@app.get("/health")
def health_check():
    """Health-check endpoint indicating that the backend service is running."""
    return {
        "status": "ok",
        "service": "UK Wind Forecast Analytics API",
        "version": "0.1.0",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(value: str, param_name: str) -> date:
    """Parse a YYYY-MM-DD string into a date object."""
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {param_name}: expected YYYY-MM-DD format, got '{value}'.",
        )


def _validate_date_range(start: date, end: date) -> None:
    """Validate that start_date <= end_date and the range is reasonable."""
    if start > end:
        raise HTTPException(
            status_code=400,
            detail=(
                f"start_date ({start}) must not be after "
                f"end_date ({end})."
            ),
        )
    max_days = 366  # generous limit; one full year
    if (end - start).days > max_days:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Date range must not exceed {max_days} days. "
                f"Requested: {(end - start).days} days."
            ),
        )


# ---------------------------------------------------------------------------
# New API endpoints (Task 3)
# ---------------------------------------------------------------------------

@app.get(
    "/api/v1/wind/actuals",
    response_model=ActualsResponse,
    summary="Actual wind generation (FUELHH)",
    description=(
        "Returns half-hourly actual wind generation records from the Elexon "
        "BMRS FUELHH dataset, filtered to fuelType=WIND. Both start_date and "
        "end_date are inclusive. Records are returned at their original "
        "30-minute settlement-period resolution."
    ),
)
async def get_wind_actuals(
    start_date: str = Query(
        ...,
        description="First settlement date, inclusive (YYYY-MM-DD).",
        examples=["2026-01-01"],
    ),
    end_date: str = Query(
        ...,
        description="Last settlement date, inclusive (YYYY-MM-DD).",
        examples=["2026-01-01"],
    ),
):
    """Retrieve actual wind generation data from Elexon FUELHH."""
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    _validate_date_range(sd, ed)

    try:
        async with ElexonClient() as client:
            raw_records = await client.get_wind_actuals(
                settlement_date_from=sd,
                settlement_date_to=ed,
            )
    except ElexonAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Elexon API returned an error: {exc.detail}",
        )
    except ElexonConnectionError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Elexon API: {exc.detail}",
        )

    try:
        records = normalise_actuals(raw_records)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Elexon API returned invalid data: "
                f"field '{exc.field}' — {exc.reason}"
            ),
        )

    # Sort by start_time for consistent output
    records.sort(key=lambda r: r.start_time)

    return ActualsResponse(
        start_date=sd.isoformat(),
        end_date=ed.isoformat(),
        record_count=len(records),
        records=records,
    )


@app.get(
    "/api/v1/wind/forecasts",
    response_model=ForecastsResponse,
    summary="Wind generation forecasts (WINDFOR)",
    description=(
        "Returns wind generation forecast records from the Elexon BMRS "
        "WINDFOR dataset. Both start_date and end_date are inclusive delivery "
        "dates. The query automatically retrieves forecasts published up to "
        "3 days before the start_date to capture day-ahead and earlier "
        "forecast publications. All historical revisions are included so "
        "the frontend can apply a configurable purchasing cutoff."
    ),
)
async def get_wind_forecasts(
    start_date: str = Query(
        ...,
        description="First delivery date, inclusive (YYYY-MM-DD).",
        examples=["2026-01-01"],
    ),
    end_date: str = Query(
        ...,
        description="Last delivery date, inclusive (YYYY-MM-DD).",
        examples=["2026-01-01"],
    ),
):
    """
    Retrieve wind generation forecast data from Elexon WINDFOR.

    Forecasts for delivery on a given date may have been published several
    days earlier (e.g. a forecast for 1 Jan may be published on 30 Dec).
    This endpoint queries publications starting 3 days before start_date
    through end_date+1 to ensure complete coverage of all revisions.

    The response preserves ALL forecast revisions for each delivery
    interval, enabling the purchasing-cutoff selection algorithm to
    pick the correct forecast.
    """
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    _validate_date_range(sd, ed)

    # WINDFOR forecasts are indexed by publishTime.
    # A forecast for delivery on sd may have been published up to ~3 days
    # earlier (the ESO typically forecasts 48-72 hours ahead).
    # We query from (sd - 3 days) to (ed + 1 day) to capture all relevant
    # publications, then filter to delivery times within [sd, ed+1).
    publish_from = datetime(
        sd.year, sd.month, sd.day,
        tzinfo=timezone.utc,
    ) - timedelta(days=3)

    publish_to = datetime(
        ed.year, ed.month, ed.day, 23, 59, 59,
        tzinfo=timezone.utc,
    ) + timedelta(days=1)

    # Delivery window: startTime must fall on one of the requested dates.
    delivery_start = datetime(
        sd.year, sd.month, sd.day, tzinfo=timezone.utc
    )
    delivery_end = datetime(
        ed.year, ed.month, ed.day, tzinfo=timezone.utc
    ) + timedelta(days=1)

    try:
        async with ElexonClient() as client:
            raw_records = await client.get_wind_forecasts(
                publish_from=publish_from,
                publish_to=publish_to,
            )
    except ElexonAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Elexon API returned an error: {exc.detail}",
        )
    except ElexonConnectionError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Elexon API: {exc.detail}",
        )

    try:
        all_records = normalise_forecasts(raw_records)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Elexon API returned invalid data: "
                f"field '{exc.field}' — {exc.reason}"
            ),
        )

    # Filter to records whose delivery startTime falls within the
    # requested date range (inclusive).
    records = [
        r for r in all_records
        if delivery_start <= r.start_time < delivery_end
    ]

    # Sort by delivery time, then by publication time
    records.sort(key=lambda r: (r.start_time, r.publish_time))

    return ForecastsResponse(
        start_date=sd.isoformat(),
        end_date=ed.isoformat(),
        publication_window_start=publish_from.isoformat(),
        publication_window_end=publish_to.isoformat(),
        record_count=len(records),
        records=records,
    )


@app.get(
    "/api/v1/wind/analysis",
    response_model=AnalysisResponse,
    summary="Wind forecast accuracy analysis",
    description=(
        "Evaluates wind generation forecast accuracy against actual outturn "
        "for a requested delivery date range (inclusive). Supports three "
        "decision cutoff policies: 'day_ahead' (default: D-1 at 12:00 UTC), "
        "'rolling' (specified lead_time_hours), and 'latest_before_delivery'. "
        "Computes aggregate metrics (MAE, RMSE, Bias, MAPE) and per-interval records."
    ),
)
async def get_wind_analysis(
    start_date: str = Query(
        ...,
        description="First delivery date, inclusive (YYYY-MM-DD).",
        examples=["2026-01-01"],
    ),
    end_date: str = Query(
        ...,
        description="Last delivery date, inclusive (YYYY-MM-DD).",
        examples=["2026-01-02"],
    ),
    policy: str = Query(
        "day_ahead",
        description=(
            "Forecast selection policy: 'day_ahead', 'rolling', or 'latest_before_delivery'."
        ),
        examples=["day_ahead"],
    ),
    lead_time_hours: Optional[float] = Query(
        None,
        description="Positive lead time in hours (required when policy is 'rolling').",
        examples=[24.0],
    ),
    day_ahead_cutoff_time: str = Query(
        "12:00",
        description="Day-ahead cutoff time in HH:MM UTC (only used for 'day_ahead' policy; default '12:00').",
        examples=["12:00"],
    ),
):
    """
    Compare wind forecasts against aligned half-hourly actuals.

    Preserves original half-hourly readings, aligns them to hourly intervals
    via arithmetic mean, applies the specified purchasing cutoff to select
    the latest eligible forecast revision, and calculates accuracy metrics.
    """
    sd = _parse_date(start_date, "start_date")
    ed = _parse_date(end_date, "end_date")
    _validate_date_range(sd, ed)

    # Validate policy and parameters
    valid_policies = {"day_ahead", "rolling", "latest_before_delivery"}
    if policy not in valid_policies:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid policy '{policy}'. Must be one of: "
                f"{', '.join(sorted(valid_policies))}."
            ),
        )

    if policy == "rolling":
        if lead_time_hours is None or lead_time_hours <= 0:
            raise HTTPException(
                status_code=400,
                detail="lead_time_hours must be a positive number when policy is 'rolling'.",
            )
    elif policy == "day_ahead":
        try:
            parse_day_ahead_cutoff_time(day_ahead_cutoff_time)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            )

    # Calculate publication window for forecasts
    if policy == "rolling" and lead_time_hours:
        buffer_days = max(3, math.ceil(lead_time_hours / 24.0) + 2)
    else:
        buffer_days = 3

    publish_from = datetime(
        sd.year, sd.month, sd.day, tzinfo=timezone.utc
    ) - timedelta(days=buffer_days)

    publish_to = datetime(
        ed.year, ed.month, ed.day, 23, 59, 59, tzinfo=timezone.utc
    ) + timedelta(days=1)

    # Fetch both actuals and forecasts concurrently
    try:
        async with ElexonClient() as client:
            raw_actuals, raw_forecasts = await asyncio.gather(
                client.get_wind_actuals(
                    settlement_date_from=sd,
                    settlement_date_to=ed,
                ),
                client.get_wind_forecasts(
                    publish_from=publish_from,
                    publish_to=publish_to,
                ),
            )
    except ElexonAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Elexon API returned an error: {exc.detail}",
        )
    except ElexonConnectionError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Elexon API: {exc.detail}",
        )

    # Parse and validate records
    try:
        actual_records = normalise_actuals(raw_actuals)
        forecast_records = normalise_forecasts(raw_forecasts)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Elexon API returned invalid data: "
                f"field '{exc.field}' — {exc.reason}"
            ),
        )

    # Perform analysis
    try:
        return analyze_wind_forecasts(
            start_date=sd,
            end_date=ed,
            actual_records=actual_records,
            forecast_records=forecast_records,
            policy=policy,
            lead_time_hours=lead_time_hours,
            day_ahead_cutoff_time=day_ahead_cutoff_time,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
