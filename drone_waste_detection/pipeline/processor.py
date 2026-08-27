"""Single shared detection pipeline used by both application modes."""

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import cv2
import numpy as np

import config
from detection.frame_sampler import TimeFrameSampler
from detection.waste_registry import RegistryEvent, WasteRegistry
from detection.yolo_tracker import TrackedDetection, YoloTracker
from geolocation.camera_geometry import estimate_object_gps, fov_from_diagonal
from geolocation.srt_telemetry import VideoGPS
from pipeline.snapshots import SnapshotStore


@dataclass(frozen=True)
class ProcessedFrame:
    """Result returned to the live/batch runner for one input frame."""

    analyzed: bool
    display_frame: np.ndarray
    map_changed: bool
    video_time: timedelta


class DetectionPipeline:
    """Own all detection rules so live and batch results stay consistent."""

    def __init__(
        self,
        input_fps: float,
        image_width: int,
        image_height: int,
        *,
        verbose: bool = True,
        create_display_frame: bool = True,
    ) -> None:
        self.input_fps = float(input_fps)
        self.image_width = int(image_width)
        self.image_height = int(image_height)
        self.verbose = bool(verbose)
        self.create_display_frame = bool(create_display_frame)

        # Shared model/tracking, sampling, deduplication and telemetry objects.
        self.tracker = YoloTracker(
            model_path=str(config.MODEL_PATH),
            confidence_threshold=config.CONFIDENCE_THRESHOLD,
            tracker_config=config.TRACKER_CONFIG,
        )
        self.sampler = TimeFrameSampler(config.DETECTION_FPS)
        self.registry = WasteRegistry(
            duplicate_radius_m=config.DUPLICATE_RADIUS_M,
            min_confirmations=config.MIN_OBJECT_CONFIRMATIONS,
        )
        self.telemetry_reader = VideoGPS(
            config.SRT_PATH,
            default_altitude_m=config.DEFAULT_ALTITUDE_M,
            heading_source=config.HEADING_SOURCE,
            default_heading_deg=config.DEFAULT_HEADING_DEG,
            fixed_heading_deg=config.FIXED_HEADING_DEG,
            heading_min_displacement_m=config.HEADING_MIN_DISPLACEMENT_M,
        )
        self.snapshots = SnapshotStore(config.SNAPSHOT_DIR)

        self.horizontal_fov_deg, self.vertical_fov_deg = fov_from_diagonal(
            config.CAMERA_DIAGONAL_FOV_DEG,
            self.image_width,
            self.image_height,
        )

    def process_frame(self, frame: np.ndarray, frame_index: int) -> ProcessedFrame:
        """Process one video frame according to the shared temporal sampler."""
        video_seconds = frame_index / self.input_fps
        video_time = timedelta(seconds=video_seconds)

        if not self.sampler.should_process(video_seconds):
            return ProcessedFrame(False, frame, False, video_time)

        telemetry = self.telemetry_reader.get(video_time)
        detections, annotated_frame = self.tracker.track(
            frame,
            annotate=self.create_display_frame,
        )

        if detections and self.verbose:
            print(
                f"{video_time} | analyzed detections={len(detections)} | "
                f"altitude={telemetry.altitude_m:.2f} m | "
                f"heading={telemetry.heading_deg:.1f}°"
            )

        map_changed = False
        for detection in detections:
            event = self._handle_detection(frame, detection, video_time, telemetry)
            if event is not None and event.confirmed:
                # Averaged coordinates and/or registry metadata can change after
                # confirmation, so the map data should be refreshed.
                map_changed = True

        return ProcessedFrame(True, annotated_frame, map_changed, video_time)

    def _handle_detection(self, frame, detection: TrackedDetection, video_time, telemetry) -> RegistryEvent | None:
        """Geolocate one YOLO box, update registry state and save its screenshot."""
        try:
            object_gps = estimate_object_gps(
                drone_lat=telemetry.lat,
                drone_lon=telemetry.lon,
                altitude_m=telemetry.altitude_m,
                heading_deg=telemetry.heading_deg,
                center_x=detection.center_x,
                center_y=detection.center_y,
                image_width=frame.shape[1],
                image_height=frame.shape[0],
                diagonal_fov_deg=config.CAMERA_DIAGONAL_FOV_DEG,
                camera_pitch_deg=config.CAMERA_PITCH_DEG,
                camera_yaw_offset_deg=config.CAMERA_YAW_OFFSET_DEG,
                camera_roll_deg=config.CAMERA_ROLL_DEG,
            )
        except ValueError as exc:
            if self.verbose:
                print(f"  skipped geometry: {exc}")
            return None

        event = self.registry.observe(
            lat=object_gps["lat"],
            lon=object_gps["lon"],
            time=video_time,
            confidence=detection.confidence,
            track_id=detection.track_id,
            altitude_m=telemetry.altitude_m,
            heading_deg=telemetry.heading_deg,
            ground_distance_m=object_gps["ground_distance_m"],
        )

        # Store one contextual visual snapshot for each physical object. The exact same
        # screenshot logic is used in live and batch modes.
        self.snapshots.consider(
            object_id=event.object_id,
            confidence=detection.confidence,
            frame=frame,
            box_xyxy=detection.box_xyxy,
            confirmed=event.confirmed,
        )

        if event.is_new_object and self.verbose:
            print(
                f"  new candidate #{event.object_id} | track={detection.track_id} | "
                f"confidence={detection.confidence:.2f} | "
                f"GPS={object_gps['lat']:.7f}, {object_gps['lon']:.7f}"
            )
        elif event.distance_to_match_m is not None and self.verbose:
            print(
                f"  matched object #{event.object_id} | "
                f"distance={event.distance_to_match_m:.2f} m | "
                f"track={detection.track_id}"
            )

        if event.became_confirmed and self.verbose:
            print(f"  >>> CONFIRMED waste object #{event.object_id}")

        return event

    def confirmed_detections(self) -> list[dict]:
        """Return confirmed objects enriched with their screenshot paths."""
        detections = self.registry.confirmed_detections()
        for item in detections:
            screenshot = self.snapshots.path(item["object_id"])
            item["image_path"] = screenshot
        return detections
