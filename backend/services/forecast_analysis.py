"""
Forecast Analysis and Temporal Alignment Service.

Implements:
1. Forecast-selection policies:
   - Policy A: Day-ahead fixed cutoff (default: D-1 at 12:00 UTC)
   - Policy B: Rolling lead time (e.g. 24h, 12h, 4h, 1h before interval startTime)
   - Policy C: Latest available before delivery (operational benchmark: publishTime <= startTime)
2. Temporal alignment:
   - Matches two half-hourly actual FUELHH generation records (periods 2k-1 and 2k)
   - Computes hourly actual generation as the arithmetic mean: (actual_1 + actual_2) / 2.0
   - Requires both half-hourly readings; missing one marks the hour incomplete.
3. Accuracy metrics:
   - MAE: Mean Absolute Error (MW)
   - RMSE: Root Mean Squared Error (MW)
   - Bias: Mean Signed Error, mean(forecast - actual) (MW). Positive = over-forecasting.
   - MAPE: Mean Absolute Percentage Error (%), zero actuals excluded. Null if no non-zero actuals.
   - Coverage: matched_intervals / expected_intervals
"""

import math
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from schemas import (
    ActualWindRecord,
    ForecastPolicy,
    ForecastWindRecord,
    IntervalStatus,
    AnalysisIntervalRecord,
    AnalysisMetrics,
    AnalysisResponse,
)


# ---------------------------------------------------------------------------
# Cutoff & Policy Helpers
# ---------------------------------------------------------------------------

def parse_day_ahead_cutoff_time(cutoff_str: str) -> Tuple[int, int]:
    """
    Parse and validate a HH:MM day-ahead cutoff time string (UTC).

    Raises:
        ValueError: If format is invalid or values out of range 00:00 - 23:59.
    """
    if not isinstance(cutoff_str, str):
        raise ValueError(f"Cutoff time must be a string, got {type(cutoff_str).__name__}.")

    match = re.fullmatch(r"^(\d{1,2}):(\d{2})$", cutoff_str.strip())
    if not match:
        raise ValueError(
            f"Invalid day-ahead cutoff time format: '{cutoff_str}'. "
            f"Expected HH:MM (e.g. '12:00')."
        )

    hour, minute = int(match.group(1)), int(match.group(2))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(
            f"Cutoff time out of range: '{cutoff_str}'. Hours must be 0-23 and minutes 0-59."
        )

    return hour, minute


def compute_interval_cutoff(
    interval_start: datetime,
    policy: str,
    lead_time_hours: Optional[float] = None,
    day_ahead_cutoff_time: str = "12:00",
) -> datetime:
    """
    Compute the exact decision cutoff datetime (UTC) for a given delivery interval.

    Args:
        interval_start: UTC datetime of the delivery interval start.
        policy: 'day_ahead', 'rolling', or 'latest_before_delivery'.
        lead_time_hours: Positive float for rolling policy.
        day_ahead_cutoff_time: HH:MM string for day_ahead policy (default '12:00').

    Returns:
        Timezone-aware UTC datetime of the cutoff boundary.
        Any forecast with publish_time <= cutoff is eligible.
    """
    if policy == ForecastPolicy.DAY_AHEAD.value or policy == "day_ahead":
        hour, minute = parse_day_ahead_cutoff_time(day_ahead_cutoff_time)
        delivery_date = interval_start.date()
        # D-1 gate closure
        prev_day = delivery_date - timedelta(days=1)
        return datetime(
            prev_day.year, prev_day.month, prev_day.day,
            hour, minute, 0,
            tzinfo=timezone.utc,
        )

    elif policy == ForecastPolicy.ROLLING.value or policy == "rolling":
        if lead_time_hours is None or lead_time_hours <= 0:
            raise ValueError(
                "lead_time_hours must be a positive number when using the 'rolling' policy."
            )
        return interval_start - timedelta(hours=lead_time_hours)

    elif policy == ForecastPolicy.LATEST_BEFORE_DELIVERY.value or policy == "latest_before_delivery":
        # Operational benchmark: publishTime <= delivery startTime
        return interval_start

    else:
        raise ValueError(
            f"Unsupported policy: '{policy}'. "
            f"Supported options: 'day_ahead', 'rolling', 'latest_before_delivery'."
        )


