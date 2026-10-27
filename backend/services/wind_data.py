"""
Wind data parsing, validation and normalisation.

Converts raw Elexon API response dicts into validated Pydantic models.

Design decisions:
  - Records with missing required fields are rejected (not silently dropped).
  - Timestamps are parsed as timezone-aware UTC datetimes.
  - Half-hourly actuals are preserved at their original resolution.
    Aggregation to hourly bins is NOT done here — it belongs in the
    alignment / analytics layer (Task 4).
  - All forecast revisions for the same delivery interval are preserved
    so the purchasing-cutoff selection algorithm can pick the right one.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from schemas import ActualWindRecord, ForecastWindRecord


# ---------------------------------------------------------------------------
# Custom exception
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when an Elexon record fails validation."""

    def __init__(self, field: str, value: Any, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(
            f"Validation error on field '{field}' "
            f"(value={value!r}): {reason}"
        )


# ---------------------------------------------------------------------------
# Timestamp parsing
# ---------------------------------------------------------------------------

def parse_utc_timestamp(raw: Any, field_name: str) -> datetime:
    """
    Parse an ISO-8601 timestamp string into a timezone-aware UTC datetime.

    The Elexon API returns timestamps like '2026-01-01T00:00:00Z'.
    Accepts both 'Z'-suffixed and '+00:00'-suffixed strings.

    Raises ValidationError if the value is missing or malformed.
    """
    if raw is None:
        raise ValidationError(field_name, raw, "Required timestamp is missing.")
    if not isinstance(raw, str):
        raise ValidationError(field_name, raw, "Expected a string timestamp.")

    try:
        # Python 3.9's fromisoformat does not handle 'Z', so replace it.
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValidationError(
            field_name, raw, f"Cannot parse as ISO-8601: {exc}"
        )

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt


def parse_generation(raw: Any, field_name: str = "generation") -> int:
    """
    Validate and return the generation value as an integer (MW).

    Raises ValidationError if the value is null, non-numeric, or negative.
    """
    if raw is None:
        raise ValidationError(field_name, raw, "Generation value is missing.")

    try:
        value = int(raw)
    except (ValueError, TypeError):
        raise ValidationError(
            field_name, raw, "Generation must be a numeric integer."
        )

    if value < 0:
        raise ValidationError(
            field_name, raw, "Generation must not be negative."
        )

    return value


# ---------------------------------------------------------------------------
# Record normalisation
# ---------------------------------------------------------------------------

def normalise_actual_record(raw: Dict[str, Any]) -> ActualWindRecord:
    """
    Convert a raw FUELHH response dict into a validated ActualWindRecord.

    Required fields (per docs/elexon-api-investigation.md §4.3):
        dataset, startTime, settlementDate, settlementPeriod,
        fuelType, generation.
    Optional: publishTime.
    """
    # Validate required string fields
    dataset = raw.get("dataset")
    if dataset is None:
        raise ValidationError("dataset", None, "Missing 'dataset' field.")

    fuel_type = raw.get("fuelType")
    if fuel_type is None:
        raise ValidationError("fuelType", None, "Missing 'fuelType' field.")

    settlement_date = raw.get("settlementDate")
    if settlement_date is None:
        raise ValidationError(
            "settlementDate", None, "Missing 'settlementDate' field."
        )

    # Validate settlement period
    sp_raw = raw.get("settlementPeriod")
    if sp_raw is None:
        raise ValidationError(
            "settlementPeriod", None, "Missing 'settlementPeriod' field."
        )
    try:
        settlement_period = int(sp_raw)
    except (ValueError, TypeError):
        raise ValidationError(
            "settlementPeriod", sp_raw, "Must be an integer."
        )
    if not 1 <= settlement_period <= 48:
        raise ValidationError(
            "settlementPeriod", sp_raw, "Must be between 1 and 48."
        )

    return ActualWindRecord(
        dataset=dataset,
        start_time=parse_utc_timestamp(raw.get("startTime"), "startTime"),
        settlement_date=settlement_date,
        settlement_period=settlement_period,
        fuel_type=fuel_type,
        generation=parse_generation(raw.get("generation")),
        publish_time=(
            parse_utc_timestamp(raw.get("publishTime"), "publishTime")
            if raw.get("publishTime") is not None
            else None
        ),
    )


def normalise_forecast_record(raw: Dict[str, Any]) -> ForecastWindRecord:
    """
    Convert a raw WINDFOR response dict into a validated ForecastWindRecord.

    Required fields (per docs/elexon-api-investigation.md §5.3):
        dataset, publishTime, startTime, generation.
    """
    dataset = raw.get("dataset")
    if dataset is None:
        raise ValidationError("dataset", None, "Missing 'dataset' field.")

    return ForecastWindRecord(
        dataset=dataset,
        start_time=parse_utc_timestamp(raw.get("startTime"), "startTime"),
        publish_time=parse_utc_timestamp(
            raw.get("publishTime"), "publishTime"
        ),
        generation=parse_generation(raw.get("generation")),
    )


# ---------------------------------------------------------------------------
# Batch normalisation
# ---------------------------------------------------------------------------

def normalise_actuals(
    raw_records: List[Dict[str, Any]],
) -> List[ActualWindRecord]:
    """
    Normalise a list of raw FUELHH dicts.

    All records must pass validation — a single invalid record raises
    an exception, because silently dropping outturn data could produce
    misleading analytics.
    """
    return [normalise_actual_record(r) for r in raw_records]


def normalise_forecasts(
    raw_records: List[Dict[str, Any]],
) -> List[ForecastWindRecord]:
    """
    Normalise a list of raw WINDFOR dicts.

    Same strictness policy as normalise_actuals.
    """
    return [normalise_forecast_record(r) for r in raw_records]
