import itertools
import math
from bisect import bisect_left
from dataclasses import dataclass

from .exceptions import InvalidGeometry

EARTH_RADIUS_MILES = 3958.7613


@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float

    def __post_init__(self) -> None:
        if not (-90 <= self.lat <= 90 and -180 <= self.lon <= 180):
            raise InvalidGeometry(f"Coordinate out of range: {self.lat}, {self.lon}")


def haversine_miles(a: Coordinate, b: Coordinate) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(h)))


@dataclass(frozen=True)
class RouteGeometry:
    """A polyline with cumulative along-route distances in miles.

    Distances are measured along the polyline and then scaled so the total
    matches the provider's reported route distance. The provider measures the
    road network more precisely than the simplified shape it returns, and
    scaling keeps checkpoint distances consistent with the reported total.
    """

    points: tuple[Coordinate, ...]
    cumulative_miles: tuple[float, ...]

    @classmethod
    def from_points(
        cls, points: list[Coordinate], reported_miles: float | None = None
    ) -> "RouteGeometry":
        if len(points) < 2:
            raise InvalidGeometry("A route needs at least two points.")
        cumulative = [0.0]
        for previous, current in itertools.pairwise(points):
            cumulative.append(cumulative[-1] + haversine_miles(previous, current))
        measured = cumulative[-1]
        if measured <= 0:
            raise InvalidGeometry("Route geometry has zero length.")
        if reported_miles is not None:
            if reported_miles <= 0:
                raise InvalidGeometry("Reported route distance must be positive.")
            scale = reported_miles / measured
            cumulative = [d * scale for d in cumulative]
        return cls(tuple(points), tuple(cumulative))

    @property
    def total_miles(self) -> float:
        return self.cumulative_miles[-1]

    def distance_at_index(self, index: int) -> float:
        return self.cumulative_miles[index]

    def point_at(self, distance_miles: float) -> Coordinate:
        if distance_miles <= 0:
            return self.points[0]
        if distance_miles >= self.total_miles:
            return self.points[-1]
        upper = bisect_left(self.cumulative_miles, distance_miles)
        lower = upper - 1
        start, end = self.cumulative_miles[lower], self.cumulative_miles[upper]
        fraction = (distance_miles - start) / (end - start) if end > start else 0.0
        a, b = self.points[lower], self.points[upper]
        return Coordinate(a.lat + (b.lat - a.lat) * fraction, a.lon + (b.lon - a.lon) * fraction)
