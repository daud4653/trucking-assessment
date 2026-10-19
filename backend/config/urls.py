from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, JsonResponse
from django.urls import include, path, re_path


def frontend(request: HttpRequest) -> FileResponse:
    """Serve the built single-page app for client-side routes."""
    index = settings.FRONTEND_DIST_DIR / "index.html"
    if not index.is_file():
        raise Http404("Frontend build not found.")
    response = FileResponse(index.open("rb"), content_type="text/html")
    response["Cache-Control"] = "no-cache"
    return response


def api_not_found(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {"error": {"code": "not_found", "message": "Unknown API endpoint."}}, status=404
    )


urlpatterns = [
    path("api/v1/", include("apps.route_planning.api.urls")),
    path("api/v1/", include("apps.health.urls")),
    re_path(r"^api/", api_not_found),
    re_path(r"^(?!api/|static/).*$", frontend, name="frontend"),
]
