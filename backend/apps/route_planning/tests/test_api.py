import threading
import uuid
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.route_planning.application.errors import ProviderUnavailable, RouteTooLong
from apps.route_planning.models import RoutePlan

from .fakes import FakeRouter, FakeWeather

pytestmark = pytest.mark.django_db
URL = "/api/v1/route-plans/"


def test_create_plan_returns_contract(api, providers, plan_body):
    response = api.post(URL, plan_body, format="json")
    assert response.status_code == 201
    body = response.json()
    assert response["Location"] == f"{URL}{body['id']}/"
    assert len(body["routes"]) == 3
    assert body["recommended_route_id"] == next(r["id"] for r in body["routes"] if r["rank"] == 1)
    route = body["routes"][0]
    assert set(route) >= {
        "id",
        "label",
        "rank",
        "screening",
        "is_recommended",
        "ranking_explanation",
        "distance_miles",
        "duration_seconds",
        "arrival_time",
        "eta_method",
        "geometry",
        "summary",
        "checkpoints",
    }
    assert route["geometry"]["type"] == "LineString"
    checkpoint = route["checkpoints"][1]
    assert checkpoint["id"] == "route-1-cp-1"
    assert checkpoint["risk_level"] == "low"
    assert checkpoint["eta"].endswith("Z")
    assert checkpoint["weather"]["wind_mph"] == 5.0
    assert route["summary"]["miles_by_level"]["low"] == route["summary"]["total_miles"]


def test_get_plan_round_trips(api, providers, plan_body):
    created = api.post(URL, plan_body, format="json").json()
    fetched = api.get(f"{URL}{created['id']}/")
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_unknown_or_expired_plan_is_404(api, providers, plan_body):
    assert api.get(f"{URL}{uuid.uuid4()}/").json()["error"]["code"] == "plan_not_found"
    created = api.post(URL, plan_body, format="json").json()
    RoutePlan.objects.filter(id=created["id"]).update(expires_at=timezone.now())
    assert api.get(f"{URL}{created['id']}/").status_code == 404


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("load_weight_lb", 0),
        ("load_weight_lb", -5),
        ("load_weight_lb", 80_001),
        ("load_weight_lb", "heavy"),
        ("sampling_interval_miles", 30),
        ("departure_time", "2026-10-20T08:00:00"),
        ("departure_time", "not a date"),
    ],
)
def test_validation_errors_use_error_schema(api, providers, plan_body, field, value):
    plan_body[field] = value
    response = api.post(URL, plan_body, format="json")
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "validation_error"
    assert field in error["details"]


def test_departure_window_is_enforced(api, providers, plan_body):
    plan_body["departure_time"] = (timezone.now() - timedelta(hours=3)).isoformat()
    assert api.post(URL, plan_body, format="json").status_code == 400
    plan_body["departure_time"] = (timezone.now() + timedelta(days=8)).isoformat()
    assert api.post(URL, plan_body, format="json").status_code == 400


def test_query_length_and_coordinate_pairs(api, providers, plan_body):
    plan_body["origin"] = {"query": "x" * 201}
    assert api.post(URL, plan_body, format="json").status_code == 400
    plan_body["origin"] = {"query": "Yard", "lat": 41.0}
    assert api.post(URL, plan_body, format="json").status_code == 400


def test_identical_origin_and_destination_rejected(api, providers, plan_body):
    plan_body["destination"] = {"query": "chicago"}
    response = api.post(URL, plan_body, format="json")
    assert response.status_code == 400
    assert "destination" in response.json()["error"]["details"]


def test_unknown_location_is_422(api, providers, plan_body):
    plan_body["destination"] = {"query": "Atlantis"}
    response = api.post(URL, plan_body, format="json")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "location_not_found"
    assert RoutePlan.objects.count() == 0


def test_routing_outage_is_503_without_internal_details(api, providers, plan_body):
    providers.router = FakeRouter(error=ProviderUnavailable("valhalla", "secret internals"))
    response = api.post(URL, plan_body, format="json")
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "provider_unavailable"
    assert "secret internals" not in error["message"]


def test_route_too_long_is_422(api, providers, plan_body):
    providers.router = FakeRouter(error=RouteTooLong("valhalla", "limit"))
    assert api.post(URL, plan_body, format="json").json()["error"]["code"] == "route_too_long"


def test_weather_provider_exception_is_503(api, providers, plan_body):
    providers.weather = FakeWeather(unavailable=True)
    response = api.post(URL, plan_body, format="json")
    assert response.status_code == 503


def test_no_weather_at_all_is_uncertain_never_low(api, providers, plan_body, departure):
    providers.weather = FakeWeather(missing_after=departure - timedelta(hours=5))
    body = api.post(URL, plan_body, format="json").json()
    for route in body["routes"]:
        assert route["screening"] == "uncertain"
        assert route["summary"]["coverage_ratio"] == 0
        assert route["summary"]["average_risk"] is None
        assert route["summary"]["miles_by_level"]["low"] == 0


