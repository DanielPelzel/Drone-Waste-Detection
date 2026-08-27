"""YOLO object detection combined with ByteTrack temporal association."""

from dataclasses import dataclass
from typing import Optional

import numpy as np
from ultralytics import YOLO


@dataclass(frozen=True)
class TrackedDetection:
    """Normalized information required by the rest of the pipeline."""

    track_id: Optional[int]
    confidence: float
    center_x: float
    center_y: float
    box_xyxy: tuple[float, float, float, float]


class YoloTracker:
    """Run the trained YOLO model and keep ByteTrack state between frames."""

    def __init__(
        self,
        model_path: str,
        confidence_threshold: float,
        tracker_config: str = "bytetrack.yaml",
    ) -> None:
        self.model = YOLO(model_path)
        self.confidence_threshold = float(confidence_threshold)
        self.tracker_config = tracker_config

    def track(
        self,
        frame: np.ndarray,
        *,
        annotate: bool = True,
    ) -> tuple[list[TrackedDetection], np.ndarray]:
        """Detect waste, associate tracks and optionally create a display frame."""
        results = self.model.track(
            frame,
            conf=self.confidence_threshold,
            persist=True,
            tracker=self.tracker_config,
            verbose=False,
        )

        result = results[0]
        annotated_frame = result.plot() if annotate else frame
        boxes = result.boxes
        if boxes is None or len(boxes) == 0:
            return [], annotated_frame

        coordinates = boxes.xyxy.cpu().tolist()
        confidences = boxes.conf.cpu().tolist()
        track_ids = (
            boxes.id.int().cpu().tolist()
            if boxes.id is not None
            else [None] * len(coordinates)
        )

        detections: list[TrackedDetection] = []
        for box, confidence, track_id in zip(coordinates, confidences, track_ids):
            x1, y1, x2, y2 = map(float, box)
            detections.append(
                TrackedDetection(
                    track_id=int(track_id) if track_id is not None else None,
                    confidence=float(confidence),
                    center_x=(x1 + x2) / 2.0,
                    center_y=(y1 + y2) / 2.0,
                    box_xyxy=(x1, y1, x2, y2),
                )
            )

        return detections, annotated_frame
