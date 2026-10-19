from datetime import datetime, timedelta
from decimal import Decimal

from apps.route_planning.application.errors import ProviderUnavailable
from apps.route_planning.application.ports import (
    Place,
    ProviderRoute,
    RoutingResult,
    TruckProfile,
)
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.timing import TimingBreakpoint
from apps.route_planning.domain.weather import HOUR, HourlySample, HourlySeries

CHICAGO = Coordinate(41.8781, -87.6298)
ST_LOUIS = Coordinate(38.6270, -90.1994)


def straight_points(a: Coordinate, b: Coordinate, segments: int) -> tuple[Coordinate, ...]:
    return tuple(
        Coordinate(a.lat + (b.lat - a.lat) * i / segments, a.lon + (b.lon - a.lon) * i / segments)
        for i in range(segments + 1)
    )


def provider_route(
    miles: float, seconds: float, bend: float = 0.0, segments: int = 40
) -> ProviderRoute:
    points = list(straight_points(CHICAGO, ST_LOUIS, segments))
    middle = segments // 2
    points[middle] = Coordinate(points[middle].lat, points[middle].lon + bend)
    return ProviderRoute(
        points=tuple(points),
        distance_miles=miles,
        duration_seconds=seconds,
        timing_breakpoints=(TimingBreakpoint(middle, seconds / 2),),
    )


class FakeGeocoder:
    name = "fake-geocoder"
    attribution = "Fake geocoder"

    def __init__(self, places: dict[str, Coordinate] | None = None) -> None:
        self.places = places or {"chicago": CHICAGO, "st. louis": ST_LOUIS}
        self.queries: list[str] = []

    def search(self, query: str, limit: int) -> list[Place]:
        self.queries.append(query)
        coordinate = self.places.get(query.lower())
        return [Place(query.title(), coordinate)] if coordinate else []


class FakeRouter:
    def __init__(self, routes: list[ProviderRoute] | None = None, error: Exception | None = None):
        self.routes = routes or [
            provider_route(300, 5 * 3600),
            provider_route(310, 5.2 * 3600, bend=0.3),
            provider_route(320, 5.1 * 3600, bend=-0.3),
        ]
        self.error = error
        self.calls: list[TruckProfile] = []

    def get_routes(self, origin, destination, truck, max_routes) -> RoutingResult:
        self.calls.append(truck)
        if self.error:
            raise self.error
        return RoutingResult(tuple(self.routes[:max_routes]), "fake-router", "truck", "Fake")


class FakeWeather:
    """Uniform weather everywhere, optionally overridden per (rounded) point."""

    name = "fake-weather"
    attribution = "Fake weather"

    def __init__(
        self,
        wind: str = "5",
        rain: str = "0",
        snow: str = "0",
        missing_after: datetime | None = None,
        fail_points: set[tuple[float, float]] | None = None,
        overrides: dict[tuple[float, float], dict[str, str]] | None = None,
        unavailable: bool = False,
    ) -> None:
        self.values = {"wind": wind, "rain": rain, "snow": snow}
        self.missing_after = missing_after
        self.fail_points = fail_points or set()
        self.overrides = overrides or {}
        self.unavailable = unavailable
        self.requests: list[tuple[int, datetime, datetime]] = []

    def get_hourly(self, points, start, end):
        self.requests.append((len(points), start, end))
        if self.unavailable:
            raise ProviderUnavailable(self.name, "down")
        return [self._series(p, start, end) for p in points]

    def _series(self, point: Coordinate, start: datetime, end: datetime):
        key = (round(point.lat, 4), round(point.lon, 4))
        if key in self.fail_points:
            return None
        values = {**self.values, **self.overrides.get(key, {})}
        samples = {}
        moment = start
        while moment <= end:
            if self.missing_after is None or moment <= self.missing_after:
                samples[moment] = HourlySample(
                    moment,
                    Decimal(values["wind"]),
                    None,
                    Decimal(values["rain"]),
                    Decimal(values["snow"]),
                )
            moment += HOUR
        return HourlySeries(samples, retrieved_at=start - timedelta(minutes=5))
