"""Fast offline evaluation using the same detection rules as live mode."""

import math
import time
import webbrowser

import cv2

import config
from pipeline.processor import DetectionPipeline
from pipeline.runtime import (
    open_video,
    print_configuration,
    print_detection_summary,
    validate_required_files,
)
from visualization.map_output import save_static_map


def _target_frame_indices(input_fps: float, frame_count: int) -> set[int]:
    """Return the exact input-frame indices selected by the shared time sampler.

    Live mode reads every video frame and lets ``TimeFrameSampler`` decide when
    the next 10-FPS analysis instant has been reached. Batch mode calculates
    those same frame indices in advance so non-analysis frames can be skipped
    without changing which video moments are sent to YOLO.
    """
    if frame_count <= 0:
        return set()

    duration_seconds = (frame_count - 1) / input_fps
    target_count = int(math.floor(duration_seconds * config.DETECTION_FPS + 1e-9)) + 1

    indices: set[int] = set()
    for sample_index in range(target_count):
        target_seconds = sample_index / config.DETECTION_FPS
        # The live sampler processes the first frame whose timestamp reaches
        # the target time. The tiny epsilon avoids floating-point overshoot.
        frame_index = int(math.ceil(target_seconds * input_fps - 1e-9))
        if 0 <= frame_index < frame_count:
            indices.add(frame_index)
    return indices


def _open_final_map(path) -> None:
    """Open the completed batch map in the default browser."""
    try:
        webbrowser.open(path.resolve().as_uri())
    except Exception as exc:
        print(f"Could not open the final map automatically: {exc}")


def run_batch() -> None:
    """Analyze the video offline and immediately show the completed result map."""
    validate_required_files()
    video, input_fps, width, height, frame_count = open_video()

    # The shared pipeline uses exactly the same model, confidence threshold,
    # tracker, geolocation and duplicate logic as live.py. Batch mode only
    # disables debug logging and creation of annotated display frames.
    pipeline = DetectionPipeline(
        input_fps,
        width,
        height,
        verbose=False,
        create_display_frame=False,
    )

    print("Drone Waste Detection - BATCH mode")
    print_configuration(input_fps, pipeline.horizontal_fov_deg, pipeline.vertical_fov_deg)
    print("Fast offline processing: no real-time playback and no live map updates.")
    print("Detection rules and analyzed video moments are identical to live.py.\n")

    target_indices = _target_frame_indices(input_fps, frame_count)
    total_targets = len(target_indices)
    processed_targets = 0
    next_progress = 10
    frame_index = 0
    start_time = time.perf_counter()

    try:
        while frame_index < frame_count:
            # grab() advances the video stream without converting the frame into
            # an image. retrieve() is only called for frames that are actually
            # analyzed by YOLO, avoiding unnecessary full frame decoding/copying.
            if not video.grab():
                break

            if frame_index in target_indices:
                success, frame = video.retrieve()
                if not success:
                    break

                pipeline.process_frame(frame, frame_index)
                processed_targets += 1

                if total_targets:
                    percent = int(processed_targets / total_targets * 100)
                    if percent >= next_progress:
                        print(f"Progress: {min(percent, 100):3d}%")
                        while next_progress <= percent:
                            next_progress += 10

            frame_index += 1
    finally:
        video.release()

    elapsed = time.perf_counter() - start_time
    detections = pipeline.confirmed_detections()

    # Build one complete, portable HTML map after analysis. Context screenshots
    # are embedded directly into the HTML by save_static_map().
    save_static_map(
        detections,
        config.BATCH_MAP_PATH,
        config.MAP_FALLBACK_LOCATION,
    )

    print(f"\nAnalysis completed in {elapsed:.1f} s.")
    print(f"Analyzed frames: {processed_targets} of {frame_count}")
    print_detection_summary(detections)
    print(f"\nFinal map: {config.BATCH_MAP_PATH}")
    print("Opening final map in the default browser...")

    _open_final_map(config.BATCH_MAP_PATH)


if __name__ == "__main__":
    run_batch()
