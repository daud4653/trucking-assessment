"""Checkpoint placement along a route.

Checkpoints sit at every multiple of the sampling interval measured along the
route (not straight-line from the origin), plus the origin and destination.
An interval checkpoint closer than MIN_DESTINATION_GAP_MILES to the
destination is dropped so the destination does not duplicate it.

Each checkpoint represents the stretch of road nearer to it than to its
neighbours: from the midpoint with the previous checkpoint to the midpoint
with the next one. Those stretches tile the route exactly, which is what makes
distance-weighted aggregation independent of the sampling interval.
"""

import itertools
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from .enums import SamplingInterval
from .geometry import Coordinate, RouteGeometry
from .timing import TimingProfile

MIN_DESTINATION_GAP_MILES = 1.0


@dataclass(frozen=True)
class CheckpointPlacement:
    sequence: int
    distance_miles: float
    coordinate: Coordinate
    eta: datetime
    represents_from_miles: float
    represents_to_miles: float

    @property
    def represented_miles(self) -> float:
        return self.represents_to_miles - self.represents_from_miles


def checkpoint_distances(total_miles: float, interval: SamplingInterval) -> list[float]:
    step = float(interval.value)
    distances = [0.0]
    next_distance = step
    while next_distance < total_miles:
        distances.append(next_distance)
        next_distance += step
    if len(distances) > 1 and total_miles - distances[-1] < MIN_DESTINATION_GAP_MILES:
        distances.pop()
    distances.append(total_miles)
    return distances


def generate_checkpoints(
    geometry: RouteGeometry,
    timing: TimingProfile,
    interval: SamplingInterval,
    departure: datetime,
) -> list[CheckpointPlacement]:
    if departure.tzinfo is None:
        raise ValueError("Departure time must be timezone-aware.")
    # Elapsed time is added in UTC so DST transitions in the departure zone
    # cannot shift ETAs by wall-clock arithmetic.
    departure_utc = departure.astimezone(UTC)
    distances = checkpoint_distances(geometry.total_miles, interval)
    boundaries = (
        [0.0] + [(a + b) / 2 for a, b in itertools.pairwise(distances)] + [geometry.total_miles]
    )
    return [
        CheckpointPlacement(
            sequence=index,
            distance_miles=distance,
            coordinate=geometry.point_at(distance),
            eta=departure_utc + timedelta(seconds=timing.elapsed_at(distance)),
            represents_from_miles=boundaries[index],
            represents_to_miles=boundaries[index + 1],
        )
        for index, distance in enumerate(distances)
    ]
