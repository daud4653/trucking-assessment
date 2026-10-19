import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import httpx

from apps.route_planning.application.errors import (
    ProviderRejected,
    ProviderResponseInvalid,
    ProviderUnavailable,
)

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
BACKOFF_BASE_SECONDS = 0.5
BACKOFF_JITTER_SECONDS = 0.25
MAX_RETRY_AFTER_SECONDS = 5.0


@dataclass(frozen=True)
class HttpSettings:
    user_agent: str
    connect_timeout: float
    read_timeout: float
    max_retries: int


class ProviderHttpClient:
    """JSON HTTP client with explicit timeouts and bounded, jittered retries.

    Only transport failures and RETRYABLE_STATUS responses are retried. A
    Retry-After longer than MAX_RETRY_AFTER_SECONDS fails fast rather than
    holding a request worker.
    """

    def __init__(
        self,
        provider: str,
        base_url: str,
        settings: HttpSettings,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.provider = provider
        self._settings = settings
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url,
            headers={"User-Agent": settings.user_agent, "Accept": "application/json"},
            timeout=httpx.Timeout(
                settings.read_timeout, connect=settings.connect_timeout, pool=settings.read_timeout
            ),
            transport=transport,
            follow_redirects=False,
        )

    def get_json(self, path: str, params: dict[str, Any]) -> Any:
        return self._request("GET", path, params=params)

    def post_json(self, path: str, body: dict[str, Any]) -> Any:
        return self._request("POST", path, json=body)

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        attempts = self._settings.max_retries + 1
        for attempt in range(attempts):
            last_attempt = attempt == attempts - 1
            try:
                response = self._client.request(method, path, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                logger.warning(
                    "provider transport failure",
                    extra={
                        "provider": self.provider,
                        "attempt": attempt,
                        "error": type(exc).__name__,
                    },
                )
                if last_attempt:
                    raise ProviderUnavailable(self.provider, "request failed or timed out") from exc
                self._sleep(self._backoff(attempt))
                continue

            if response.status_code in RETRYABLE_STATUS:
                delay = self._retry_delay(response, attempt)
                logger.warning(
                    "provider retryable status",
                    extra={"provider": self.provider, "status": response.status_code},
                )
                if last_attempt or delay is None:
                    raise ProviderUnavailable(
                        self.provider, f"temporarily unavailable (HTTP {response.status_code})"
                    )
                self._sleep(delay)
                continue

            if response.is_error:
                raise ProviderRejected(self.provider, response.status_code, _safe_json(response))
            try:
                return response.json()
            except ValueError as exc:
                raise ProviderResponseInvalid(self.provider, "response is not JSON") from exc
        raise ProviderUnavailable(self.provider, "retries exhausted")

    def _backoff(self, attempt: int) -> float:
        return BACKOFF_BASE_SECONDS * (2**attempt) + random.uniform(0, BACKOFF_JITTER_SECONDS)  # noqa: S311

    def _retry_delay(self, response: httpx.Response, attempt: int) -> float | None:
        header = response.headers.get("Retry-After")
        if header is None:
            return self._backoff(attempt)
        try:
            seconds = float(header)
        except ValueError:
            return self._backoff(attempt)
        return seconds if seconds <= MAX_RETRY_AFTER_SECONDS else None


def _safe_json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        return None
