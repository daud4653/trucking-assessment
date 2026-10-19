from bisect import bisect_left
from dataclasses import dataclass

from .exceptions import InvalidTimingProfile
from .geometry import RouteGeometry


@dataclass(frozen=True)
class TimingBreakpoint:
    """Cumulative provider travel time at a vertex of the route geometry."""

    point_index: int
    elapsed_seconds: float


@dataclass(frozen=True)
class TimingProfile:
    """Piecewise-linear map from along-route distance to elapsed travel time.

    Between provider breakpoints, travel time is assumed proportional to
    distance. With only the route total available the whole route is one
    proportional segment and the profile is flagged as approximate.
    """

    distances_miles: tuple[float, ...]
    elapsed_seconds: tuple[float, ...]
    is_approximate: bool

    @classmethod
    def build(
        cls,
        geometry: RouteGeometry,
        total_seconds: float,
        breakpoints: list[TimingBreakpoint] | None = None,
    ) -> "TimingProfile":
        if total_seconds <= 0:
            raise InvalidTimingProfile("Route duration must be positive.")
        last_index = len(geometry.points) - 1
        distances = [0.0]
        elapsed = [0.0]
        for bp in sorted(breakpoints or [], key=lambda b: b.point_index):
            if not 0 < bp.point_index < last_index:
                continue
            distance = geometry.distance_at_index(bp.point_index)
            if bp.elapsed_seconds < elapsed[-1] or bp.elapsed_seconds > total_seconds:
                raise InvalidTimingProfile("Provider segment times are not monotonic.")
            if distance <= distances[-1]:
                continue
            distances.append(distance)
            elapsed.append(bp.elapsed_seconds)
        distances.append(geometry.total_miles)
        elapsed.append(total_seconds)
        return cls(tuple(distances), tuple(elapsed), is_approximate=len(distances) == 2)

    @property
    def total_seconds(self) -> float:
        return self.elapsed_seconds[-1]

    def elapsed_at(self, distance_miles: float) -> float:
        if distance_miles <= 0:
            return 0.0
        if distance_miles >= self.distances_miles[-1]:
            return self.total_seconds
        upper = bisect_left(self.distances_miles, distance_miles)
        lower = upper - 1
        d0, d1 = self.distances_miles[lower], self.distances_miles[upper]
        t0, t1 = self.elapsed_seconds[lower], self.elapsed_seconds[upper]
        return t0 + (t1 - t0) * (distance_miles - d0) / (d1 - d0)
