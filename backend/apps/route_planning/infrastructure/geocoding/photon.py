"""Photon geocoding adapter (https://photon.komoot.io), backed by OpenStreetMap."""

from pydantic import BaseModel, ValidationError

from apps.route_planning.application.errors import ProviderResponseInvalid
from apps.route_planning.application.ports import Place
from apps.route_planning.domain.exceptions import InvalidGeometry
from apps.route_planning.domain.geometry import Coordinate
from apps.route_planning.infrastructure.http import ProviderHttpClient

PROVIDER = "photon"
ATTRIBUTION = "Geocoding by Photon (komoot), data © OpenStreetMap contributors"
LABEL_FIELDS = ("name", "street", "city", "county", "state", "country")


class _Geometry(BaseModel):
    coordinates: tuple[float, float]


class _Feature(BaseModel):
    geometry: _Geometry
    properties: dict[str, object]


class _Response(BaseModel):
    features: list[_Feature]


class PhotonGeocodingProvider:
    name = PROVIDER
    attribution = ATTRIBUTION

    def __init__(self, client: ProviderHttpClient) -> None:
        self._client = client

    def search(self, query: str, limit: int) -> list[Place]:
        payload = self._client.get_json("/api/", {"q": query, "limit": limit, "lang": "en"})
        try:
            parsed = _Response.model_validate(payload)
        except ValidationError as exc:
            raise ProviderResponseInvalid(PROVIDER, "unexpected geocoding response") from exc
        places = []
        for feature in parsed.features:
            lon, lat = feature.geometry.coordinates
            try:
                coordinate = Coordinate(lat, lon)
            except InvalidGeometry:
                continue
            places.append(Place(label=_label(feature.properties), coordinate=coordinate))
        return places


def _label(properties: dict[str, object]) -> str:
    parts: list[str] = []
    house = properties.get("housenumber")
    for field in LABEL_FIELDS:
        value = properties.get(field)
        if not isinstance(value, str) or not value or value in parts:
            continue
        if field == "street" and isinstance(house, str):
            value = f"{house} {value}"
        parts.append(value)
    return ", ".join(parts) or "Unnamed location"
