"""Shared runtime helpers for opening video input and printing final results."""

from pathlib import Path

import cv2

import config


def validate_required_files() -> None:
    """Fail early with actionable messages if a required input is missing."""
    required = (
        ("Video", config.VIDEO_PATH),
        ("SRT telemetry", config.SRT_PATH),
        ("YOLO model", config.MODEL_PATH),
    )
    missing = [(name, path) for name, path in required if not Path(path).exists()]
    if not missing:
        return

    lines = ["Required project file(s) are missing:"]
    for name, path in missing:
        lines.append(f"  - {name}: {path}")
    lines.append("See README.md for the expected repository layout or environment-variable overrides.")
    raise FileNotFoundError("\n".join(lines))


def open_video() -> tuple[cv2.VideoCapture, float, int, int, int]:
    """Open the configured video and return validated basic metadata."""
    capture = cv2.VideoCapture(str(config.VIDEO_PATH))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open video: {config.VIDEO_PATH}")

    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise ValueError("Video metadata is invalid.")
    return capture, fps, width, height, frame_count


def print_configuration(input_fps: float, horizontal_fov: float, vertical_fov: float) -> None:
    """Print the important shared processing parameters for reproducibility."""
    print(f"Input video FPS: {input_fps:.2f}")
    print(f"Detection/tracking FPS: {config.DETECTION_FPS:.2f}")
    print(f"Confidence threshold: {config.CONFIDENCE_THRESHOLD:.2f}")
    print(f"Minimum confirmations: {config.MIN_OBJECT_CONFIRMATIONS}")
    print(f"Duplicate radius: {config.DUPLICATE_RADIUS_M:.2f} m")
    print(f"Heading source: {config.HEADING_SOURCE}")
    print(
        f"Camera FOV: diagonal={config.CAMERA_DIAGONAL_FOV_DEG:.1f}°, "
        f"horizontal={horizontal_fov:.1f}°, vertical={vertical_fov:.1f}°, "
        f"pitch={config.CAMERA_PITCH_DEG:.1f}°"
    )


def print_detection_summary(detections: list[dict]) -> None:
    """Print one compact terminal row per final confirmed waste object."""
    print("\n" + "=" * 92)
    print(f"FINAL RESULT: {len(detections)} confirmed unique waste object(s)")
    print("=" * 92)
    if not detections:
        print("No confirmed waste objects were found.")
        return

    for item in detections:
        tracks = ",".join(map(str, item.get("track_ids", []))) or "-"
        image = item.get("image_path")
        print(
            f"#{item['object_id']:02d} | conf={item['conf']:.2f} | obs={item['observations']:3d} | "
            f"first={item['time']} | last={item['last_seen']} | "
            f"GPS={item['lat']:.7f},{item['lon']:.7f} | tracks={tracks} | "
            f"image={image if image else '-'}"
        )
