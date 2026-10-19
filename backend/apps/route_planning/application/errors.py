class ProviderError(Exception):
    """An external provider could not satisfy a request."""

    def __init__(self, provider: str, message: str) -> None:
        super().__init__(f"{provider}: {message}")
        self.provider = provider


class ProviderUnavailable(ProviderError):
    """Timeouts, connection failures, rate limiting or 5xx after retries."""


class ProviderRejected(ProviderError):
    """The provider refused the request (non-retryable 4xx)."""

    def __init__(self, provider: str, status_code: int, body: object = None) -> None:
        super().__init__(provider, f"HTTP {status_code}")
        self.status_code = status_code
        self.body = body


class ProviderResponseInvalid(ProviderError):
    """The provider answered with a payload that does not match its contract."""


class RouteNotFound(ProviderError):
    """The routing provider found no drivable route between the locations."""


class RouteTooLong(ProviderError):
    """The route exceeds the routing provider's distance limit."""


class PlanningError(Exception):
    """Errors raised by use cases that map to client-visible responses."""

    code = "planning_failed"


class LocationNotFound(PlanningError):
    code = "location_not_found"

    def __init__(self, field: str, query: str) -> None:
        super().__init__(f"No location matched '{query}'.")
        self.field = field


class SameLocation(PlanningError):
    code = "same_location"


class PlanNotFound(PlanningError):
    code = "plan_not_found"
