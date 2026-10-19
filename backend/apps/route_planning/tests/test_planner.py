from datetime import UTC, datetime, timedelta

import pytest

from apps.route_planning.application.corridor import FORECAST_HOURS, CorridorForecaster
from apps.route_planning.application.dto import LocationInput, PlanCommand
from apps.route_planning.application.errors import LocationNotFound, SameLocation
from apps.route_planning.application.planner import RoutePlanner
from apps.route_planning.domain.enums import DataStatus, RiskLevel, SamplingInterval
from apps.route_planning.domain.recommendation import ScreeningTier
from apps.route_planning.domain.weather import nearest_hour
from apps.route_planning.infrastructure.caching import (
    CachedGeocodingProvider,
    CachedWeatherProvider,
)

from .fakes import (
    CHICAGO,
    ST_LOUIS,
    FakeGeocoder,
    FakeRouter,
    FakeWeather,
    provider_route,
)

DEPARTURE = datetime(2026, 10, 20, 13, 40, tzinfo=UTC)


def command(**overrides) -> PlanCommand:
    values = {
        "origin": LocationInput("Chicago", None),
        "destination": LocationInput("St. Louis", None),
        "departure": DEPARTURE,
        "load_weight_lb": 20_000,
        "sampling_interval": SamplingInterval.MILES_25,
    }
    values.update(overrides)
    return PlanCommand(**values)


def planner(router=None, weather=None, geocoder=None) -> RoutePlanner:
    return RoutePlanner(
        geocoder or FakeGeocoder(), router or FakeRouter(), weather or FakeWeather(), 35_000
    )


def test_plan_ranks_three_routes_and_passes_gross_weight():
    router = FakeRouter()
    result = planner(router=router).plan(command())
    assert [r.ranking.rank for r in result.routes] == [1, 3, 2]
    assert router.calls[0].gross_weight_lb == 55_000
    assert {n.code for n in result.notices} == {"routing_scope"}


def test_checkpoint_weather_matches_each_eta():
    result = planner().plan(command())
    for route in result.routes:
        for checkpoint in route.checkpoints:
            assert checkpoint.reading.valid_time == nearest_hour(checkpoint.placement.eta)
            assert checkpoint.reading.precipitation_window_end >= checkpoint.placement.eta


def test_fewer_alternatives_are_disclosed_not_padded():
    result = planner(router=FakeRouter([provider_route(300, 18000)])).plan(command())
    assert len(result.routes) == 1
    assert "fewer_alternatives" in {n.code for n in result.notices}


def test_explicit_coordinates_skip_geocoding():
    geocoder = FakeGeocoder()
    planner(geocoder=geocoder).plan(
        command(
            origin=LocationInput("Home yard", CHICAGO),
            destination=LocationInput("Customer", ST_LOUIS),
        )
    )
    assert geocoder.queries == []


def test_unknown_location_raises():
    with pytest.raises(LocationNotFound) as excinfo:
        planner().plan(command(destination=LocationInput("Atlantis", None)))
    assert excinfo.value.field == "destination"


def test_same_location_rejected():
    with pytest.raises(SameLocation):
        planner().plan(command(destination=LocationInput("Chicago again", CHICAGO)))


def test_forecast_horizon_gap_makes_checkpoints_unknown():
    weather = FakeWeather(missing_after=DEPARTURE + timedelta(hours=2))
    result = planner(weather=weather).plan(command())
    route = result.routes[0]
    statuses = [c.risk.data_status for c in route.checkpoints]
    assert DataStatus.UNAVAILABLE in statuses
    assert route.summary.unknown_miles > 0
    assert route.summary.is_uncertain
    assert route.ranking.tier == ScreeningTier.UNCERTAIN
    assert "incomplete_weather" in {n.code for n in result.notices}


def test_heavy_load_wind_creates_no_travel_everywhere():
    result = planner(weather=FakeWeather(wind="50")).plan(command(load_weight_lb=30_001))
    assert all(r.ranking.tier == ScreeningTier.NO_TRAVEL for r in result.routes)
    assert "all_routes_no_travel" in {n.code for n in result.notices}


def test_same_wind_at_threshold_load_is_severe_not_no_travel():
    result = planner(weather=FakeWeather(wind="50")).plan(command(load_weight_lb=30_000))
    assert all(r.summary.peak_level == RiskLevel.SEVERE for r in result.routes)


def test_weather_requested_once_for_deduplicated_points():
    weather = FakeWeather()
    planner(weather=weather).plan(command())
    assert len(weather.requests) == 1
    _count, start, end = weather.requests[0]
    assert start == datetime(2026, 10, 20, 13, tzinfo=UTC)
    assert end > start


def test_corridor_returns_49_hourly_frames_with_load_adjusted_risk():
    forecaster = CorridorForecaster(FakeWeather(wind="40"))
    routes = [list(provider_route(300, 18000).points)]
    forecast = forecaster.forecast(routes, DEPARTURE, 45_000)
    assert len(forecast.frames) == FORECAST_HOURS + 1
    assert forecast.base_time == datetime(2026, 10, 20, 14, tzinfo=UTC)
    assert forecast.frames[-1].valid_time == forecast.base_time + timedelta(hours=48)
    assert set(forecast.frames[0].risk) == {int(RiskLevel.SEVERE)}
    assert forecast.coverage_ratio == 1.0


def test_corridor_marks_missing_hours_unknown():
    forecaster = CorridorForecaster(FakeWeather(missing_after=DEPARTURE + timedelta(hours=10)))
    forecast = forecaster.forecast([list(provider_route(300, 18000).points)], DEPARTURE, 1000)
    assert set(forecast.frames[-1].risk) == {None}
    assert forecast.coverage_ratio < 1


def test_weather_cache_hits_and_does_not_cache_failures(settings):
    from django.core.cache import cache

    point = provider_route(300, 1).points[0]
    failing = FakeWeather(fail_points={(round(point.lat, 4), round(point.lon, 4))})
    cached = CachedWeatherProvider(failing, cache, 60)
    points = list(provider_route(300, 1).points[:3])
    first = cached.get_hourly(points, DEPARTURE, DEPARTURE)
    second = cached.get_hourly(points, DEPARTURE, DEPARTURE)
    assert first[0] is None
    assert second[1] is first[1] or second[1] == first[1]
    assert failing.requests[1][0] == 1  # only the failed point is re-requested


def test_geocode_cache_normalizes_query():
    from django.core.cache import cache

    inner = FakeGeocoder()
    cached = CachedGeocodingProvider(inner, cache, 60)
    cached.search("Chicago", 1)
    cached.search("  chicago ", 1)
    assert inner.queries == ["Chicago"]
