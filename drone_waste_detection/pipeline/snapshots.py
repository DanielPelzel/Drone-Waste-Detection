"""Detection screenshot management shared by live and batch processing."""

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class _SnapshotCandidate:
    """Best pre-confirmation visual candidate for one physical waste object."""

    confidence: float
    image: np.ndarray


class SnapshotStore:
    """Create one stable context screenshot for each confirmed waste object.

    Before an object is confirmed, the store keeps the clearest candidate based
    on detection confidence. As soon as the object becomes confirmed, that
    candidate is written once and then kept unchanged. Avoiding repeated writes
    also prevents the live browser from ever reading a JPEG while it is being
    replaced.
    """

    # The context crop should show enough surroundings to help a person locate
    # the item while keeping the detected object clearly visible.
    CONTEXT_SCALE = 4.0
    MIN_CONTEXT_WIDTH_FRACTION = 0.25
    MIN_CONTEXT_HEIGHT_FRACTION = 0.25

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._candidates: dict[int, _SnapshotCandidate] = {}
        self._paths: dict[int, Path] = {}

    @classmethod
    def _context_snapshot(
        cls,
        frame: np.ndarray,
        box_xyxy: tuple[float, float, float, float],
        object_id: int,
    ) -> np.ndarray:
        """Return a context crop with the detected object visibly marked."""
        frame_height, frame_width = frame.shape[:2]
        x1, y1, x2, y2 = box_xyxy

        # Compute a crop centered on the detection. Its size is at least four
        # bounding boxes wide/high and at least one quarter of the full frame.
        box_width = max(1.0, x2 - x1)
        box_height = max(1.0, y2 - y1)
        crop_width = min(
            frame_width,
            max(box_width * cls.CONTEXT_SCALE, frame_width * cls.MIN_CONTEXT_WIDTH_FRACTION),
        )
        crop_height = min(
            frame_height,
            max(box_height * cls.CONTEXT_SCALE, frame_height * cls.MIN_CONTEXT_HEIGHT_FRACTION),
        )

        center_x = (x1 + x2) / 2.0
        center_y = (y1 + y2) / 2.0
        left = int(round(center_x - crop_width / 2.0))
        top = int(round(center_y - crop_height / 2.0))

        # Shift the crop back inside the frame instead of shrinking it near an
        # image edge. This preserves as much environmental context as possible.
        left = max(0, min(left, frame_width - int(round(crop_width))))
        top = max(0, min(top, frame_height - int(round(crop_height))))
        right = min(frame_width, left + int(round(crop_width)))
        bottom = min(frame_height, top + int(round(crop_height)))

        image = frame[top:bottom, left:right].copy()
        if image.size == 0:
            return image

        # Convert the original YOLO coordinates into crop-local coordinates and
        # draw a clear box so the object remains obvious despite the wider view.
        local_x1 = max(0, min(image.shape[1] - 1, int(round(x1)) - left))
        local_y1 = max(0, min(image.shape[0] - 1, int(round(y1)) - top))
        local_x2 = max(0, min(image.shape[1] - 1, int(round(x2)) - left))
        local_y2 = max(0, min(image.shape[0] - 1, int(round(y2)) - top))

        thickness = max(2, int(round(min(image.shape[:2]) / 180)))
        cv2.rectangle(
            image,
            (local_x1, local_y1),
            (local_x2, local_y2),
            (0, 255, 0),
            thickness,
        )

        label = f"Waste Object {object_id}"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = max(0.45, min(0.8, image.shape[1] / 900.0))
        (text_width, text_height), baseline = cv2.getTextSize(
            label, font, font_scale, max(1, thickness - 1)
        )
        label_top = max(0, local_y1 - text_height - baseline - 6)
        label_bottom = min(image.shape[0] - 1, label_top + text_height + baseline + 6)
        label_right = min(image.shape[1] - 1, local_x1 + text_width + 8)
        cv2.rectangle(
            image,
            (local_x1, label_top),
            (label_right, label_bottom),
            (0, 255, 0),
            -1,
        )
        cv2.putText(
            image,
            label,
            (local_x1 + 4, label_bottom - baseline - 3),
            font,
            font_scale,
            (0, 0, 0),
            max(1, thickness - 1),
            cv2.LINE_AA,
        )
        return image

    def consider(
        self,
        object_id: int,
        confidence: float,
        frame: np.ndarray,
        box_xyxy: tuple[float, float, float, float],
        confirmed: bool,
    ) -> None:
        """Keep the best candidate and save it once when confirmation occurs."""
        # Once a screenshot has been written, keep it stable for the remainder
        # of the run. This gives the live map a reliable image source.
        if object_id in self._paths:
            return

        current = self._candidates.get(object_id)
        if current is None or confidence > current.confidence:
            image = self._context_snapshot(frame, box_xyxy, object_id)
            if image.size > 0:
                self._candidates[object_id] = _SnapshotCandidate(confidence, image)

        if confirmed and object_id in self._candidates:
            path = self.output_dir / f"waste_{object_id:03d}.jpg"
            written = cv2.imwrite(str(path), self._candidates[object_id].image)
            if written:
                self._paths[object_id] = path

    def relative_path(self, object_id: int, root: Path) -> str | None:
        """Return a POSIX-style path relative to a web/output root."""
        path = self._paths.get(object_id)
        if path is None:
            return None
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    def path(self, object_id: int) -> Path | None:
        """Return the saved screenshot path for one confirmed object."""
        return self._paths.get(object_id)
