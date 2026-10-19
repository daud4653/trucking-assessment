from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class ContentSecurityPolicyMiddleware:
    """Sets a restrictive CSP for the single-page app and API.

    The map renders tiles, glyphs and sprites from the configured tile host,
    builds workers from blob: URLs and applies inline styles to its canvas
    controls; everything else is same-origin.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response
        tiles = settings.MAP_TILE_ORIGIN
        self.policy = "; ".join(
            [
                "default-src 'self'",
                "script-src 'self'",
                "style-src 'self' 'unsafe-inline'",
                f"img-src 'self' data: blob: {tiles}",
                "font-src 'self'",
                f"connect-src 'self' {tiles}",
                "worker-src blob:",
                "child-src blob:",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
            ]
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.policy)
        return response
