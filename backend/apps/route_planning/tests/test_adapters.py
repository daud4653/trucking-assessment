import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
import pytest

from apps.route_planning.application.errors import (
    ProviderRejected,
    ProviderResponseInvalid,
    ProviderUnavailable,
    RouteNotFound,
    RouteTooLong,
)
from apps.route_planning.application.ports import TruckProfile
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.infrastructure.geocoding.photon import PhotonGeocodingProvider
from apps.route_planning.infrastructure.http import HttpSettings, ProviderHttpClient
from apps.route_planning.infrastructure.routing.polyline import decode_polyline
from apps.route_planning.infrastructure.routing.valhalla import ValhallaRoutingProvider
from apps.route_planning.infrastructure.weather.open_meteo import OpenMeteoWeatherProvider

SETTINGS = HttpSettings("test-agent", connect_timeout=1, read_timeout=1, max_retries=2)
START = datetime(2026, 10, 20, 12, tzinfo=UTC)


def encode_polyline(points: list[tuple[float, float]], precision: int = 6) -> str:
    factor = 10**precision
    output, prev_lat, prev_lon = [], 0, 0
    for lat, lon in points:
        ilat, ilon = round(lat * factor), round(lon * factor)
        for delta in (ilat - prev_lat, ilon - prev_lon):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                output.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            output.append(chr(value + 63))
        prev_lat, prev_lon = ilat, ilon
    return "".join(output)


def client(handler, provider="test", sleeps=None) -> ProviderHttpClient:
    recorder = sleeps if sleeps is not None else []
    return ProviderHttpClient(
        provider,
        "https://provider.test",
        SETTINGS,
        transport=httpx.MockTransport(handler),
        sleep=recorder.append,
    )


# --- HTTP client -----------------------------------------------------------


def test_retries_transient_status_then_succeeds():
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    sleeps: list[float] = []
    assert client(handler, sleeps=sleeps).get_json("/x", {}) == {"ok": True}
    assert len(calls) == 3
    assert len(sleeps) == 2
    assert sleeps[1] > sleeps[0]


def test_honours_short_retry_after_on_429():
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "1"}), httpx.Response(200, json=[])]
    )
    sleeps: list[float] = []
    client(lambda r: next(responses), sleeps=sleeps).get_json("/x", {})
    assert sleeps == [1.0]


def test_long_retry_after_fails_fast():
    sleeps: list[float] = []
    with pytest.raises(ProviderUnavailable):
        client(
            lambda r: httpx.Response(429, headers={"Retry-After": "120"}), sleeps=sleeps
        ).get_json("/x", {})
    assert sleeps == []


def test_timeouts_are_retried_then_reported_unavailable():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(ProviderUnavailable):
        client(handler).get_json("/x", {})
    assert len(calls) == SETTINGS.max_retries + 1


def test_client_errors_are_not_retried():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": "bad key"})

    with pytest.raises(ProviderRejected) as excinfo:
        client(handler).get_json("/x", {})
    assert len(calls) == 1
    assert excinfo.value.status_code == 401


def test_non_json_response_is_invalid():
    with pytest.raises(ProviderResponseInvalid):
        client(lambda r: httpx.Response(200, text="<html>")).get_json("/x", {})


# --- Valhalla ----------------------------------------------------------------


def valhalla_trip(points, miles, seconds, maneuvers):
    return {
        "units": "miles",
        "summary": {"length": miles, "time": seconds},
        "legs": [
            {
                "shape": encode_polyline(points),
                "summary": {"length": miles, "time": seconds},
                "maneuvers": [
                    {"time": t, "length": length, "begin_shape_index": i}
                    for i, t, length in maneuvers
                ],
            }
        ],
    }


ROUTE_A = [(41.0, -87.0), (40.5, -87.5), (40.0, -88.0)]
ROUTE_B = [(41.0, -87.0), (40.6, -87.2), (40.0, -88.0)]


def test_valhalla_parses_routes_and_segment_times():
    captured = {}

    def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "trip": valhalla_trip(
                    ROUTE_A, 80.0, 5000, [(0, 3000, 50), (1, 2000, 30), (2, 0, 0)]
                ),
                "alternates": [{"trip": valhalla_trip(ROUTE_B, 85.0, 5400, [(0, 5400, 85)])}],
            },
        )

    result = ValhallaRoutingProvider(client(handler)).get_routes(
        Coordinate(41, -87), Coordinate(40, -88), TruckProfile(77_000), 3
    )
    assert captured["body"]["costing"] == "truck"
    assert captured["body"]["alternates"] == 2
    assert captured["body"]["costing_options"]["truck"]["weight"] == pytest.approx(34.93, abs=0.01)
    assert len(result.routes) == 2
    first = result.routes[0]
    assert first.distance_miles == 80.0
    assert first.points[1] == Coordinate(40.5, -87.5)
    assert [(b.point_index, b.elapsed_seconds) for b in first.timing_breakpoints] == [
        (0, 0.0),
        (1, 3000.0),
        (2, 5000.0),
    ]


