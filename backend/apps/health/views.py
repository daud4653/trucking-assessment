from django.core.cache import cache
from django.db import DatabaseError, connection
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness: the process is serving requests."""

    def get(self, request: Request) -> Response:
        return Response({"status": "ok"})


class ReadinessView(APIView):
    """Readiness: required local dependencies (database, cache) respond.

    External providers are deliberately not probed: their outages degrade
    individual requests and are reported per request, and probing them here
    would spend their quota on every load-balancer check.
    """

    def get(self, request: Request) -> Response:
        checks = {"database": _database_ok(), "cache": _cache_ok()}
        ready = all(checks.values())
        return Response(
            {"status": "ready" if ready else "unavailable", "checks": checks},
            status=200 if ready else 503,
        )


def _database_ok() -> bool:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except DatabaseError:
        return False
    return True


def _cache_ok() -> bool:
    try:
        cache.set("readiness-probe", "1", 10)
        return cache.get("readiness-probe") == "1"
    except DatabaseError:
        return False
