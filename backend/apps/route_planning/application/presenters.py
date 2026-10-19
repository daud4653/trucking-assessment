"""Response contracts for the public API.

These functions are the single definition of the JSON returned to clients;
`frontend/src/features/route-planning/types/api.ts` mirrors them field for
field. Risk levels are strings in plan responses and integers 0-4 (same
order) in the compact corridor frames.
"""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from apps.route_planning.domain.aggregation import MIN_COVERAGE_RATIO
from apps.route_planning.domain.enums import RiskLevel
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.domain.risk import MetricAssessment

from .corridor import CorridorForecast
from .dto import AssessedCheckpoint, AssessedRoute, PlanCommand, PlanResult, ResolvedLocation

RISK_LEVEL_CODES = {
    RiskLevel.LOW: "low",
    RiskLevel.MODERATE: "moderate",
    RiskLevel.HIGH: "high",
    RiskLevel.SEVERE: "severe",
    RiskLevel.NO_TRAVEL: "no_travel",
}


def present_command(command: PlanCommand) -> dict[str, Any]:
    def location(loc) -> dict[str, Any]:
        coordinate = loc.coordinate
        return {
            "query": loc.query,
            "lat": coordinate.lat if coordinate else None,
            "lon": coordinate.lon if coordinate else None,
        }

    return {
        "origin": location(command.origin),
        "destination": location(command.destination),
        "departure_time": iso_utc(command.departure),
        "load_weight_lb": command.load_weight_lb,
        "sampling_interval_miles": int(command.sampling_interval),
    }


def present_plan(result: PlanResult) -> dict[str, Any]:
    recommended = next(r for r in result.routes if r.ranking.rank == 1)
    return {
        "origin": _location(result.origin),
        "destination": _location(result.destination),
        "departure_time": iso_utc(result.departure),
        "load_weight_lb": result.load_weight_lb,
        "sampling_interval_miles": int(result.sampling_interval),
        "recommended_route_id": recommended.route_id,
        "routes": [_route(route, recommended.route_id) for route in result.routes],
        "notices": [
            {"code": n.code, "message": n.message, "severity": n.severity} for n in result.notices
        ],
        "providers": {
            "routing": {
                "name": result.routing.name,
                "profile": result.routing.profile,
                "attribution": result.routing.attribution,
            },
            "weather": {"name": result.weather.name, "attribution": result.weather.attribution},
            "geocoding": {
                "name": result.geocoding.name,
                "attribution": result.geocoding.attribution,
            },
        },
        "methodology": {
            "min_coverage_ratio": float(MIN_COVERAGE_RATIO),
            "precipitation": "Mean intensity over the forecast hour containing the ETA.",
            "wind": "Sustained 10 m wind at the forecast hour nearest the ETA.",
        },
    }


def present_corridor(plan_id: str, forecast: CorridorForecast) -> dict[str, Any]:
    return {
        "plan_id": plan_id,
        "base_time": iso_utc(forecast.base_time),
        "cell_size_degrees": forecast.grid.cell_size,
        "cells": [list(cell.bounds) for cell in forecast.grid.cells],
        "frames": [
            {
                "offset_hours": index,
                "valid_time": iso_utc(frame.valid_time),
                "risk": list(frame.risk),
                "wind_mph": list(frame.wind_mph),
                "rain_in_per_hr": list(frame.rain_in_per_hr),
                "snow_in_per_hr": list(frame.snow_in_per_hr),
            }
            for index, frame in enumerate(forecast.frames)
        ],
        "retrieved_at": iso_utc(forecast.retrieved_at) if forecast.retrieved_at else None,
        "coverage_ratio": forecast.coverage_ratio,
        "attribution": forecast.attribution,
    }


def _location(location: ResolvedLocation) -> dict[str, Any]:
    return {
        "query": location.query,
        "label": location.label,
        "lat": location.coordinate.lat,
        "lon": location.coordinate.lon,
    }