def test_valhalla_drops_duplicate_alternatives():
    trip = valhalla_trip(ROUTE_A, 80.0, 5000, [(0, 5000, 80)])
    result = ValhallaRoutingProvider(
        client(lambda r: httpx.Response(200, json={"trip": trip, "alternates": [{"trip": trip}]}))
    ).get_routes(Coordinate(41, -87), Coordinate(40, -88), TruckProfile(50_000), 3)
    assert len(result.routes) == 1


@pytest.mark.parametrize(
    ("code", "error"), [(442, RouteNotFound), (171, RouteNotFound), (154, RouteTooLong)]
)
def test_valhalla_error_codes_are_translated(code, error):
    handler = lambda r: httpx.Response(400, json={"error_code": code, "error": "x"})  # noqa: E731
    with pytest.raises(error):
        ValhallaRoutingProvider(client(handler)).get_routes(
            Coordinate(41, -87), Coordinate(40, -88), TruckProfile(50_000), 3
        )


def test_valhalla_invalid_payload():
    with pytest.raises(ProviderResponseInvalid):
        ValhallaRoutingProvider(client(lambda r: httpx.Response(200, json={"nope": 1}))).get_routes(
            Coordinate(41, -87), Coordinate(40, -88), TruckProfile(50_000), 3
        )


def test_polyline_round_trip():
    points = [(38.5, -120.2), (40.7, -120.95), (43.252, -126.453)]
    decoded = decode_polyline(encode_polyline(points))
    assert [(round(p.lat, 6), round(p.lon, 6)) for p in decoded] == points


# --- Open-Meteo --------------------------------------------------------------


def open_meteo_location(hours: int, rain=0.0, showers=0.0, snow=0.0, wind=10.0):
    epoch = int(START.timestamp())
    return {
        "hourly": {
            "time": [epoch + 3600 * i for i in range(hours)],
            "wind_speed_10m": [wind] * hours,
            "wind_gusts_10m": [wind + 5] * hours,
            "rain": [rain] * hours,
            "showers": [showers] * hours,
            "snowfall": [snow] * hours,
        }
    }


def test_open_meteo_converts_units_exactly():
    handler = lambda r: httpx.Response(  # noqa: E731
        200, json=open_meteo_location(2, rain=2.0, showers=0.54, snow=1.27)
    )
    provider = OpenMeteoWeatherProvider(client(handler), concurrency=2)
    [series] = provider.get_hourly([Coordinate(40, -88)], START, START + timedelta(hours=1))
    sample = series.samples[START]
    assert sample.rain_in_per_hr == Decimal("0.1")
    assert sample.snow_in_per_hr == Decimal("0.5")
    assert sample.wind_mph == Decimal("10.0")


def test_open_meteo_null_values_stay_unknown():
    payload = open_meteo_location(1)
    payload["hourly"]["snowfall"] = [None]
    payload["hourly"]["showers"] = [None]
    provider = OpenMeteoWeatherProvider(client(lambda r: httpx.Response(200, json=payload)), 1)
    [series] = provider.get_hourly([Coordinate(40, -88)], START, START)
    assert series.samples[START].snow_in_per_hr is None
    assert series.samples[START].rain_in_per_hr is None


def test_open_meteo_batches_points_and_isolates_chunk_failures():
    requests = []

    def handler(request):
        requests.append(request)
        count = len(request.url.params["latitude"].split(","))
        if request.url.params["latitude"].startswith("30.0000"):
            return httpx.Response(500)
        body = [open_meteo_location(1) for _ in range(count)]
        return httpx.Response(200, json=body if count > 1 else body[0])

    points = [Coordinate(30 + i * 0.01, -90) for i in range(120)]
    provider = OpenMeteoWeatherProvider(client(handler), concurrency=3)
    series = provider.get_hourly(points, START, START)
    assert len(series) == 120
    assert all(s is None for s in series[:50])
    assert all(s is not None for s in series[50:])
    batch_requests = {r.url.params["latitude"].split(",")[0] for r in requests}
    assert len(batch_requests) == 3


def test_open_meteo_requests_explicit_units_and_window():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=open_meteo_location(3))

    OpenMeteoWeatherProvider(client(handler), 1).get_hourly(
        [Coordinate(40, -88)], START, START + timedelta(hours=2)
    )
    assert seen["wind_speed_unit"] == "mph"
    assert seen["precipitation_unit"] == "mm"
    assert seen["start_hour"] == "2026-10-20T12:00"
    assert seen["end_hour"] == "2026-10-20T14:00"


# --- Photon ------------------------------------------------------------------


def test_photon_builds_labels_and_skips_invalid_coordinates():
    body = {
        "features": [
            {
                "geometry": {"coordinates": [-96.79, 32.77]},
                "properties": {"name": "Dallas", "state": "Texas", "country": "United States"},
            },
            {"geometry": {"coordinates": [500, 32.77]}, "properties": {"name": "Broken"}},
        ]
    }
    places = PhotonGeocodingProvider(client(lambda r: httpx.Response(200, json=body))).search(
        "Dallas", 5
    )
    assert len(places) == 1
    assert places[0].label == "Dallas, Texas, United States"
    assert places[0].coordinate == Coordinate(32.77, -96.79)
