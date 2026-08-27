"""Small geographic helper functions used by telemetry and camera geometry."""

import math

EARTH_RADIUS_M = 6_371_000.0


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in meters using the haversine formula."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_M * c


def bearing_degrees(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return initial bearing in degrees where 0=north and 90=east."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)

    y = math.sin(d_lambda) * math.cos(phi2)
    x = (
        math.cos(phi1) * math.sin(phi2)
        - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    )
    return math.degrees(math.atan2(y, x)) % 360.0


def offset_gps(
    latitude: float,
    longitude: float,
    north_m: float,
    east_m: float,
) -> dict[str, float]:
    """Apply a small local north/east meter offset to a GPS coordinate."""
    d_lat = north_m / EARTH_RADIUS_M
    cos_lat = math.cos(math.radians(latitude))
    if abs(cos_lat) < 1e-12:
        raise ValueError("Longitude offset is undefined near the poles.")

    d_lon = east_m / (EARTH_RADIUS_M * cos_lat)
    return {
        "lat": latitude + math.degrees(d_lat),
        "lon": longitude + math.degrees(d_lon),
    }
