"""Valhalla routing adapter (https://valhalla.github.io/valhalla/api/turn-by-turn/api-reference/).

Uses the `truck` costing model with the gross vehicle weight, so routing
avoids roads Valhalla's data marks as closed to heavy vehicles. It does not
model live traffic, permits, hazmat or every local restriction.
"""

from pydantic import BaseModel, ValidationError

from apps.route_planning.application.errors import (
    ProviderRejected,
    ProviderResponseInvalid,
    RouteNotFound,
    RouteTooLong,
)
from apps.route_planning.application.ports import ProviderRoute, RoutingResult, TruckProfile
from apps.route_planning.domain.exceptions import InvalidGeometry
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.timing import TimingBreakpoint
from apps.route_planning.infrastructure.http import ProviderHttpClient

from .polyline import decode_polyline

PROVIDER = "valhalla"
ATTRIBUTION = "Routing © Valhalla, map data © OpenStreetMap contributors"
POUNDS_PER_METRIC_TON = 2204.62262
NO_ROUTE_ERROR_CODES = frozenset({171, 442, 443})
DISTANCE_LIMIT_ERROR_CODES = frozenset({154})


class _Maneuver(BaseModel):
    time: float
    length: float
    begin_shape_index: int


class _Summary(BaseModel):
    time: float
    length: float


class _Leg(BaseModel):
    shape: str
    summary: _Summary
    maneuvers: list[_Maneuver]


class _Trip(BaseModel):
    legs: list[_Leg]
    summary: _Summary
    units: str


class _TripEnvelope(BaseModel):
    trip: _Trip


class _RouteResponse(BaseModel):
    trip: _Trip
    alternates: list[_TripEnvelope] = []


class ValhallaRoutingProvider:
    def __init__(self, client: ProviderHttpClient) -> None:
        self._client = client

    def get_routes(
        self,
        origin: Coordinate,
        destination: Coordinate,
        truck: TruckProfile,
        max_routes: int,
    ) -> RoutingResult:
        body = {
            "locations": [
                {"lat": origin.lat, "lon": origin.lon, "type": "break"},
                {"lat": destination.lat, "lon": destination.lon, "type": "break"},
            ],
            "costing": "truck",
            "costing_options": {
                "truck": {"weight": round(truck.gross_weight_lb / POUNDS_PER_METRIC_TON, 2)}
            },
            "alternates": max(0, max_routes - 1),
            "units": "miles",
            "directions_type": "maneuvers",
        }
        try:
            payload = self._client.post_json("/route", body)
        except ProviderRejected as exc:
            raise _translate_rejection(exc) from exc

        try:
            parsed = _RouteResponse.model_validate(payload)
        except ValidationError as exc:
            raise ProviderResponseInvalid(PROVIDER, "unexpected route response") from exc

        trips = [parsed.trip, *(alt.trip for alt in parsed.alternates)][:max_routes]
        routes = [_to_route(trip) for trip in trips]
        return RoutingResult(
            routes=tuple(_distinct(routes)),
            provider=PROVIDER,
            profile="truck",
            attribution=ATTRIBUTION,
        )


def _to_route(trip: _Trip) -> ProviderRoute:
    if trip.units != "miles" or len(trip.legs) != 1:
        raise ProviderResponseInvalid(PROVIDER, "unexpected units or leg count")
    leg = trip.legs[0]
    try:
        points = decode_polyline(leg.shape, precision=6)
    except (ValueError, InvalidGeometry) as exc:
        raise ProviderResponseInvalid(PROVIDER, "invalid route shape") from exc

    breakpoints = []
    elapsed = 0.0
    for maneuver in leg.maneuvers:
        breakpoints.append(TimingBreakpoint(maneuver.begin_shape_index, elapsed))
        elapsed += maneuver.time
    return ProviderRoute(
        points=tuple(points),
        distance_miles=trip.summary.length,
        duration_seconds=trip.summary.time,
        timing_breakpoints=tuple(breakpoints),
    )


def _distinct(routes: list[ProviderRoute]) -> list[ProviderRoute]:
    seen: set[tuple] = set()
    unique = []
    for route in routes:
        signature = _signature(route)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(route)
    return unique


def _signature(route: ProviderRoute) -> tuple:
    step = max(1, len(route.points) // 25)
    sampled = route.points[::step]
    return (round(route.distance_miles, 1), *((round(p.lat, 3), round(p.lon, 3)) for p in sampled))


def _translate_rejection(exc: ProviderRejected) -> Exception:
    body = exc.body if isinstance(exc.body, dict) else {}
    code = body.get("error_code")
    if code in NO_ROUTE_ERROR_CODES:
        return RouteNotFound(PROVIDER, "no route between the locations")
    if code in DISTANCE_LIMIT_ERROR_CODES:
        return RouteTooLong(PROVIDER, "route exceeds the provider's maximum distance")
    return exc
