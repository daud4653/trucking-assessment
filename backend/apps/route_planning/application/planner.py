"""Route-planning use case: geocode, route, checkpoint, forecast, assess, rank."""

import string
from dataclasses import dataclass
from datetime import datetime

from apps.route_planning.domain.aggregation import AttributedRisk, summarize_route
from apps.route_planning.domain.checkpointing import CheckpointPlacement, generate_checkpoints
from apps.route_planning.domain.enums import DataStatus
from apps.route_planning.domain.geometry import (
    Coordinate,
    RouteGeometry,
    haversine_miles,
    simplify,
)
from apps.route_planning.domain.recommendation import (
    RankedRoute,
    RankingCandidate,
    ScreeningTier,
    rank_routes,
)
from apps.route_planning.domain.risk import assess_checkpoint
from apps.route_planning.domain.timing import TimingProfile
from apps.route_planning.domain.weather import (
    HOUR,
    WeatherReading,
    ceil_hour,
    floor_hour,
    select_reading,
)

from .dto import (
    AssessedCheckpoint,
    AssessedRoute,
    LocationInput,
    Notice,
    PlanCommand,
    PlanResult,
    ProviderInfo,
    ResolvedLocation,
)
from .errors import LocationNotFound, RouteNotFound, SameLocation
from .ports import (
    GeocodingProvider,
    ProviderRoute,
    RoutingProvider,
    TruckProfile,
    WeatherProvider,
)

MAX_ROUTES = 3
DISPLAY_TOLERANCE_DEGREES = 0.0002
MIN_TRIP_MILES = 0.5

_Readings = dict[tuple[str, int], WeatherReading | None]


@dataclass(frozen=True)
class _PlacedRoute:
    route_id: str
    label: str
    provider_order: int
    source: ProviderRoute
    timing: TimingProfile
    placements: list[CheckpointPlacement]


class RoutePlanner:
    def __init__(
        self,
        geocoder: GeocodingProvider,
        router: RoutingProvider,
        weather: WeatherProvider,
        tare_weight_lb: int,
    ) -> None:
        self._geocoder = geocoder
        self._router = router
        self._weather = weather
        self._tare_weight_lb = tare_weight_lb

    def plan(self, command: PlanCommand) -> PlanResult:
        origin = self._resolve(command.origin, "origin")
        destination = self._resolve(command.destination, "destination")
        if _too_close(origin.coordinate, destination.coordinate):
            raise SameLocation("Origin and destination resolve to the same place.")

        truck = TruckProfile(gross_weight_lb=self._tare_weight_lb + command.load_weight_lb)
        routing = self._router.get_routes(
            origin.coordinate, destination.coordinate, truck, MAX_ROUTES
        )
        if not routing.routes:
            raise RouteNotFound(routing.provider, "no routes returned")
        placed = [_place_route(index, route, command) for index, route in enumerate(routing.routes)]
        readings = self._forecast(placed, command.departure)
        assessed = _assess_routes(placed, readings, command.load_weight_lb)

        return PlanResult(
            origin=origin,
            destination=destination,
            departure=command.departure,
            load_weight_lb=command.load_weight_lb,
            sampling_interval=command.sampling_interval,
            routes=tuple(assessed),
            notices=tuple(_notices(assessed)),
            routing=ProviderInfo(routing.provider, routing.attribution, routing.profile),
            weather=ProviderInfo(self._weather.name, self._weather.attribution),
            geocoding=ProviderInfo(self._geocoder.name, self._geocoder.attribution),
        )

    def _resolve(self, location: LocationInput, field: str) -> ResolvedLocation:
        if location.coordinate is not None:
            return ResolvedLocation(location.query, location.query, location.coordinate)
        matches = self._geocoder.search(location.query, limit=1)
        if not matches:
            raise LocationNotFound(field, location.query)
        best = matches[0]
        return ResolvedLocation(location.query, best.label, best.coordinate)

    def _forecast(self, placed: list[_PlacedRoute], departure: datetime) -> _Readings:
        placements = [p for route in placed for p in route.placements]
        unique_points = list(dict.fromkeys(_weather_key(p.coordinate) for p in placements))
        start = floor_hour(departure)
        end = ceil_hour(max(p.eta for p in placements)) + HOUR
        series = self._weather.get_hourly(
            [Coordinate(lat, lon) for lat, lon in unique_points], start, end
        )
        by_point = dict(zip(unique_points, series, strict=True))
        return {
            (route.route_id, p.sequence): select_reading(
                by_point[_weather_key(p.coordinate)], p.eta
            )
            for route in placed
            for p in route.placements
        }