def describe_policy_cutoff(
    policy: str,
    lead_time_hours: Optional[float] = None,
    day_ahead_cutoff_time: str = "12:00",
) -> str:
    """Return a human-readable description of the policy and cutoff assumptions."""
    if policy in (ForecastPolicy.DAY_AHEAD.value, "day_ahead"):
        return (
            f"Day-ahead D-1 at {day_ahead_cutoff_time} UTC "
            "(configurable project assumption; not an official market rule)"
        )
    elif policy in (ForecastPolicy.ROLLING.value, "rolling"):
        return (
            f"Rolling {lead_time_hours}h lead time before interval delivery startTime "
            f"(publishTime <= startTime - {lead_time_hours}h)"
        )
    elif policy in (ForecastPolicy.LATEST_BEFORE_DELIVERY.value, "latest_before_delivery"):
        return (
            "Latest available before delivery (publishTime <= delivery startTime; "
            "operational benchmark, not a day-ahead purchasing forecast)"
        )
    return f"Custom policy: {policy}"


# ---------------------------------------------------------------------------
# Forecast Selection
# ---------------------------------------------------------------------------

def select_forecast_for_interval(
    candidates: List[ForecastWindRecord],
    cutoff: datetime,
) -> Optional[ForecastWindRecord]:
    """
    Select the eligible forecast revision for an interval based on the cutoff.

    Rules:
      - Only forecasts with publish_time <= cutoff are eligible.
      - A forecast published exactly at the cutoff (publish_time == cutoff) is eligible.
      - A forecast published after cutoff (publish_time > cutoff) is rejected.
      - Out of all eligible forecasts, the one with the latest publish_time is selected.
      - Deterministic tie-breaking: If multiple candidates share the exact same publish_time,
        the forecast with the highest generation value is selected.

    Returns:
      The selected ForecastWindRecord, or None if no eligible forecast exists.
    """
    eligible = [f for f in candidates if f.publish_time <= cutoff]
    if not eligible:
        return None

    # Sort key: publish_time ascending, then generation ascending.
    # The last element will have the latest publish_time and (if tied) highest generation.
    eligible.sort(key=lambda f: (f.publish_time, f.generation))
    return eligible[-1]


# ---------------------------------------------------------------------------
# Temporal Alignment (Half-Hourly Actuals -> Hourly)
# ---------------------------------------------------------------------------

def align_hourly_actual(
    interval_start: datetime,
    actuals_by_time: Dict[datetime, ActualWindRecord],
) -> Tuple[Optional[float], List[Optional[float]]]:
    """
    Align half-hourly FUELHH actuals to a single hourly interval.

    GB Settlement rules:
      - Period 2k-1 covers interval_start (e.g. 14:00 to 14:30)
      - Period 2k covers interval_start + 30m (e.g. 14:30 to 15:00)

    Calculates hourly generation as the arithmetic mean:
      hourly_mean = (h1 + h2) / 2.0

    Requirements:
      - Both half-hourly actuals MUST be present.
      - If either reading is missing, the hour is marked incomplete and actual is None.
      - Values are NOT summed or doubled; they represent average power (MW).

    Returns:
      Tuple of (hourly_mean_MW or None, [h1_val or None, h2_val or None])
    """
    t1 = interval_start
    t2 = interval_start + timedelta(minutes=30)

    r1 = actuals_by_time.get(t1)
    r2 = actuals_by_time.get(t2)

    h1_val = float(r1.generation) if r1 is not None else None
    h2_val = float(r2.generation) if r2 is not None else None

    if h1_val is None or h2_val is None:
        return None, [h1_val, h2_val]

    # Arithmetic mean of the two half-hours
    hourly_mean = (h1_val + h2_val) / 2.0
    return round(hourly_mean, 2), [h1_val, h2_val]


# ---------------------------------------------------------------------------
# Metrics Calculation
# ---------------------------------------------------------------------------