def test_partial_weather_is_reported(api, providers, plan_body, departure):
    providers.weather = FakeWeather(missing_after=departure + timedelta(hours=1))
    body = api.post(URL, plan_body, format="json").json()
    route = body["routes"][0]
    assert route["screening"] == "uncertain"
    assert route["summary"]["unknown_miles"] > 0
    assert route["summary"]["miles_by_level"]["low"] < route["summary"]["total_miles"]
    unknown = [c for c in route["checkpoints"] if c["data_status"] == "unavailable"]
    assert unknown
    assert all(c["risk_level"] is None for c in unknown)
    assert "incomplete_weather" in {n["code"] for n in body["notices"]}


def test_idempotent_replay_returns_same_plan(api, providers, plan_body):
    headers = {"HTTP_IDEMPOTENCY_KEY": "abc-123"}
    first = api.post(URL, plan_body, format="json", **headers)
    second = api.post(URL, plan_body, format="json", **headers)
    assert first.status_code == second.status_code == 201
    assert second["Idempotent-Replayed"] == "true"
    assert first.json()["id"] == second.json()["id"]
    assert RoutePlan.objects.count() == 1


def test_idempotency_key_reuse_with_different_payload(api, providers, plan_body):
    headers = {"HTTP_IDEMPOTENCY_KEY": "abc-123"}
    api.post(URL, plan_body, format="json", **headers)
    plan_body["load_weight_lb"] = 10_000
    response = api.post(URL, plan_body, format="json", **headers)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "idempotency_key_reused"


def test_idempotency_key_in_progress(api, providers, plan_body):
    headers = {"HTTP_IDEMPOTENCY_KEY": "busy"}
    api.post(URL, plan_body, format="json", **headers)
    RoutePlan.objects.update(status=RoutePlan.Status.PENDING, result=None)
    response = api.post(URL, plan_body, format="json", **headers)
    assert response.status_code == 409
    assert response["Retry-After"] == "2"


def test_failed_plan_releases_idempotency_key(api, providers, plan_body):
    headers = {"HTTP_IDEMPOTENCY_KEY": "retry-me"}
    providers.router = FakeRouter(error=ProviderUnavailable("valhalla", "down"))
    assert api.post(URL, plan_body, format="json", **headers).status_code == 503
    providers.router = FakeRouter()
    assert api.post(URL, plan_body, format="json", **headers).status_code == 201


@pytest.mark.django_db(transaction=True)
def test_concurrent_duplicate_requests_create_one_plan(providers, plan_body):
    barrier = threading.Barrier(4)
    statuses = []

    def submit():
        barrier.wait()
        response = APIClient().post(URL, plan_body, format="json", HTTP_IDEMPOTENCY_KEY="race")
        statuses.append(response.status_code)
        connection.close()

    threads = [threading.Thread(target=submit) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert RoutePlan.objects.filter(idempotency_key="race").count() == 1
    assert set(statuses) <= {201, 409}
    assert 201 in statuses


def test_plan_endpoint_is_rate_limited(api, providers, plan_body, monkeypatch):
    rates = {**ScopedRateThrottle.THROTTLE_RATES, "route_plan": "2/hour"}
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", rates)
    codes = [api.post(URL, plan_body, format="json").status_code for _ in range(2)]
    assert codes == [201, 201]
    limited = api.post(URL, plan_body, format="json")
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "rate_limited"
    assert int(limited["Retry-After"]) > 0


def test_corridor_forecast_endpoint(api, providers, plan_body):
    plan = api.post(URL, plan_body, format="json").json()
    response = api.get(f"{URL}{plan['id']}/corridor-forecast/")
    assert response.status_code == 200
    body = response.json()
    assert len(body["frames"]) == 49
    assert [f["offset_hours"] for f in body["frames"]] == list(range(49))
    assert len(body["frames"][0]["risk"]) == len(body["cells"])
    cached = api.get(f"{URL}{plan['id']}/corridor-forecast/")
    assert cached.json() == body


def test_geocode_endpoint(api, providers):
    response = api.get("/api/v1/geocode/", {"q": "Chicago"})
    assert response.status_code == 200
    assert response.json()["results"][0]["lat"] == pytest.approx(41.8781)
    assert api.get("/api/v1/geocode/", {"q": "ab"}).status_code == 400


def test_non_json_body_rejected(api, providers):
    response = api.post(URL, "origin=x", content_type="application/x-www-form-urlencoded")
    assert response.status_code == 415


def test_health_and_readiness(api):
    assert api.get("/api/v1/health/").json() == {"status": "ok"}
    ready = api.get("/api/v1/ready/")
    assert ready.status_code == 200
    assert ready.json()["checks"] == {"database": True, "cache": True}


def test_unknown_api_path_returns_json_error(api):
    response = api.get("/api/v1/does-not-exist/")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_security_headers(api):
    response = api.get("/api/v1/health/")
    policy = response["Content-Security-Policy"]
    assert "default-src 'self'" in policy
    assert "frame-ancestors 'none'" in policy
    assert response["X-Content-Type-Options"] == "nosniff"
