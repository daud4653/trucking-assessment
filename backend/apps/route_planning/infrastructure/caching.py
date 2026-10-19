"""Caching decorators around provider adapters.

Keys include the provider name, a schema version and every input that
changes the answer. Failures are never cached: only successful geocoding and
routing results, and only weather series that were actually retrieved.
Cached weather keeps its original `retrieved_at`, so freshness shown to the
user reflects when the provider answered, not when the cache was read.
"""

import hashlib
import json
from datetime import datetime

from django.core.cache import BaseCache

from apps.route_planning.application.ports import (
    GeocodingProvider,
    Place,
    RoutingProvider,
    RoutingResult,
    TruckProfile,
    WeatherProvider,
)
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.weather import HourlySeries

CACHE_VERSION = "v1"


def cache_key(namespace: str, *parts: object) -> str:
    digest = hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()
    return f"{namespace}:{CACHE_VERSION}:{digest}"


class CachedGeocodingProvider:
    def __init__(self, inner: GeocodingProvider, cache: BaseCache, ttl: int) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl
        self.name = inner.name
        self.attribution = inner.attribution

    def search(self, query: str, limit: int) -> list[Place]:
        key = cache_key("geocode", self.name, " ".join(query.lower().split()), limit)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        places = self._inner.search(query, limit)
        self._cache.set(key, places, self._ttl)
        return places


class CachedRoutingProvider:
    def __init__(self, inner: RoutingProvider, cache: BaseCache, ttl: int, name: str) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl
        self._name = name

    def get_routes(
        self, origin: Coordinate, destination: Coordinate, truck: TruckProfile, max_routes: int
    ) -> RoutingResult:
        key = cache_key(
            "route",
            self._name,
            round(origin.lat, 5),
            round(origin.lon, 5),
            round(destination.lat, 5),
            round(destination.lon, 5),
            truck.gross_weight_lb,
            max_routes,
        )
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        result = self._inner.get_routes(origin, destination, truck, max_routes)
        self._cache.set(key, result, self._ttl)
        return result


class CachedWeatherProvider:
    def __init__(self, inner: WeatherProvider, cache: BaseCache, ttl: int) -> None:
        self._inner = inner
        self._cache = cache
        self._ttl = ttl
        self.name = inner.name
        self.attribution = inner.attribution

    def get_hourly(
        self, points: list[Coordinate], start: datetime, end: datetime
    ) -> list[HourlySeries | None]:
        keys = [
            cache_key(
                "weather",
                self.name,
                round(p.lat, 4),
                round(p.lon, 4),
                start.isoformat(),
                end.isoformat(),
            )
            for p in points
        ]
        cached = self._cache.get_many(keys)
        missing = [i for i, key in enumerate(keys) if key not in cached]
        fetched = (
            self._inner.get_hourly([points[i] for i in missing], start, end) if missing else []
        )
        fresh = {
            keys[i]: series
            for i, series in zip(missing, fetched, strict=True)
            if series is not None
        }
        if fresh:
            self._cache.set_many(fresh, self._ttl)
        merged = {**cached, **fresh}
        return [merged.get(key) for key in keys]
