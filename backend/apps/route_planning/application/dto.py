from dataclasses import dataclass
from datetime import datetime

from apps.route_planning.domain.aggregation import RouteRiskSummary
from apps.route_planning.domain.checkpointing import CheckpointPlacement
from apps.route_planning.domain.enums import SamplingInterval
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.recommendation import RankedRoute
from apps.route_planning.domain.risk import CheckpointRisk
from apps.route_planning.domain.weather import WeatherReading


@dataclass(frozen=True)
class LocationInput:
    query: str
    coordinate: Coordinate | None


@dataclass(frozen=True)
class PlanCommand:
    origin: LocationInput
    destination: LocationInput
    departure: datetime
    load_weight_lb: int
    sampling_interval: SamplingInterval


@dataclass(frozen=True)
class ResolvedLocation:
    query: str
    label: str
    coordinate: Coordinate


@dataclass(frozen=True)
class AssessedCheckpoint:
    checkpoint_id: str
    placement: CheckpointPlacement
    reading: WeatherReading | None
    risk: CheckpointRisk


@dataclass(frozen=True)
class AssessedRoute:
    route_id: str
    label: str
    display_geometry: tuple[Coordinate, ...]
    distance_miles: float
    duration_seconds: int
    arrival: datetime
    eta_is_approximate: bool
    checkpoints: tuple[AssessedCheckpoint, ...]
    summary: RouteRiskSummary
    ranking: RankedRoute


@dataclass(frozen=True)
class Notice:
    code: str
    message: str
    severity: str


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    attribution: str
    profile: str | None = None


@dataclass(frozen=True)
class PlanResult:
    origin: ResolvedLocation
    destination: ResolvedLocation
    departure: datetime
    load_weight_lb: int
    sampling_interval: SamplingInterval
    routes: tuple[AssessedRoute, ...]
    notices: tuple[Notice, ...]
    routing: ProviderInfo
    weather: ProviderInfo
    geocoding: ProviderInfo
