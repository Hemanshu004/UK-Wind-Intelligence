"""
Elexon BMRS API Client

Provides asynchronous HTTP access to the official Elexon Insights Solution API
for retrieving wind generation actuals (FUELHH) and forecasts (WINDFOR).

Base URL: https://data.elexon.co.uk/bmrs/api/v1
Authentication: None required (public API, confirmed by OpenAPI spec and live tests).
Timestamps: All returned timestamps are ISO-8601 UTC with 'Z' suffix.
Units: generation values are in Megawatts (MW).

See docs/elexon-api-investigation.md for full verification details.
"""

import httpx
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ELEXON_BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"

# Reasonable timeouts for external API calls.
# The stream endpoints can return large payloads (e.g. ~18 000 forecast
# records for a full month), so the read timeout is generous.
DEFAULT_CONNECT_TIMEOUT = 10.0  # seconds
DEFAULT_READ_TIMEOUT = 60.0    # seconds

# Maximum number of automatic retries for transient failures.
MAX_RETRIES = 2


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class ElexonAPIError(Exception):
    """Raised when the Elexon API returns an unexpected HTTP status."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Elexon API error {status_code}: {detail}")


class ElexonConnectionError(Exception):
    """Raised when the Elexon API cannot be reached."""

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(f"Elexon connection error: {detail}")


# ---------------------------------------------------------------------------
# Client class
# ---------------------------------------------------------------------------

class ElexonClient:
    """
    Async HTTP client for the Elexon BMRS Insights Solution API.

    Usage:
        async with ElexonClient() as client:
            actuals = await client.get_wind_actuals(
                settlement_date_from=date(2026, 1, 1),
                settlement_date_to=date(2026, 1, 1),
            )

    The client uses /stream endpoints which return raw JSON arrays and do
    not enforce the 7-day query window that the standard endpoints impose.
    """

    def __init__(
        self,
        base_url: str = ELEXON_BASE_URL,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
        read_timeout: float = DEFAULT_READ_TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=10.0,
            pool=10.0,
        )
        self._client: Optional[httpx.AsyncClient] = None

    # -- Context manager support -------------------------------------------

    async def __aenter__(self) -> "ElexonClient":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # -- Internal request helper -------------------------------------------

    async def _request(
        self,
        path: str,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Make a GET request to the given path with query params.

        Returns the parsed JSON response.  Stream endpoints return a JSON
        array directly (list of dicts).

        Retries up to MAX_RETRIES times on connection or timeout errors.
        Raises ElexonAPIError on non-2xx HTTP responses.
        Raises ElexonConnectionError on network failures after retries.
        """
        if self._client is None:
            raise RuntimeError(
                "ElexonClient must be used as an async context manager "
                "(async with ElexonClient() as client: ...)"
            )

        last_error: Optional[Exception] = None

        for attempt in range(1 + MAX_RETRIES):
            try:
                response = await self._client.get(path, params=params)

                if response.status_code != 200:
                    # Extract a short error detail from the response body
                    try:
                        body = response.json()
                        detail = body.get("title", response.text[:200])
                    except Exception:
                        detail = response.text[:200]
                    raise ElexonAPIError(response.status_code, detail)

                data = response.json()

                # Stream endpoints return a bare list; validate that.
                if not isinstance(data, list):
                    raise ElexonAPIError(
                        200,
                        f"Expected JSON array from stream endpoint, "
                        f"got {type(data).__name__}",
                    )
                return data

            except ElexonAPIError:
                # Do not retry client-side errors (4xx) or validation issues.
                raise
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    continue  # retry
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < MAX_RETRIES:
                    continue  # retry

        raise ElexonConnectionError(str(last_error))

    # -- Public data-access methods ----------------------------------------

    async def get_wind_actuals(
        self,
        settlement_date_from: date,
        settlement_date_to: date,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve FUELHH records filtered to fuelType=WIND.

        Parameters:
            settlement_date_from: First settlement date (inclusive), YYYY-MM-DD.
            settlement_date_to:   Last settlement date (inclusive), YYYY-MM-DD.

        Returns:
            List of raw Elexon record dicts. Each contains:
                dataset, publishTime, startTime, settlementDate,
                settlementPeriod, fuelType, generation.
        """
        params = {
            "settlementDateFrom": settlement_date_from.isoformat(),
            "settlementDateTo": settlement_date_to.isoformat(),
            "fuelType": "WIND",
        }
        return await self._request("/datasets/FUELHH/stream", params)

    async def get_wind_forecasts(
        self,
        publish_from: datetime,
        publish_to: datetime,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve WINDFOR records by publication time range.

        Parameters:
            publish_from: Earliest publication time (inclusive), UTC datetime.
            publish_to:   Latest publication time (inclusive), UTC datetime.

        Returns:
            List of raw Elexon record dicts.  Each contains:
                dataset, publishTime, startTime, generation.
        """
        params = {
            "publishDateTimeFrom": _format_utc(publish_from),
            "publishDateTimeTo": _format_utc(publish_to),
        }
        return await self._request("/datasets/WINDFOR/stream", params)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_utc(dt: datetime) -> str:
    """Format a datetime as ISO-8601 UTC string for Elexon query params."""
    if dt.tzinfo is None:
        # Treat naïve datetimes as UTC (all Elexon timestamps are UTC).
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
