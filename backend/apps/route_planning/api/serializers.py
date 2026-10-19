from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from apps.route_planning.application.dto import LocationInput, PlanCommand
from apps.route_planning.domain.enums import SamplingInterval
from apps.route_planning.domain.geometry import Coordinate

MAX_QUERY_LENGTH = 200
MAX_LOAD_WEIGHT_LB = 80_000
MAX_DEPARTURE_PAST = timedelta(hours=1)
MAX_DEPARTURE_AHEAD = timedelta(days=7)


class LocationSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=MAX_QUERY_LENGTH, trim_whitespace=True)
    lat = serializers.FloatField(min_value=-90, max_value=90, required=False, allow_null=True)
    lon = serializers.FloatField(min_value=-180, max_value=180, required=False, allow_null=True)

    def validate(self, attrs):
        has_lat = attrs.get("lat") is not None
        has_lon = attrs.get("lon") is not None
        if has_lat != has_lon:
            raise serializers.ValidationError("Provide both lat and lon, or neither.")
        return attrs

    def to_location(self, data) -> LocationInput:
        coordinate = Coordinate(data["lat"], data["lon"]) if data.get("lat") is not None else None
        return LocationInput(query=data["query"], coordinate=coordinate)


class RoutePlanRequestSerializer(serializers.Serializer):
    origin = LocationSerializer()
    destination = LocationSerializer()
    departure_time = serializers.DateTimeField(
        help_text="ISO 8601 with an explicit UTC offset, e.g. 2026-10-20T08:00:00-05:00."
    )
    load_weight_lb = serializers.IntegerField(min_value=1, max_value=MAX_LOAD_WEIGHT_LB)
    sampling_interval_miles = serializers.ChoiceField(
        choices=[interval.value for interval in SamplingInterval]
    )

    def to_internal_value(self, data):
        raw = data.get("departure_time") if isinstance(data, dict) else None
        if isinstance(raw, str) and not _has_offset(raw):
            raise serializers.ValidationError(
                {"departure_time": ["Include a UTC offset or 'Z' so the time is unambiguous."]}
            )
        return super().to_internal_value(data)

    def validate_departure_time(self, value):
        now = timezone.now()
        if value < now - MAX_DEPARTURE_PAST:
            raise serializers.ValidationError("Departure cannot be more than 1 hour in the past.")
        if value > now + MAX_DEPARTURE_AHEAD:
            raise serializers.ValidationError(
                "Departure must be within 7 days; forecasts beyond that are not reliable enough."
            )
        return value

    def validate(self, attrs):
        origin, destination = attrs["origin"], attrs["destination"]
        same_query = origin["query"].casefold() == destination["query"].casefold()
        same_point = (origin.get("lat"), origin.get("lon")) == (
            destination.get("lat"),
            destination.get("lon"),
        )
        if same_query and same_point:
            raise serializers.ValidationError(
                {"destination": ["Destination must differ from origin."]}
            )
        return attrs

    def to_command(self) -> PlanCommand:
        data = self.validated_data
        return PlanCommand(
            origin=LocationSerializer().to_location(data["origin"]),
            destination=LocationSerializer().to_location(data["destination"]),
            departure=data["departure_time"],
            load_weight_lb=data["load_weight_lb"],
            sampling_interval=SamplingInterval(data["sampling_interval_miles"]),
        )


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=3, max_length=MAX_QUERY_LENGTH, trim_whitespace=True)


def _has_offset(value: str) -> bool:
    tail = value.strip()[10:]
    return tail.endswith(("Z", "z")) or "+" in tail or "-" in tail
