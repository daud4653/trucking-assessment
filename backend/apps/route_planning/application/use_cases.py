"""Use cases exposed to the API: create/read plans and corridor forecasts.

Idempotency (Idempotency-Key header on plan creation):
* Keys are scoped to the caller (hashed client address) and live as long as
  the plan they produced (PLAN_RETENTION_HOURS).
* The first request inserts a PENDING row; the unique (scope, key)
  constraint makes concurrent duplicates fail atomically. A duplicate then
  gets the stored result (replay), "in progress" while the first request
  runs, or a rejection if the payload differs from the original.
* A failed plan deletes its row so the client can retry with the same key.
* A PENDING row older than STALE_PENDING (e.g. a crashed worker) is replaced.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from django.core.cache import BaseCache
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.models import RoutePlan

from .corridor import CorridorForecaster
from .dto import PlanCommand
from .errors import PlanningError, PlanNotFound
from .planner import RoutePlanner
from .presenters import iso_utc, present_command, present_corridor, present_plan

STALE_PENDING = timedelta(minutes=2)


class IdempotencyKeyReused(PlanningError):
    code = "idempotency_key_reused"


class IdempotencyInProgress(PlanningError):
    code = "idempotency_in_progress"


@dataclass(frozen=True)
class PlanResponse:
    payload: dict[str, Any]
    plan_id: UUID
    replayed: bool


def create_plan(
    planner: RoutePlanner,
    command: PlanCommand,
    retention: timedelta,
    idempotency_key: str | None = None,
    client_scope: str | None = None,
) -> PlanResponse:
    request = present_command(command)
    fingerprint = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
    record, replay = _reserve(request, fingerprint, retention, idempotency_key, client_scope)
    if replay:
        return PlanResponse(_payload(record), record.id, replayed=True)

    try:
        result = planner.plan(command)
    except BaseException:
        record.delete()
        raise
    record.result = present_plan(result)
    record.status = RoutePlan.Status.COMPLETE
    record.save(update_fields=["result", "status"])
    return PlanResponse(_payload(record), record.id, replayed=False)


def get_plan(plan_id: UUID) -> dict[str, Any]:
    return _payload(_complete_plan(plan_id))


def get_corridor(
    forecaster: CorridorForecaster, cache: BaseCache, plan_id: UUID, ttl: int
) -> dict[str, Any]:
    record = _complete_plan(plan_id)
    key = f"corridor:v1:{plan_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    result = record.result
    routes = [
        [Coordinate(lat, lon) for lon, lat in route["geometry"]["coordinates"]]
        for route in result["routes"]
    ]
    departure = datetime.fromisoformat(result["departure_time"])
    forecast = forecaster.forecast(routes, departure, result["load_weight_lb"])
    payload = present_corridor(str(plan_id), forecast)
    cache.set(key, payload, ttl)
    return payload


def purge_expired_plans() -> int:
    deleted, _ = RoutePlan.objects.filter(expires_at__lte=timezone.now()).delete()
    return deleted


def _reserve(
    request: dict[str, Any],
    fingerprint: str,
    retention: timedelta,
    key: str | None,
    scope: str | None,
) -> tuple[RoutePlan, bool]:
    def insert() -> RoutePlan:
        with transaction.atomic():
            return RoutePlan.objects.create(
                expires_at=timezone.now() + retention,
                request_fingerprint=fingerprint,
                idempotency_scope=scope if key else None,
                idempotency_key=key,
                request=request,
            )

    if key is None:
        return insert(), False
    for _ in range(2):
        try:
            return insert(), False
        except IntegrityError:
            existing = RoutePlan.objects.filter(
                idempotency_scope=scope, idempotency_key=key
            ).first()
            if existing is None:
                continue
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyKeyReused(
                    "This Idempotency-Key was already used with a different request."
                ) from None
            if _is_replayable(existing):
                return existing, True
            if not _is_abandoned(existing):
                raise IdempotencyInProgress(
                    "A request with this Idempotency-Key is still being processed."
                ) from None
            existing.delete()
    raise IdempotencyInProgress("Could not reserve the Idempotency-Key; retry shortly.")


def _is_replayable(record: RoutePlan) -> bool:
    return record.status == RoutePlan.Status.COMPLETE and record.expires_at > timezone.now()


def _is_abandoned(record: RoutePlan) -> bool:
    now = timezone.now()
    return record.expires_at <= now or (
        record.status == RoutePlan.Status.PENDING and now - record.created_at > STALE_PENDING
    )


def _complete_plan(plan_id: UUID) -> RoutePlan:
    record = RoutePlan.objects.filter(
        id=plan_id, status=RoutePlan.Status.COMPLETE, expires_at__gt=timezone.now()
    ).first()
    if record is None:
        raise PlanNotFound("Route plan not found or expired.")
    return record


def _payload(record: RoutePlan) -> dict[str, Any]:
    return {
        "id": str(record.id),
        "created_at": iso_utc(record.created_at),
        "expires_at": iso_utc(record.expires_at),
        **record.result,
    }