def _place_route(index: int, route: ProviderRoute, command: PlanCommand) -> _PlacedRoute:
    geometry = RouteGeometry.from_points(list(route.points), reported_miles=route.distance_miles)
    timing = TimingProfile.build(geometry, route.duration_seconds, list(route.timing_breakpoints))
    placements = generate_checkpoints(
        geometry, timing, command.sampling_interval, command.departure
    )
    return _PlacedRoute(
        route_id=f"route-{index + 1}",
        label=f"Route {string.ascii_uppercase[index]}",
        provider_order=index,
        source=route,
        timing=timing,
        placements=placements,
    )


def _assess_routes(
    placed: list[_PlacedRoute], readings: _Readings, load_lb: int
) -> list[AssessedRoute]:
    checkpoints_by_route = {
        route.route_id: [
            AssessedCheckpoint(
                checkpoint_id=f"{route.route_id}-cp-{p.sequence}",
                placement=p,
                reading=readings[(route.route_id, p.sequence)],
                risk=assess_checkpoint(readings[(route.route_id, p.sequence)], load_lb),
            )
            for p in route.placements
        ]
        for route in placed
    }
    summaries = {
        route.route_id: summarize_route(
            route.placements[-1].distance_miles,
            [
                AttributedRisk(c.placement.represented_miles, c.risk)
                for c in checkpoints_by_route[route.route_id]
            ],
        )
        for route in placed
    }
    rankings: dict[str, RankedRoute] = {
        ranked.route_id: ranked
        for ranked in rank_routes(
            [
                RankingCandidate(
                    route.route_id,
                    route.label,
                    route.provider_order,
                    round(route.timing.total_seconds),
                    summaries[route.route_id],
                )
                for route in placed
            ]
        )
    }
    return [
        AssessedRoute(
            route_id=route.route_id,
            label=route.label,
            display_geometry=tuple(simplify(route.source.points, DISPLAY_TOLERANCE_DEGREES)),
            distance_miles=route.placements[-1].distance_miles,
            duration_seconds=round(route.timing.total_seconds),
            arrival=route.placements[-1].eta,
            eta_is_approximate=route.timing.is_approximate,
            checkpoints=tuple(checkpoints_by_route[route.route_id]),
            summary=summaries[route.route_id],
            ranking=rankings[route.route_id],
        )
        for route in placed
    ]


def _notices(routes: list[AssessedRoute]) -> list[Notice]:
    notices = [
        Notice(
            "routing_scope",
            "Routes use the provider's truck profile with your load's estimated gross "
            "weight. They are not verified for height, hazmat, permits or local truck "
            "restrictions. Confirm legality before dispatch.",
            "info",
        )
    ]
    if len(routes) < MAX_ROUTES:
        notices.append(
            Notice(
                "fewer_alternatives",
                f"The routing provider returned {len(routes)} distinct route"
                f"{'s' if len(routes) != 1 else ''} for this trip instead of {MAX_ROUTES}.",
                "warning",
            )
        )
    tiers = {route.ranking.tier for route in routes}
    if tiers == {ScreeningTier.NO_TRAVEL}:
        notices.append(
            Notice(
                "all_routes_no_travel",
                "Every route has at least one checkpoint classified No Travel. None satisfies "
                "the wind, rain and snow thresholds at this departure time; consider a "
                "different departure.",
                "critical",
            )
        )
    missing = sum(
        1
        for route in routes
        for c in route.checkpoints
        if c.risk.data_status != DataStatus.COMPLETE
    )
    if missing:
        notices.append(
            Notice(
                "incomplete_weather",
                f"{missing} checkpoint{'s' if missing != 1 else ''} lack complete forecast data. "
                "Those miles are reported as unknown or as a minimum classification, never as "
                "low risk.",
                "warning",
            )
        )
    return notices


def _weather_key(coordinate: Coordinate) -> tuple[float, float]:
    return (round(coordinate.lat, 4), round(coordinate.lon, 4))


def _too_close(a: Coordinate, b: Coordinate) -> bool:
    return haversine_miles(a, b) < MIN_TRIP_MILES
