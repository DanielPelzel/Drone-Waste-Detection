"""Central configuration for the drone waste detection applications.

Both ``live.py`` and ``batch.py`` import this file. Keeping every detection,
tracking and geolocation parameter in one place guarantees that both execution
modes use the same processing rules.
"""

from pathlib import Path
import os

# The repository root is the directory containing this file.
PROJECT_ROOT = Path(__file__).resolve().parent


def _env_path(variable_name: str, default: Path) -> Path:
    """Return an optional environment-variable path or the repository default."""
    value = os.environ.get(variable_name)
    return Path(value).expanduser() if value else default


# -----------------------------------------------------------------------------
# Input and output paths
# -----------------------------------------------------------------------------
# The video is deliberately not committed by default because the current demo
# file is larger than GitHub's normal 100 MB file limit. Put the video at the
# default location below or set DRONE_WASTE_VIDEO to another file.
VIDEO_PATH = _env_path("DRONE_WASTE_VIDEO", PROJECT_ROOT / "data" / "Dji_0079comp.mp4")
SRT_PATH = _env_path("DRONE_WASTE_SRT", PROJECT_ROOT / "data" / "DJI_0079.SRT")
MODEL_PATH = _env_path(
    "DRONE_WASTE_MODEL",
    PROJECT_ROOT
    / "AI"
    / "runs"
    / "detect"
    / "waste_freeze10_selective_v5_continued"
    / "weights"
    / "best.pt",
)

OUTPUT_DIR = PROJECT_ROOT / "outputs"
SNAPSHOT_DIR = OUTPUT_DIR / "snapshots"
LIVE_MAP_PATH = OUTPUT_DIR / "live_map.html"
LIVE_DATA_PATH = OUTPUT_DIR / "detections.json"
BATCH_MAP_PATH = OUTPUT_DIR / "batch_map.html"

# -----------------------------------------------------------------------------
# Detection and tracking parameters shared by BOTH applications
# -----------------------------------------------------------------------------
# YOLO/ByteTrack is executed at this temporal rate while the input video itself
# can keep its original frame rate.
DETECTION_FPS = 10.0
CONFIDENCE_THRESHOLD = 0.75
TRACKER_CONFIG = "bytetrack.yaml"

# A localized waste candidate must be observed this many times before it is
# accepted as a confirmed physical waste object.
MIN_OBJECT_CONFIRMATIONS = 2

# Observations whose estimated object coordinates are closer than this distance
# are treated as the same physical object. ByteTrack IDs are only an additional
# temporal association signal, not the final duplicate criterion.
DUPLICATE_RADIUS_M = 0.75

# -----------------------------------------------------------------------------
# Camera model and geolocation assumptions
# -----------------------------------------------------------------------------
# DJI Mini 3 camera diagonal field of view. Horizontal and vertical field of
# view are derived from the actual video resolution at runtime.
CAMERA_DIAGONAL_FOV_DEG = 82.1

# Camera pitch convention: 0° = horizontal, -90° = vertically downward.
# The supplied test flight was recorded approximately at nadir.
CAMERA_PITCH_DEG = -90.0
CAMERA_YAW_OFFSET_DEG = 0.0
CAMERA_ROLL_DEG = 0.0

# Relative altitude from the SRT is used whenever available. This fallback is
# only used if the SRT sample does not contain a valid positive relative height.
DEFAULT_ALTITUDE_M = 3.5

# The supplied SRT does not contain a reliable drone/gimbal yaw value. The
# default therefore estimates heading from GPS trajectory. "fixed" can be used
# when a known heading is available.
HEADING_SOURCE = "trajectory"  # Allowed values: "trajectory" or "fixed".
DEFAULT_HEADING_DEG = 0.0
FIXED_HEADING_DEG = 0.0
HEADING_MIN_DISPLACEMENT_M = 0.50

# -----------------------------------------------------------------------------
# Live display parameters
# -----------------------------------------------------------------------------
DISPLAY_WIDTH = 960
DISPLAY_HEIGHT = 540
LIVE_MAP_HOST = "127.0.0.1"
LIVE_MAP_PORT = 8765
LIVE_MAP_POLL_MS = 750
MAP_FALLBACK_LOCATION = (51.3127, 9.4797)
