"""Live demonstration: real-time video playback, analysis and map updates."""

import time

import cv2

import config
from pipeline.processor import DetectionPipeline
from pipeline.runtime import (
    open_video,
    print_configuration,
    print_detection_summary,
    validate_required_files,
)
from visualization.live_map import LiveMapServer
from visualization.map_output import save_static_map

WINDOW_NAME = "Drone Waste Detection - Live"


def run_live() -> None:
    """Run the shared detection pipeline in real-time presentation mode."""
    validate_required_files()
    video, input_fps, width, height, _ = open_video()
    pipeline = DetectionPipeline(input_fps, width, height)

    # Start a persistent browser map. Marker data changes, but the whole map page
    # is never reloaded, preventing the old white-screen refresh failure.
    live_map = LiveMapServer(
        output_dir=config.OUTPUT_DIR,
        map_path=config.LIVE_MAP_PATH,
        data_path=config.LIVE_DATA_PATH,
        host=config.LIVE_MAP_HOST,
        port=config.LIVE_MAP_PORT,
        poll_ms=config.LIVE_MAP_POLL_MS,
        fallback_location=config.MAP_FALLBACK_LOCATION,
    )
    live_map.start()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_NAME, config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT)

    print("Drone Waste Detection - LIVE mode")
    print_configuration(input_fps, pipeline.horizontal_fov_deg, pipeline.vertical_fov_deg)
    print("Press q in the video window to stop.\n")

    # Synchronize processing/display to the video's own time axis.
    start_real_time = time.perf_counter()
    frame_index = 0

    try:
        while True:
            success, frame = video.read()
            if not success:
                break

            result = pipeline.process_frame(frame, frame_index)
            if result.map_changed:
                live_map.update(pipeline.confirmed_detections())

            resized = cv2.resize(
                result.display_frame,
                (config.DISPLAY_WIDTH, config.DISPLAY_HEIGHT),
                interpolation=cv2.INTER_AREA,
            )
            cv2.imshow(WINDOW_NAME, resized)

            # Prevent the analysis loop from racing ahead of the live video demo.
            video_seconds = frame_index / input_fps
            elapsed = time.perf_counter() - start_real_time
            if video_seconds > elapsed:
                time.sleep(video_seconds - elapsed)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
            frame_index += 1
    finally:
        video.release()
        cv2.destroyAllWindows()

    detections = pipeline.confirmed_detections()
    live_map.update(detections)
    live_map.stop()

    # Also save a self-contained static final map with embedded screenshots.
    save_static_map(detections, config.BATCH_MAP_PATH, config.MAP_FALLBACK_LOCATION)
    print_detection_summary(detections)
    print(f"\nLive map files: {config.OUTPUT_DIR}")
    print(f"Static final map: {config.BATCH_MAP_PATH}")


if __name__ == "__main__":
    run_live()