def _route(route: AssessedRoute, recommended_id: str) -> dict[str, Any]:
    summary = route.summary
    return {
        "id": route.route_id,
        "label": route.label,
        "rank": route.ranking.rank,
        "screening": route.ranking.tier.name.lower(),
        "is_recommended": route.route_id == recommended_id,
        "ranking_explanation": route.ranking.explanation,
        "distance_miles": round(route.distance_miles, 2),
        "duration_seconds": route.duration_seconds,
        "arrival_time": iso_utc(route.arrival),
        "eta_method": "proportional" if route.eta_is_approximate else "provider_segments",
        "geometry": {
            "type": "LineString",
            "coordinates": [_lon_lat(point) for point in route.display_geometry],
        },
        "summary": {
            "total_miles": _float(summary.total_miles),
            "miles_by_level": {
                RISK_LEVEL_CODES[level]: _float(miles)
                for level, miles in summary.miles_by_level.items()
            },
            "severe_or_worse_miles": _float(summary.severe_or_worse_miles),
            "high_miles": _float(summary.high_miles),
            "unknown_miles": _float(summary.unknown_miles),
            "partial_miles": _float(summary.partial_miles),
            "coverage_ratio": _float(summary.coverage_ratio),
            "average_risk": _float(summary.average_risk),
            "peak_level": _level(summary.peak_level),
            "is_uncertain": summary.is_uncertain,
            "has_no_travel": summary.has_no_travel,
        },
        "checkpoints": [_checkpoint(c) for c in route.checkpoints],
    }


def _checkpoint(checkpoint: AssessedCheckpoint) -> dict[str, Any]:
    placement, risk, reading = checkpoint.placement, checkpoint.risk, checkpoint.reading
    adjustment = risk.load_adjustment
    return {
        "id": checkpoint.checkpoint_id,
        "sequence": placement.sequence,
        "distance_miles": round(placement.distance_miles, 2),
        "represents_from_miles": round(placement.represents_from_miles, 2),
        "represents_to_miles": round(placement.represents_to_miles, 2),
        "lat": round(placement.coordinate.lat, 5),
        "lon": round(placement.coordinate.lon, 5),
        "eta": iso_utc(placement.eta),
        "risk_level": _level(risk.level),
        "data_status": risk.data_status.value,
        "explanation": risk.explanation,
        "decisive_metrics": [metric.value for metric in risk.decisive_metrics],
        "metrics": [_metric(m) for m in risk.metrics],
        "load_adjustment": (
            {
                "rule": adjustment.rule_id,
                "description": adjustment.description,
                "from_level": _level(adjustment.from_level),
                "to_level": _level(adjustment.to_level),
            }
            if adjustment
            else None
        ),
        "weather": (
            {
                "valid_time": iso_utc(reading.valid_time),
                "precipitation_window_end": iso_utc(reading.precipitation_window_end),
                "retrieved_at": iso_utc(reading.retrieved_at),
                "wind_mph": _float(reading.wind_mph),
                "gust_mph": _float(reading.gust_mph),
                "rain_in_per_hr": _float(reading.rain_in_per_hr),
                "snow_in_per_hr": _float(reading.snow_in_per_hr),
            }
            if reading
            else None
        ),
    }


def _metric(metric: MetricAssessment) -> dict[str, Any]:
    return {
        "metric": metric.metric.value,
        "value": _float(metric.value),
        "unit": metric.unit,
        "level": _level(metric.level),
        "band": metric.band,
        "invalid": metric.invalid,
    }


def _level(level: RiskLevel | None) -> str | None:
    return RISK_LEVEL_CODES[level] if level is not None else None


def _float(value: Decimal | None) -> float | None:
    if value is None:
        return None
    return float(round(value, 4))


def _lon_lat(point: Coordinate) -> list[float]:
    return [round(point.lon, 5), round(point.lat, 5)]


def iso_utc(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