def calculate_accuracy_metrics(
    matched_pairs: List[Tuple[float, float]],
) -> AnalysisMetrics:
    """
    Calculate forecast accuracy metrics over valid MATCHED pairs (forecast, actual).

    Metrics:
      - MAE: mean(|forecast - actual|) in MW
      - RMSE: sqrt(mean((forecast - actual)^2)) in MW
      - Bias: mean(forecast - actual) in MW.
              Positive = over-forecasting (forecast > actual).
              Negative = under-forecasting (forecast < actual).
      - MAPE: mean(|forecast - actual| / |actual|) * 100 over pairs with actual != 0.
              Zero actuals are excluded from MAPE denominator to prevent division by zero.
              Returns None if no non-zero actual values exist.

    If matched_pairs is empty, returns all metrics as None.
    """
    if not matched_pairs:
        return AnalysisMetrics(
            mae=None,
            rmse=None,
            bias=None,
            mape=None,
        )

    n = len(matched_pairs)
    errors = [f - a for f, a in matched_pairs]
    abs_errors = [abs(e) for e in errors]
    sq_errors = [e ** 2 for e in errors]

    mae = round(sum(abs_errors) / n, 2)
    rmse = round(math.sqrt(sum(sq_errors) / n), 2)
    bias = round(sum(errors) / n, 2)

    # MAPE excluding zero actuals
    nonzero_pairs = [(f, a) for f, a in matched_pairs if a != 0.0]
    if nonzero_pairs:
        mape_vals = [abs(f - a) / abs(a) for f, a in nonzero_pairs]
        mape = round((sum(mape_vals) / len(nonzero_pairs)) * 100.0, 2)
    else:
        mape = None

    return AnalysisMetrics(
        mae=mae,
        rmse=rmse,
        bias=bias,
        mape=mape,
    )


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def analyze_wind_forecasts(
    start_date: date,
    end_date: date,
    actual_records: List[ActualWindRecord],
    forecast_records: List[ForecastWindRecord],
    policy: str = "day_ahead",
    lead_time_hours: Optional[float] = None,
    day_ahead_cutoff_time: str = "12:00",
) -> AnalysisResponse:
    """
    Perform full temporal alignment, forecast selection, and accuracy metric calculation.

    Args:
        start_date: First delivery date (inclusive).
        end_date: Last delivery date (inclusive).
        actual_records: Normalized FUELHH actual records.
        forecast_records: Normalized WINDFOR forecast records (all historical revisions).
        policy: 'day_ahead', 'rolling', or 'latest_before_delivery'.
        lead_time_hours: Lead time in hours (required if policy == 'rolling').
        day_ahead_cutoff_time: Cutoff time HH:MM UTC for day_ahead policy.

    Returns:
        Structured AnalysisResponse with interval records and summary metrics.
    """
    if start_date > end_date:
        raise ValueError(
            f"start_date ({start_date}) must not be after end_date ({end_date})."
        )

    # Validate policy and lead time
    if policy == ForecastPolicy.ROLLING.value or policy == "rolling":
        if lead_time_hours is None or lead_time_hours <= 0:
            raise ValueError(
                "lead_time_hours must be a positive number when using 'rolling' policy."
            )
    elif policy in (ForecastPolicy.DAY_AHEAD.value, "day_ahead"):
        # Validate cutoff time
        parse_day_ahead_cutoff_time(day_ahead_cutoff_time)

    # Index actuals by start_time (UTC)
    actuals_by_time: Dict[datetime, ActualWindRecord] = {
        r.start_time: r for r in actual_records
    }

    # Group forecasts by delivery start_time (UTC)
    forecasts_by_start: Dict[datetime, List[ForecastWindRecord]] = {}
    for f in forecast_records:
        forecasts_by_start.setdefault(f.start_time, []).append(f)

    # Generate expected hourly delivery intervals across [start_date, end_date]
    total_days = (end_date - start_date).days + 1
    expected_interval_count = total_days * 24

    interval_records: List[AnalysisIntervalRecord] = []
    matched_pairs: List[Tuple[float, float]] = []

    missing_forecast_count = 0
    missing_actual_count = 0

    curr_date = start_date
    while curr_date <= end_date:
        for hour in range(24):
            interval_start = datetime(
                curr_date.year, curr_date.month, curr_date.day,
                hour, 0, 0,
                tzinfo=timezone.utc,
            )

            # Settlement periods: period 1 = 00:00, period 2 = 00:30, etc.
            sp_start = hour * 2 + 1
            sp_end = hour * 2 + 2

            # Compute decision cutoff
            cutoff = compute_interval_cutoff(
                interval_start=interval_start,
                policy=policy,
                lead_time_hours=lead_time_hours,
                day_ahead_cutoff_time=day_ahead_cutoff_time,
            )

            # Select forecast
            candidate_forecasts = forecasts_by_start.get(interval_start, [])
            selected_forecast = select_forecast_for_interval(candidate_forecasts, cutoff)

            # Align actuals
            hourly_actual, half_hourly_vals = align_hourly_actual(
                interval_start, actuals_by_time
            )

            forecast_val: Optional[float] = (
                float(selected_forecast.generation) if selected_forecast else None
            )
            forecast_pub: Optional[datetime] = (
                selected_forecast.publish_time if selected_forecast else None
            )

            # Classify status and compute errors
            if forecast_val is not None and hourly_actual is not None:
                status = IntervalStatus.MATCHED
                error = round(forecast_val - hourly_actual, 2)
                abs_error = round(abs(forecast_val - hourly_actual), 2)
                matched_pairs.append((forecast_val, hourly_actual))
            elif forecast_val is None and hourly_actual is not None:
                status = IntervalStatus.MISSING_FORECAST
                error = None
                abs_error = None
                missing_forecast_count += 1
            elif forecast_val is not None and hourly_actual is None:
                status = IntervalStatus.INCOMPLETE_ACTUAL
                error = None
                abs_error = None
                missing_actual_count += 1
            else:
                status = IntervalStatus.MISSING_BOTH
                error = None
                abs_error = None
                missing_forecast_count += 1
                missing_actual_count += 1

            record = AnalysisIntervalRecord(
                delivery_start_time=interval_start,
                settlement_date=curr_date.isoformat(),
                settlement_period_start=sp_start,
                settlement_period_end=sp_end,
                cutoff_time=cutoff,
                forecast_generation=forecast_val,
                forecast_publish_time=forecast_pub,
                actual_generation=hourly_actual,
                half_hourly_actuals=half_hourly_vals,
                error=error,
                absolute_error=abs_error,
                status=status,
            )
            interval_records.append(record)

        curr_date += timedelta(days=1)

    matched_interval_count = len(matched_pairs)
    coverage_ratio = (
        round(matched_interval_count / expected_interval_count, 4)
        if expected_interval_count > 0 else 0.0
    )
    coverage_percentage = round(coverage_ratio * 100.0, 2)

    # Compute aggregate accuracy metrics
    metrics = calculate_accuracy_metrics(matched_pairs)

    data_notes = None
    if matched_interval_count == 0:
        data_notes = (
            "No valid matched intervals found for the selected date range and cutoff policy. "
            "All accuracy metrics are null."
        )
    elif matched_interval_count < expected_interval_count:
        data_notes = (
            f"Partial coverage: {matched_interval_count}/{expected_interval_count} intervals "
            f"matched ({coverage_percentage}%). "
            f"{missing_forecast_count} intervals missing eligible forecasts; "
            f"{missing_actual_count} intervals missing or incomplete actuals."
        )

    cutoff_rule_str = describe_policy_cutoff(
        policy=policy,
        lead_time_hours=lead_time_hours,
        day_ahead_cutoff_time=day_ahead_cutoff_time,
    )

    return AnalysisResponse(
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        policy=policy,
        cutoff_rule=cutoff_rule_str,
        lead_time_hours=lead_time_hours if policy == "rolling" else None,
        expected_interval_count=expected_interval_count,
        matched_interval_count=matched_interval_count,
        missing_forecast_count=missing_forecast_count,
        missing_actual_count=missing_actual_count,
        coverage_ratio=coverage_ratio,
        coverage_percentage=coverage_percentage,
        metrics=metrics,
        records=interval_records,
        data_notes=data_notes,
    )
