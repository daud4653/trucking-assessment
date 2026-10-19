"""Composition root: builds use-case collaborators from settings.

Views obtain their dependencies only through these functions, so tests can
substitute in-memory providers by overriding them.
"""

from functools import cache

from django.conf import settings
from django.core.cache import cache as django_cache

from .application.corridor import CorridorForecaster
from .application.planner import RoutePlanner
from .application.ports import GeocodingProvider, WeatherProvider
from .infrastructure.caching import (
    CachedGeocodingProvider,
    CachedRoutingProvider,
    CachedWeatherProvider,
)
from .infrastructure.geocoding.photon import PhotonGeocodingProvider
from .infrastructure.http import HttpSettings, ProviderHttpClient
from .infrastructure.routing.valhalla import ValhallaRoutingProvider
from .infrastructure.weather.open_meteo import OpenMeteoWeatherProvider


def _http_settings() -> HttpSettings:
    providers = settings.PROVIDERS
    return HttpSettings(
        user_agent=providers["USER_AGENT"],
        connect_timeout=providers["CONNECT_TIMEOUT_SECONDS"],
        read_timeout=providers["READ_TIMEOUT_SECONDS"],
        max_retries=providers["MAX_RETRIES"],
    )


@cache
def geocoder() -> GeocodingProvider:
    client = ProviderHttpClient("photon", settings.PROVIDERS["PHOTON_BASE_URL"], _http_settings())
    return CachedGeocodingProvider(
        PhotonGeocodingProvider(client),
        django_cache,
        settings.PLANNING["GEOCODE_CACHE_SECONDS"],
    )


@cache
def weather() -> WeatherProvider:
    client = ProviderHttpClient(
        "open-meteo", settings.PROVIDERS["OPEN_METEO_BASE_URL"], _http_settings()
    )
    return CachedWeatherProvider(
        OpenMeteoWeatherProvider(client, settings.PROVIDERS["WEATHER_CONCURRENCY"]),
        django_cache,
        settings.PLANNING["WEATHER_CACHE_SECONDS"],
    )


@cache
def planner() -> RoutePlanner:
    client = ProviderHttpClient(
        "valhalla", settings.PROVIDERS["VALHALLA_BASE_URL"], _http_settings()
    )
    router = CachedRoutingProvider(
        ValhallaRoutingProvider(client),
        django_cache,
        settings.PLANNING["ROUTE_CACHE_SECONDS"],
        name="valhalla",
    )
    return RoutePlanner(geocoder(), router, weather(), settings.PLANNING["TRUCK_TARE_WEIGHT_LB"])


@cache
def corridor_forecaster() -> CorridorForecaster:
    return CorridorForecaster(weather())
