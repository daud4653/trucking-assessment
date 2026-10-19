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


def simplify(points: tuple[Coordinate, ...], tolerance_degrees: float) -> list[Coordinate]:
    """Ramer-Douglas-Peucker simplification for display geometry only.

    Checkpoints and distances are always computed from the full geometry.
    Planar degrees are an adequate metric at display tolerances (~tens of m).
    """
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        start, end = stack.pop()
        index, distance = _farthest(points, start, end)
        if distance > tolerance_degrees:
            keep[index] = True
            stack.extend(((start, index), (index, end)))
    return [point for point, kept in zip(points, keep, strict=True) if kept]


def _farthest(points: tuple[Coordinate, ...], start: int, end: int) -> tuple[int, float]:
    a, b = points[start], points[end]
    dx, dy = b.lon - a.lon, b.lat - a.lat
    length_sq = dx * dx + dy * dy
    best_index, best_distance = start, 0.0
    for i in range(start + 1, end):
        p = points[i]
        if length_sq == 0:
            distance = math.hypot(p.lon - a.lon, p.lat - a.lat)
        else:
            t = max(0.0, min(1.0, ((p.lon - a.lon) * dx + (p.lat - a.lat) * dy) / length_sq))
            distance = math.hypot(p.lon - (a.lon + t * dx), p.lat - (a.lat + t * dy))
        if distance > best_distance:
            best_index, best_distance = i, distance
    return best_index, best_distance
