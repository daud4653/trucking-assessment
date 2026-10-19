from datetime import timedelta

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.route_planning import wiring
from apps.route_planning.application.corridor import CorridorForecaster
from apps.route_planning.application.planner import RoutePlanner

from .fakes import FakeGeocoder, FakeRouter, FakeWeather


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def providers(monkeypatch):
    """Replace every external provider with in-memory fakes for the API."""

    class Providers:
        geocoder = FakeGeocoder()
        router = FakeRouter()
        weather = FakeWeather()

    def planner():
        return RoutePlanner(Providers.geocoder, Providers.router, Providers.weather, 35_000)

    monkeypatch.setattr(wiring, "planner", planner)
    monkeypatch.setattr(wiring, "geocoder", lambda: Providers.geocoder)
    monkeypatch.setattr(
        wiring, "corridor_forecaster", lambda: CorridorForecaster(Providers.weather)
    )
    return Providers


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def departure():
    return (timezone.now() + timedelta(hours=2)).replace(microsecond=0)


@pytest.fixture
def plan_body(departure):
    return {
        "origin": {"query": "Chicago"},
        "destination": {"query": "St. Louis"},
        "departure_time": departure.isoformat(),
        "load_weight_lb": 42_000,
        "sampling_interval_miles": 25,
    }
