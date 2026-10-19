import itertools
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from apps.route_planning.domain.checkpointing import checkpoint_distances, generate_checkpoints
from apps.route_planning.domain.enums import SamplingInterval
from apps.route_planning.domain.exceptions import InvalidGeometry, InvalidTimingProfile
from apps.route_planning.domain.geometry import Coordinate, RouteGeometry, haversine_miles
from apps.route_planning.domain.timing import TimingBreakpoint, TimingProfile

DEPARTURE = datetime(2026, 3, 2, 14, 0, tzinfo=UTC)


def straight_route(miles: float, segments: int = 1) -> RouteGeometry:
    # One degree of latitude is ~69.09 miles; walk due north in equal steps.
    degrees = miles / 69.09
    points = [Coordinate(30 + degrees * i / segments, -97.0) for i in range(segments + 1)]
    return RouteGeometry.from_points(points, reported_miles=miles)


def test_short_route_has_only_endpoints():
    assert checkpoint_distances(7.5, SamplingInterval.MILES_10) == [0.0, 7.5]


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        (SamplingInterval.MILES_10, [0, 10, 20, 30, 40, 50, 55]),
        (SamplingInterval.MILES_25, [0, 25, 50, 55]),
        (SamplingInterval.MILES_50, [0, 50, 55]),
    ],
)
def test_intervals(interval, expected):
    assert checkpoint_distances(55.0, interval) == expected


def test_interval_point_too_close_to_destination_is_dropped():
    assert checkpoint_distances(50.4, SamplingInterval.MILES_25) == [0, 25, 50.4]


def test_exact_multiple_does_not_duplicate_destination():
    assert checkpoint_distances(50.0, SamplingInterval.MILES_25) == [0, 25, 50.0]


def test_long_route_with_many_segments():
    geometry = straight_route(612.0, segments=400)
    timing = TimingProfile.build(geometry, total_seconds=612 / 55 * 3600)
    checkpoints = generate_checkpoints(geometry, timing, SamplingInterval.MILES_10, DEPARTURE)
    distances = [c.distance_miles for c in checkpoints]
    assert distances == sorted(set(distances))
    assert distances[0] == 0
    assert distances[-1] == pytest.approx(612.0)
    assert len(checkpoints) == 63


def test_checkpoint_coordinates_follow_route_distance():
    geometry = straight_route(100.0, segments=7)
    timing = TimingProfile.build(geometry, total_seconds=7200)
    checkpoints = generate_checkpoints(geometry, timing, SamplingInterval.MILES_25, DEPARTURE)
    for checkpoint in checkpoints:
        measured = haversine_miles(geometry.points[0], checkpoint.coordinate)
        assert measured == pytest.approx(checkpoint.distance_miles, rel=1e-3)


def test_checkpoint_on_bent_route_is_measured_along_route():
    points = [Coordinate(30, -97), Coordinate(30.5, -97), Coordinate(30.5, -96.4)]
    geometry = RouteGeometry.from_points(points)
    halfway = geometry.total_miles / 2
    point = geometry.point_at(halfway)
    along = haversine_miles(points[0], points[1]) + haversine_miles(points[1], point)
    assert along == pytest.approx(halfway, rel=1e-3)


def test_represented_miles_tile_the_route_exactly():
    geometry = straight_route(137.3, segments=13)
    timing = TimingProfile.build(geometry, total_seconds=9000)
    for interval in SamplingInterval:
        checkpoints = generate_checkpoints(geometry, timing, interval, DEPARTURE)
        assert sum(c.represented_miles for c in checkpoints) == pytest.approx(137.3)
        for a, b in itertools.pairwise(checkpoints):
            assert a.represents_to_miles == b.represents_from_miles


def test_proportional_eta_when_no_segment_times():
    geometry = straight_route(100.0)
    timing = TimingProfile.build(geometry, total_seconds=7200)
    assert timing.is_approximate
    checkpoints = generate_checkpoints(geometry, timing, SamplingInterval.MILES_25, DEPARTURE)
    assert checkpoints[1].eta == DEPARTURE + timedelta(minutes=30)
    assert checkpoints[-1].eta == DEPARTURE + timedelta(hours=2)


