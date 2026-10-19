"""Corridor heatmap use case.

Distinct from route risk: route risk uses each checkpoint's own ETA, while
the corridor shows the whole area at one forecast time (departure + offset).
All FORECAST_HOURS + 1 hourly frames are produced in one call so the slider
can move through them without further requests.

Offsets are whole hours from the departure time rounded to the nearest
forecast hour; each frame reports the exact hour it represents. Cell risk
uses the same classification and load rules as checkpoints.
"""

from dataclasses import dataclass
from datetime import datetime

from apps.route_planning.domain.corridor import CorridorGrid, build_corridor
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.risk import (
    RAIN_SCALE,
    SNOW_SCALE,
    WIND_SCALE,
    MetricScale,
    assess_checkpoint,
    assess_metric,
)
from apps.route_planning.domain.weather import (
    HOUR,
    HourlySample,
    HourlySeries,
    WeatherReading,
    nearest_hour,
)

from .ports import WeatherProvider

FORECAST_HOURS = 48


@dataclass(frozen=True)
class CorridorFrame:
    valid_time: datetime
    risk: tuple[int | None, ...]
    wind_level: tuple[int | None, ...]
    rain_level: tuple[int | None, ...]
    snow_level: tuple[int | None, ...]
    wind_mph: tuple[float | None, ...]
    rain_in_per_hr: tuple[float | None, ...]
    snow_in_per_hr: tuple[float | None, ...]


@dataclass(frozen=True)
class CorridorForecast:
    grid: CorridorGrid
    base_time: datetime
    frames: tuple[CorridorFrame, ...]
    retrieved_at: datetime | None
    coverage_ratio: float
    attribution: str


class CorridorForecaster:
    def __init__(self, weather: WeatherProvider) -> None:
        self._weather = weather

    def forecast(
        self, routes: list[list[Coordinate]], departure: datetime, load_lb: int
    ) -> CorridorForecast:
        grid = build_corridor(routes)
        base = nearest_hour(departure)
        end = base + FORECAST_HOURS * HOUR
        series = self._weather.get_hourly([cell.center for cell in grid.cells], base, end)

        frames = tuple(
            _frame(base + offset * HOUR, series, load_lb) for offset in range(FORECAST_HOURS + 1)
        )
        known = sum(value is not None for frame in frames for value in frame.risk)
        total = len(frames) * len(grid.cells)
        retrieved = [s.retrieved_at for s in series if s is not None]
        return CorridorForecast(
            grid=grid,
            base_time=base,
            frames=frames,
            retrieved_at=min(retrieved) if retrieved else None,
            coverage_ratio=round(known / total, 4) if total else 0.0,
            attribution=self._weather.attribution,
        )


def _frame(moment: datetime, series: list[HourlySeries | None], load_lb: int) -> CorridorFrame:
    samples = [s.samples.get(moment) if s is not None else None for s in series]
    return CorridorFrame(
        valid_time=moment,
        risk=tuple(_risk(sample, load_lb) for sample in samples),
        wind_level=tuple(_metric_level(WIND_SCALE, sample, "wind_mph") for sample in samples),
        rain_level=tuple(_metric_level(RAIN_SCALE, sample, "rain_in_per_hr") for sample in samples),
        snow_level=tuple(_metric_level(SNOW_SCALE, sample, "snow_in_per_hr") for sample in samples),
        wind_mph=tuple(_number(sample, "wind_mph") for sample in samples),
        rain_in_per_hr=tuple(_number(sample, "rain_in_per_hr") for sample in samples),
        snow_in_per_hr=tuple(_number(sample, "snow_in_per_hr") for sample in samples),
    )


def _risk(sample: HourlySample | None, load_lb: int) -> int | None:
    if sample is None:
        return None
    reading = WeatherReading(
        valid_time=sample.time,
        precipitation_window_end=sample.time,
        wind_mph=sample.wind_mph,
        gust_mph=sample.gust_mph,
        rain_in_per_hr=sample.rain_in_per_hr,
        snow_in_per_hr=sample.snow_in_per_hr,
        retrieved_at=sample.time,
    )
    level = assess_checkpoint(reading, load_lb).level
    return int(level) if level is not None else None


def _metric_level(scale: MetricScale, sample: HourlySample | None, field: str) -> int | None:
    if sample is None:
        return None
    level = assess_metric(scale, getattr(sample, field)).level
    return int(level) if level is not None else None


def _number(sample: HourlySample | None, field: str) -> float | None:
    if sample is None:
        return None
    value = getattr(sample, field)
    return round(float(value), 4) if value is not None else None
