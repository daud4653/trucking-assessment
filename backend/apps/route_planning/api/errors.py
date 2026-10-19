"""Uniform error responses: {"error": {"code", "message", "details"?}}.

Provider and internal failures are logged server-side; clients only see a
stable code and a safe message.
"""

import logging

from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from apps.route_planning.application.errors import (
    LocationNotFound,
    PlanningError,
    PlanNotFound,
    ProviderError,
    ProviderRejected,
    ProviderResponseInvalid,
    ProviderUnavailable,
    RouteNotFound,
    RouteTooLong,
    SameLocation,
)
from apps.route_planning.application.use_cases import (
    IdempotencyInProgress,
    IdempotencyKeyReused,
)
from apps.route_planning.domain.exceptions import DomainError

logger = logging.getLogger(__name__)


def error_response(
    code: str, message: str, http_status: int, details: dict | None = None, headers=None
) -> Response:
    body: dict = {"code": code, "message": message}
    if details:
        body["details"] = details
    return Response({"error": body}, status=http_status, headers=headers)


def api_exception_handler(exc, context):
    if isinstance(exc, PlanningError | ProviderError | DomainError):
        return _domain_response(exc)
    if isinstance(exc, exceptions.ValidationError):
        return error_response(
            "validation_error",
            "Some fields are invalid.",
            status.HTTP_400_BAD_REQUEST,
            details=exc.detail
            if isinstance(exc.detail, dict)
            else {"non_field_errors": exc.detail},
        )
    if isinstance(exc, exceptions.Throttled):
        wait = int(exc.wait) if exc.wait is not None else None
        return error_response(
            "rate_limited",
            "Too many requests. Please wait before trying again.",
            status.HTTP_429_TOO_MANY_REQUESTS,
            details={"retry_after_seconds": wait} if wait is not None else None,
            headers={"Retry-After": str(wait)} if wait is not None else None,
        )
    if isinstance(exc, Http404 | exceptions.NotFound):
        return error_response("not_found", "Not found.", status.HTTP_404_NOT_FOUND)

    response = exception_handler(exc, context)
    if response is not None:
        code = getattr(exc, "default_code", "error")
        detail = getattr(exc, "detail", "Request failed.")
        return error_response(str(code), str(detail), response.status_code)

    logger.exception("unhandled API error")
    return error_response(
        "internal_error", "An unexpected error occurred.", status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def _domain_response(exc: Exception) -> Response:
    match exc:
        case LocationNotFound():
            return error_response(
                exc.code,
                str(exc),
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={exc.field: [str(exc)]},
            )
        case SameLocation():
            return error_response(exc.code, str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
        case PlanNotFound():
            return error_response(exc.code, str(exc), status.HTTP_404_NOT_FOUND)
        case IdempotencyKeyReused():
            return error_response(exc.code, str(exc), status.HTTP_422_UNPROCESSABLE_ENTITY)
        case IdempotencyInProgress():
            return error_response(
                exc.code, str(exc), status.HTTP_409_CONFLICT, headers={"Retry-After": "2"}
            )
        case RouteNotFound():
            return error_response(
                "route_not_found",
                "No drivable truck route was found between these locations.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        case RouteTooLong():
            return error_response(
                "route_too_long",
                "This trip exceeds the routing provider's maximum distance (about 930 miles "
                "on the public server). Split the trip into shorter legs.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        case ProviderUnavailable() | ProviderRejected() | ProviderResponseInvalid():
            logger.warning("provider failure", extra={"provider": exc.provider, "error": str(exc)})
            return error_response(
                "provider_unavailable",
                f"The {exc.provider} service is unavailable right now. Try again in a minute.",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                details={"provider": exc.provider},
            )
        case DomainError():
            logger.warning("domain invariant failed", extra={"error": str(exc)})
            return error_response(
                "invalid_provider_data",
                "Route data from the provider could not be processed.",
                status.HTTP_502_BAD_GATEWAY,
            )
    logger.error("unmapped planning error", extra={"error": type(exc).__name__})
    return error_response(
        "internal_error", "An unexpected error occurred.", status.HTTP_500_INTERNAL_SERVER_ERROR
    )
