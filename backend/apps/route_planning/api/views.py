import hashlib
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.core.cache import cache
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.route_planning import wiring
from apps.route_planning.application import use_cases

from .errors import error_response
from .serializers import GeocodeQuerySerializer, RoutePlanRequestSerializer

MAX_IDEMPOTENCY_KEY_LENGTH = 255
GEOCODE_RESULT_LIMIT = 6


class RoutePlanCollectionView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "route_plan"

    def post(self, request: Request) -> Response:
        serializer = RoutePlanRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        key = request.headers.get("Idempotency-Key")
        if key is not None and not 0 < len(key) <= MAX_IDEMPOTENCY_KEY_LENGTH:
            return error_response(
                "invalid_idempotency_key",
                f"Idempotency-Key must be 1-{MAX_IDEMPOTENCY_KEY_LENGTH} characters.",
                status.HTTP_400_BAD_REQUEST,
            )
        outcome = use_cases.create_plan(
            wiring.planner(),
            serializer.to_command(),
            retention=timedelta(hours=settings.PLANNING["PLAN_RETENTION_HOURS"]),
            idempotency_key=key,
            client_scope=_client_scope(request),
        )
        headers = {"Location": f"/api/v1/route-plans/{outcome.plan_id}/"}
        if outcome.replayed:
            headers["Idempotent-Replayed"] = "true"
        return Response(outcome.payload, status=status.HTTP_201_CREATED, headers=headers)


class RoutePlanDetailView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "read"

    def get(self, request: Request, plan_id: UUID) -> Response:
        return Response(use_cases.get_plan(plan_id))


class CorridorForecastView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "corridor_forecast"

    def get(self, request: Request, plan_id: UUID) -> Response:
        payload = use_cases.get_corridor(
            wiring.corridor_forecaster(),
            cache,
            plan_id,
            ttl=settings.PLANNING["WEATHER_CACHE_SECONDS"],
        )
        return Response(payload)


class GeocodeView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "geocode"

    def get(self, request: Request) -> Response:
        serializer = GeocodeQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        geocoder = wiring.geocoder()
        places = geocoder.search(serializer.validated_data["q"], GEOCODE_RESULT_LIMIT)
        return Response(
            {
                "results": [
                    {"label": p.label, "lat": p.coordinate.lat, "lon": p.coordinate.lon}
                    for p in places
                ],
                "attribution": geocoder.attribution,
            }
        )


def _client_scope(request: Request) -> str:
    ident = ScopedRateThrottle().get_ident(request)
    salted = f"{settings.SECRET_KEY}:{ident}".encode()
    return hashlib.sha256(salted).hexdigest()
