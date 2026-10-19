"""Interfaces the planning use cases depend on.

Adapters in `infrastructure` implement these with vendor APIs; tests supply
in-memory fakes. Every value crossing these interfaces is already normalized
to the domain's units (miles, seconds, mph, in/hr, UTC datetimes).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.timing import TimingBreakpoint
from apps.route_planning.domain.weather import HourlySeries


@dataclass(frozen=True)
class Place:
    label: str
    coordinate: Coordinate


@dataclass(frozen=True)
class TruckProfile:
    gross_weight_lb: int


@dataclass(frozen=True)
class ProviderRoute:
    points: tuple[Coordinate, ...]
    distance_miles: float
    duration_seconds: float
    timing_breakpoints: tuple[TimingBreakpoint, ...]


@dataclass(frozen=True)
class RoutingResult:
    routes: tuple[ProviderRoute, ...]
    provider: str
    profile: str
    attribution: str


class GeocodingProvider(Protocol):
    name: str
    attribution: str

    def search(self, query: str, limit: int) -> list[Place]: ...


class RoutingProvider(Protocol):
    def get_routes(
        self,
        origin: Coordinate,
        destination: Coordinate,
        truck: TruckProfile,
        max_routes: int,
    ) -> RoutingResult: ...


class WeatherProvider(Protocol):
    name: str
    attribution: str

    def get_hourly(
        self, points: list[Coordinate], start: datetime, end: datetime
    ) -> list[HourlySeries | None]:
        """Return one series per point (same order); None where retrieval failed."""
        ...
