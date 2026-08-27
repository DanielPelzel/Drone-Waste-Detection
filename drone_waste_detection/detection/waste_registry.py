"""Registry for confirming and deduplicating physical waste objects."""

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Optional

from geolocation.gps_utils import distance_meters


@dataclass
class WasteObject:
    """Accumulated state of one estimated physical waste item."""

    object_id: int
    lat: float
    lon: float
    first_seen: timedelta
    last_seen: timedelta
    best_confidence: float
    observations: int = 1
    confirmed: bool = False
    track_ids: set[int] = field(default_factory=set)
    altitude_m: float = 0.0
    heading_deg: float = 0.0
    ground_distance_m: float = 0.0


@dataclass(frozen=True)
class RegistryEvent:
    """Describe what happened when one detection was added to the registry."""

    object_id: int
    is_new_object: bool
    became_confirmed: bool
    confirmed: bool
    distance_to_match_m: float | None
    best_confidence: float


class WasteRegistry:
    """Merge repeated observations into unique physical waste objects.

    A known ByteTrack ID is checked first as a temporal shortcut. If no track ID
    match exists, the estimated geographic object position is compared against
    all known objects. Therefore a lost/reassigned tracker ID does not
    automatically create a duplicate map marker.
    """

    def __init__(self, duplicate_radius_m: float, min_confirmations: int = 2) -> None:
        if duplicate_radius_m <= 0:
            raise ValueError("duplicate_radius_m must be positive.")
        self.duplicate_radius_m = float(duplicate_radius_m)
        self.min_confirmations = max(1, int(min_confirmations))
        self.objects: list[WasteObject] = []
        self._track_to_object: dict[int, int] = {}
        self._next_object_id = 1

    def observe(
        self,
        *,
        lat: float,
        lon: float,
        time: timedelta,
        confidence: float,
        track_id: Optional[int],
        altitude_m: float,
        heading_deg: float,
        ground_distance_m: float,
    ) -> RegistryEvent:
        """Add one localized detection and return the resulting registry event."""
        matched: WasteObject | None = None
        match_distance: float | None = None

        # First try an already known ByteTrack identity.
        if track_id is not None and track_id in self._track_to_object:
            matched = self._get_by_id(self._track_to_object[track_id])
            match_distance = distance_meters(matched.lat, matched.lon, lat, lon)

        # If no temporal match exists, use the physical GPS estimate.
        if matched is None and self.objects:
            nearest = min(
                self.objects,
                key=lambda obj: distance_meters(obj.lat, obj.lon, lat, lon),
            )
            nearest_distance = distance_meters(nearest.lat, nearest.lon, lat, lon)
            if nearest_distance <= self.duplicate_radius_m:
                matched = nearest
                match_distance = nearest_distance

        # Create a new candidate if no existing object matches.
        if matched is None:
            obj = WasteObject(
                object_id=self._next_object_id,
                lat=lat,
                lon=lon,
                first_seen=time,
                last_seen=time,
                best_confidence=confidence,
                confirmed=self.min_confirmations <= 1,
                altitude_m=altitude_m,
                heading_deg=heading_deg,
                ground_distance_m=ground_distance_m,
            )
            if track_id is not None:
                obj.track_ids.add(track_id)
                self._track_to_object[track_id] = obj.object_id
            self.objects.append(obj)
            self._next_object_id += 1
            return RegistryEvent(
                object_id=obj.object_id,
                is_new_object=True,
                became_confirmed=obj.confirmed,
                confirmed=obj.confirmed,
                distance_to_match_m=None,
                best_confidence=obj.best_confidence,
            )

        # Update an existing object's averaged position and metadata.
        was_confirmed = matched.confirmed
        previous_n = matched.observations
        new_n = previous_n + 1
        matched.lat = (matched.lat * previous_n + lat) / new_n
        matched.lon = (matched.lon * previous_n + lon) / new_n
        matched.observations = new_n
        matched.last_seen = time
        matched.best_confidence = max(matched.best_confidence, confidence)
        matched.altitude_m = altitude_m
        matched.heading_deg = heading_deg
        matched.ground_distance_m = ground_distance_m
        matched.confirmed = matched.observations >= self.min_confirmations

        if track_id is not None:
            matched.track_ids.add(track_id)
            self._track_to_object[track_id] = matched.object_id

        return RegistryEvent(
            object_id=matched.object_id,
            is_new_object=False,
            became_confirmed=(not was_confirmed and matched.confirmed),
            confirmed=matched.confirmed,
            distance_to_match_m=match_distance,
            best_confidence=matched.best_confidence,
        )

    def confirmed_detections(self) -> list[dict]:
        """Return confirmed objects as serialization-friendly dictionaries."""
        result: list[dict] = []
        for obj in self.objects:
            if not obj.confirmed:
                continue
            result.append(
                {
                    "object_id": obj.object_id,
                    "lat": obj.lat,
                    "lon": obj.lon,
                    "time": obj.first_seen,
                    "last_seen": obj.last_seen,
                    "conf": obj.best_confidence,
                    "track_id": min(obj.track_ids) if obj.track_ids else None,
                    "track_ids": sorted(obj.track_ids),
                    "observations": obj.observations,
                    "altitude_m": obj.altitude_m,
                    "heading_deg": obj.heading_deg,
                    "ground_distance_m": obj.ground_distance_m,
                }
            )
        return result

    def _get_by_id(self, object_id: int) -> WasteObject:
        """Return one internal object by ID."""
        for obj in self.objects:
            if obj.object_id == object_id:
                return obj
        raise KeyError(object_id)
