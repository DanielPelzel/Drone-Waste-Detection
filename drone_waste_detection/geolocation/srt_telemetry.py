"""DJI SRT telemetry reader.

This module extends the project's original VideoGPS idea: the SRT is still
parsed by timestamp and nearest telemetry sample, but relative/absolute altitude
are retained as well. The original project contribution is therefore preserved
instead of being replaced by an unrelated GPS implementation.
"""

from bisect import bisect_left
from dataclasses import dataclass
from datetime import timedelta
import re
from pathlib import Path

from .gps_utils import bearing_degrees, distance_meters


@dataclass(frozen=True)
class Telemetry:
    timestamp: timedelta
    lat: float
    lon: float
    altitude_m: float
    absolute_altitude_m: float | None
    heading_deg: float


@dataclass(frozen=True)
class _SrtSample:
    timestamp: timedelta
    lat: float
    lon: float
    rel_alt: float | None
    abs_alt: float | None


class VideoGPS:
    """Extended version of the original project VideoGPS SRT reader."""

    TIME_RE = re.compile(r"(\d{2}:\d{2}:\d{2},\d+)\s*-->")
    LAT_RE = re.compile(r"\[latitude:\s*([-+]?\d+(?:\.\d+)?)")
    LON_RE = re.compile(r"\[longitude:\s*([-+]?\d+(?:\.\d+)?)")
    REL_ALT_RE = re.compile(r"\brel_alt:\s*([-+]?\d+(?:\.\d+)?)")
    ABS_ALT_RE = re.compile(r"\babs_alt:\s*([-+]?\d+(?:\.\d+)?)")

    def __init__(
        self,
        file_path: str | Path,
        default_altitude_m: float = 3.5,
        heading_source: str = "trajectory",
        default_heading_deg: float = 0.0,
        fixed_heading_deg: float = 0.0,
        heading_min_displacement_m: float = 0.5,
    ) -> None:
        self.file_path = Path(file_path)
        self.default_altitude_m = float(default_altitude_m)
        self.heading_source = heading_source.lower()
        self.default_heading_deg = float(default_heading_deg) % 360.0
        self.fixed_heading_deg = float(fixed_heading_deg) % 360.0
        self.heading_min_displacement_m = max(0.01, float(heading_min_displacement_m))

        if self.heading_source not in {"trajectory", "fixed"}:
            raise ValueError("heading_source must be 'trajectory' or 'fixed'.")

        self.samples = self._extract()
        if not self.samples:
            raise ValueError(f"No GPS telemetry found in SRT: {self.file_path}")
        self._times = [sample.timestamp.total_seconds() for sample in self.samples]
        self._trajectory_headings = self._build_trajectory_headings()

    def _read_file(self) -> list[str]:
        content = self.file_path.read_text(encoding="utf-8", errors="replace")
        return re.split(r"\r?\n\s*\r?\n", content.strip())

    @staticmethod
    def _parse_time(value: str) -> timedelta:
        hours, minutes, rest = value.split(":")
        seconds, milliseconds = rest.split(",")
        return timedelta(
            hours=int(hours),
            minutes=int(minutes),
            seconds=int(seconds),
            milliseconds=int(milliseconds),
        )

    @staticmethod
    def _optional_float(match: re.Match[str] | None) -> float | None:
        return float(match.group(1)) if match is not None else None

    def _extract(self) -> list[_SrtSample]:
        samples: list[_SrtSample] = []
        for block in self._read_file():
            time_match = self.TIME_RE.search(block)
            lat_match = self.LAT_RE.search(block)
            lon_match = self.LON_RE.search(block)
            if not (time_match and lat_match and lon_match):
                continue

            samples.append(
                _SrtSample(
                    timestamp=self._parse_time(time_match.group(1)),
                    lat=float(lat_match.group(1)),
                    lon=float(lon_match.group(1)),
                    rel_alt=self._optional_float(self.REL_ALT_RE.search(block)),
                    abs_alt=self._optional_float(self.ABS_ALT_RE.search(block)),
                )
            )
        return samples

    def _nearest_index(self, current_time: timedelta) -> int:
        target = current_time.total_seconds()
        idx = bisect_left(self._times, target)
        if idx <= 0:
            return 0
        if idx >= len(self._times):
            return len(self._times) - 1
        before = idx - 1
        return idx if abs(self._times[idx] - target) < abs(self._times[before] - target) else before

    def _bearing_near_index(self, index: int) -> float | None:
        """Estimate local flight bearing using sufficiently separated GPS points.

        This is trajectory direction, not guaranteed body yaw. It is nevertheless
        useful when the SRT contains no yaw/heading and the drone flies mostly
        forward along its trajectory.
        """
        current = self.samples[index]

        # Prefer a symmetric local direction around the sample.
        for radius in range(1, len(self.samples)):
            left = max(0, index - radius)
            right = min(len(self.samples) - 1, index + radius)
            a = self.samples[left]
            b = self.samples[right]
            if distance_meters(a.lat, a.lon, b.lat, b.lon) >= self.heading_min_displacement_m:
                return bearing_degrees(a.lat, a.lon, b.lat, b.lon)
            if left == 0 and right == len(self.samples) - 1:
                break

        # If the entire trajectory is effectively stationary, no bearing exists.
        if distance_meters(current.lat, current.lon, self.samples[0].lat, self.samples[0].lon) < self.heading_min_displacement_m:
            return None
        return None

    def _build_trajectory_headings(self) -> list[float]:
        raw: list[float | None] = [self._bearing_near_index(i) for i in range(len(self.samples))]

        # Fill missing values from the nearest known heading, allowing initial
        # stationary footage to inherit the first meaningful flight direction.
        known_indices = [i for i, value in enumerate(raw) if value is not None]
        if not known_indices:
            return [self.default_heading_deg] * len(raw)

        headings: list[float] = []
        for i, value in enumerate(raw):
            if value is not None:
                headings.append(value)
                continue
            nearest = min(known_indices, key=lambda j: abs(j - i))
            headings.append(float(raw[nearest]))
        return headings

    def get_gps_from_time(self, current_time: timedelta) -> dict[str, float | timedelta | None]:
        """Compatibility method retaining the original project's interface."""
        index = self._nearest_index(current_time)
        sample = self.samples[index]
        heading = (
            self.fixed_heading_deg
            if self.heading_source == "fixed"
            else self._trajectory_headings[index]
        )
        return {
            "timestamp": sample.timestamp,
            "lat": sample.lat,
            "lon": sample.lon,
            "rel_alt": sample.rel_alt,
            "abs_alt": sample.abs_alt,
            "heading": heading,
        }

    def get(self, current_time: timedelta) -> Telemetry:
        raw = self.get_gps_from_time(current_time)
        altitude = raw["rel_alt"]
        if altitude is None or float(altitude) <= 0:
            altitude = self.default_altitude_m

        return Telemetry(
            timestamp=raw["timestamp"],
            lat=float(raw["lat"]),
            lon=float(raw["lon"]),
            altitude_m=float(altitude),
            absolute_altitude_m=(float(raw["abs_alt"]) if raw["abs_alt"] is not None else None),
            heading_deg=float(raw["heading"]) % 360.0,
        )
