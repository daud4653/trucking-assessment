"""Open-Meteo forecast adapter (https://open-meteo.com/en/docs).

Variables and unit handling:
* wind_speed_10m / wind_gusts_10m requested in mph.
* rain + showers: liquid precipitation in mm accumulated over the preceding
  hour. Their sum / 25.4 is the hour's mean intensity in in/hr.
* snowfall: snow depth in cm accumulated over the preceding hour. / 2.54
  gives the hour's mean snowfall intensity in in/hr.

Conversions use Decimal so values on a threshold (e.g. 2.54 mm = 0.10 in)
are not nudged across it by binary floating point.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from django.utils import timezone
from pydantic import BaseModel, ValidationError

from apps.route_planning.application.errors import ProviderError, ProviderResponseInvalid
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.weather import HourlySample, HourlySeries
from apps.route_planning.infrastructure.http import ProviderHttpClient

PROVIDER = "open-meteo"
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
HOURLY_VARIABLES = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
MAX_LOCATIONS_PER_REQUEST = 50
MM_PER_INCH = Decimal("25.4")
CM_PER_INCH = Decimal("2.54")
COORDINATE_DECIMALS = 4

logger = logging.getLogger(__name__)


class _Hourly(BaseModel):
    time: list[int]
    wind_speed_10m: list[float | None]
    wind_gusts_10m: list[float | None]
    rain: list[float | None]
    showers: list[float | None]
    snowfall: list[float | None]


class _Location(BaseModel):
    hourly: _Hourly


class OpenMeteoWeatherProvider:
    name = PROVIDER
    attribution = ATTRIBUTION

    def __init__(self, client: ProviderHttpClient, concurrency: int) -> None:
        self._client = client
        self._concurrency = concurrency

    def get_hourly(
        self, points: list[Coordinate], start: datetime, end: datetime
    ) -> list[HourlySeries | None]:
        chunks = [
            points[i : i + MAX_LOCATIONS_PER_REQUEST]
            for i in range(0, len(points), MAX_LOCATIONS_PER_REQUEST)
        ]
        with ThreadPoolExecutor(max_workers=self._concurrency) as pool:
            results = list(pool.map(lambda chunk: self._fetch_chunk(chunk, start, end), chunks))
        return [series for chunk_result in results for series in chunk_result]

    def _fetch_chunk(
        self, points: list[Coordinate], start: datetime, end: datetime
    ) -> list[HourlySeries | None]:
        params = {
            "latitude": ",".join(f"{p.lat:.{COORDINATE_DECIMALS}f}" for p in points),
            "longitude": ",".join(f"{p.lon:.{COORDINATE_DECIMALS}f}" for p in points),
            "hourly": ",".join(HOURLY_VARIABLES),
            "wind_speed_unit": "mph",
            "precipitation_unit": "mm",
            "timezone": "GMT",
            "timeformat": "unixtime",
            "start_hour": _format_hour(start),
            "end_hour": _format_hour(end),
        }
        try:
            payload = self._client.get_json("/v1/forecast", params)
            locations = payload if isinstance(payload, list) else [payload]
            parsed = [_Location.model_validate(item) for item in locations]
            if len(parsed) != len(points):
                raise ProviderResponseInvalid(PROVIDER, "location count mismatch")
        except (ValidationError, ProviderError) as exc:
            # Weather failures are tolerated per chunk: affected points become
            # "unavailable" rather than failing the whole plan.
            logger.warning(
                "weather chunk failed", extra={"points": len(points), "error": type(exc).__name__}
            )
            return [None] * len(points)
        retrieved_at = timezone.now()
        return [_to_series(location.hourly, retrieved_at) for location in parsed]


def _to_series(hourly: _Hourly, retrieved_at: datetime) -> HourlySeries:
    samples = {}
    for i, epoch in enumerate(hourly.time):
        moment = datetime.fromtimestamp(epoch, UTC)
        samples[moment] = HourlySample(
            time=moment,
            wind_mph=_decimal(_at(hourly.wind_speed_10m, i)),
            gust_mph=_decimal(_at(hourly.wind_gusts_10m, i)),
            rain_in_per_hr=_liquid_in_per_hr(_at(hourly.rain, i), _at(hourly.showers, i)),
            snow_in_per_hr=_divide(_decimal(_at(hourly.snowfall, i)), CM_PER_INCH),
        )
    return HourlySeries(samples=samples, retrieved_at=retrieved_at)


def _liquid_in_per_hr(rain_mm: float | None, showers_mm: float | None) -> Decimal | None:
    rain, showers = _decimal(rain_mm), _decimal(showers_mm)
    if rain is None or showers is None:
        return None
    return (rain + showers) / MM_PER_INCH


def _divide(value: Decimal | None, divisor: Decimal) -> Decimal | None:
    return None if value is None else value / divisor


def _at(values: list[float | None], index: int) -> float | None:
    return values[index] if index < len(values) else None


def _decimal(value: float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return None


def _format_hour(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:00")