def test_segment_times_shape_eta():
    # First half of the route is slow (90 min), second half fast (30 min).
    geometry = straight_route(100.0, segments=2)
    timing = TimingProfile.build(
        geometry, total_seconds=7200, breakpoints=[TimingBreakpoint(1, 5400)]
    )
    assert not timing.is_approximate
    checkpoints = generate_checkpoints(geometry, timing, SamplingInterval.MILES_25, DEPARTURE)
    etas = {round(c.distance_miles): c.eta for c in checkpoints}
    assert etas[25] == DEPARTURE + timedelta(minutes=45)
    assert etas[75] == DEPARTURE + timedelta(minutes=105)


def test_etas_are_monotonic():
    geometry = straight_route(300.0, segments=30)
    breakpoints = [TimingBreakpoint(i, i * 300 + (i % 3) * 20) for i in range(1, 30)]
    timing = TimingProfile.build(geometry, total_seconds=30 * 300, breakpoints=breakpoints)
    checkpoints = generate_checkpoints(geometry, timing, SamplingInterval.MILES_10, DEPARTURE)
    etas = [c.eta for c in checkpoints]
    assert etas == sorted(etas)


def test_non_monotonic_provider_times_are_rejected():
    geometry = straight_route(100.0, segments=3)
    with pytest.raises(InvalidTimingProfile):
        TimingProfile.build(
            geometry,
            total_seconds=7200,
            breakpoints=[TimingBreakpoint(1, 4000), TimingBreakpoint(2, 3000)],
        )


def test_non_utc_departure_is_normalized_to_utc():
    departure = datetime(2026, 3, 2, 8, 0, tzinfo=ZoneInfo("America/Chicago"))
    geometry = straight_route(50.0)
    timing = TimingProfile.build(geometry, total_seconds=3600)
    checkpoints = generate_checkpoints(geometry, timing, SamplingInterval.MILES_50, departure)
    assert checkpoints[0].eta == datetime(2026, 3, 2, 14, 0, tzinfo=UTC)
    assert checkpoints[-1].eta.tzinfo == UTC


def test_eta_across_dst_transition_uses_elapsed_time():
    # US DST begins 2026-03-08 02:00 local; a 3 hour trip from 00:30 CST
    # arrives at 04:30 CDT (3 real hours), not 03:30.
    departure = datetime(2026, 3, 8, 0, 30, tzinfo=ZoneInfo("America/Chicago"))
    geometry = straight_route(150.0)
    timing = TimingProfile.build(geometry, total_seconds=3 * 3600)
    checkpoints = generate_checkpoints(geometry, timing, SamplingInterval.MILES_50, departure)
    arrival_local = checkpoints[-1].eta.astimezone(ZoneInfo("America/Chicago"))
    assert arrival_local.hour == 4
    assert arrival_local.minute == 30
    assert checkpoints[-1].eta - departure == timedelta(hours=3)


def test_naive_departure_is_rejected():
    geometry = straight_route(50.0)
    timing = TimingProfile.build(geometry, total_seconds=3600)
    with pytest.raises(ValueError, match="timezone-aware"):
        generate_checkpoints(geometry, timing, SamplingInterval.MILES_10, datetime(2026, 1, 1))


def test_geometry_requires_two_distinct_points():
    with pytest.raises(InvalidGeometry):
        RouteGeometry.from_points([Coordinate(30, -97)])
    with pytest.raises(InvalidGeometry):
        RouteGeometry.from_points([Coordinate(30, -97), Coordinate(30, -97)])


def test_geometry_scales_to_reported_distance():
    geometry = straight_route(100.0, segments=4)
    rescaled = RouteGeometry.from_points(list(geometry.points), reported_miles=103.0)
    assert rescaled.total_miles == pytest.approx(103.0)
