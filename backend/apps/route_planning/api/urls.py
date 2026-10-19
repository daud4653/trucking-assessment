from django.urls import path

from .views import (
    CorridorForecastView,
    GeocodeView,
    RoutePlanCollectionView,
    RoutePlanDetailView,
)

urlpatterns = [
    path("route-plans/", RoutePlanCollectionView.as_view(), name="route-plan-list"),
    path("route-plans/<uuid:plan_id>/", RoutePlanDetailView.as_view(), name="route-plan-detail"),
    path(
        "route-plans/<uuid:plan_id>/corridor-forecast/",
        CorridorForecastView.as_view(),
        name="corridor-forecast",
    ),
    path("geocode/", GeocodeView.as_view(), name="geocode"),
]
