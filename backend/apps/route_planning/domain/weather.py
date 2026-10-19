"""Normalized weather values and selection of the forecast hour for an ETA.

Forecast samples follow the provider convention that precipitation values
stamped at hour T are the accumulation over (T - 1h, T]. Dividing by one hour
gives the mean intensity over that hour, which is what the in/hr thresholds
are compared against; short bursts within the hour may be more intense.

For an arrival time t:
* precipitation uses the hour whose window contains t (sample at ceil(t));
* wind, an instantaneous value, uses the sample nearest to t.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class HourlySample:
    time: datetime
    wind_mph: Decimal | None
    gust_mph: Decimal | None
    rain_in_per_hr: Decimal | None
    snow_in_per_hr: Decimal | None


@dataclass(frozen=True)
class HourlySeries:
    samples: dict[datetime, HourlySample]
    retrieved_at: datetime


@dataclass(frozen=True)
class WeatherReading:
    """Values describing conditions at one checkpoint at its arrival time.

    Any value may be None when the provider has no data for it.
    """

    valid_time: datetime
    precipitation_window_end: datetime
    wind_mph: Decimal | None
    gust_mph: Decimal | None
    rain_in_per_hr: Decimal | None
    snow_in_per_hr: Decimal | None
    retrieved_at: datetime


def floor_hour(moment: datetime) -> datetime:
    return moment.replace(minute=0, second=0, microsecond=0)


def ceil_hour(moment: datetime) -> datetime:
    floored = floor_hour(moment)
    return floored if floored == moment else floored + HOUR


def nearest_hour(moment: datetime) -> datetime:
    floored = floor_hour(moment)
    return floored + HOUR if moment - floored >= HOUR / 2 else floored


def select_reading(series: HourlySeries | None, at: datetime) -> WeatherReading | None:
    if series is None:
        return None
    wind_time = nearest_hour(at)
    precipitation_time = ceil_hour(at)
    wind_sample = series.samples.get(wind_time)
    precipitation_sample = series.samples.get(precipitation_time)
    if wind_sample is None and precipitation_sample is None:
        return None
    return WeatherReading(
        valid_time=wind_time,
        precipitation_window_end=precipitation_time,
        wind_mph=wind_sample.wind_mph if wind_sample else None,
        gust_mph=wind_sample.gust_mph if wind_sample else None,
        rain_in_per_hr=precipitation_sample.rain_in_per_hr if precipitation_sample else None,
        snow_in_per_hr=precipitation_sample.snow_in_per_hr if precipitation_sample else None,
        retrieved_at=series.retrieved_at,
    )
