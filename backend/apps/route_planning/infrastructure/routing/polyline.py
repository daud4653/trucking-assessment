from apps.route_planning.domain.geometry import Coordinate


def decode_polyline(encoded: str, precision: int = 6) -> list[Coordinate]:
    """Decode a Google-style encoded polyline (Valhalla uses precision 6)."""
    factor = 10**precision
    coordinates: list[Coordinate] = []
    index = lat = lon = 0
    length = len(encoded)
    while index < length:
        deltas = []
        for _ in range(2):
            result = shift = 0
            while True:
                if index >= length:
                    raise ValueError("Truncated polyline.")
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        coordinates.append(Coordinate(lat / factor, lon / factor))
    return coordinates
