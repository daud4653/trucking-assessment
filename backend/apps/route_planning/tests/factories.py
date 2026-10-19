from datetime import UTC, datetime
from decimal import Decimal

from apps.route_planning.domain.weather import WeatherReading

VALID_TIME = datetime(2026, 1, 15, 12, tzinfo=UTC)


def reading(
    wind: str | None = "0",
    rain: str | None = "0",
    snow: str | None = "0",
    gust: str | None = None,
) -> WeatherReading:
    return WeatherReading(
        valid_time=VALID_TIME,
        precipitation_window_end=VALID_TIME,
        wind_mph=Decimal(wind) if wind is not None else None,
        gust_mph=Decimal(gust) if gust is not None else None,
        rain_in_per_hr=Decimal(rain) if rain is not None else None,
        snow_in_per_hr=Decimal(snow) if snow is not None else None,
        retrieved_at=VALID_TIME,
    )
