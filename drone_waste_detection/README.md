# Drone Waste Detection

This repository contains two execution modes that share **one identical waste-detection pipeline**:

- `live.py` — real-time demonstration with video preview and continuously updating map.
- `batch.py` — fast full-video evaluation without real-time playback, followed by the complete map and terminal result list.

The detection, tracking, confirmation, duplicate handling and object geolocation are implemented only once in `pipeline/processor.py`. The two applications therefore do not contain separate detection conditions that can drift apart.

## Processing pipeline

`Video -> temporal sampler -> YOLO -> ByteTrack -> bounding-box center -> SRT telemetry -> camera geometry -> estimated waste GPS -> physical-object registry -> screenshot + map`

### Important behavior

- YOLO/ByteTrack runs at `DETECTION_FPS`, independent of drone movement.
- A waste candidate must satisfy the shared confidence threshold and confirmation count.
- Duplicate prevention is based primarily on the estimated geographic object position. ByteTrack helps temporal association but a changed tracker ID does not automatically create a new waste object.
- Relative altitude is read from the DJI SRT when available.
- The waste position is calculated from drone GPS, altitude, heading estimate, camera model and the bounding-box center.
- Each confirmed map marker includes the best saved screenshot of that waste object.

## Repository layout

```text
Drone-Waste-Detection/
├─ live.py
├─ batch.py
├─ config.py
├─ requirements.txt
├─ AI/
│  └─ runs/detect/waste_freeze10_selective_v5_continued/weights/best.pt
├─ data/
│  ├─ DJI_0079.SRT
│  └─ Dji_0079comp.mp4        # add separately / Git LFS
├─ detection/
├─ geolocation/
├─ pipeline/
├─ visualization/
├─ tests/
└─ outputs/                    # generated automatically
```

## Installation

Python 3.10–3.12 is recommended for the broadest Ultralytics/OpenCV compatibility.

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

Linux/macOS:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

## Required files

The model and SRT can be stored in the default repository paths shown above. Put the demo video at:

```text
data/Dji_0079comp.mp4
```

The current demo video is larger than GitHub's normal 100 MB per-file limit. For a GitHub submission, use Git LFS or provide the video separately. The application also accepts external paths without source changes:

- `DRONE_WASTE_VIDEO`
- `DRONE_WASTE_SRT`
- `DRONE_WASTE_MODEL`

Example in PowerShell:

```powershell
$env:DRONE_WASTE_VIDEO="C:\path\to\Dji_0079comp.mp4"
python live.py
```

## Run the live demonstration

```bash
python live.py
```

The application opens the video window and a browser map. Press `q` in the video window to stop.

### Why the live map no longer hangs on refresh

The map page is loaded only once. A small local HTTP server publishes `outputs/detections.json`, and JavaScript updates the Leaflet markers by polling that JSON file. The browser does **not** repeatedly reload a changing HTML file. This removes the previous full-page refresh mechanism that could leave a white loading screen or stale map state.

## Run the fast evaluation

```bash
python batch.py
```

Batch mode processes the same sampled frames with the same YOLO model, ByteTrack state, confidence threshold, confirmation count, duplicate registry and geolocation functions. It simply removes real-time waiting and GUI display. At the end it prints every confirmed object in the terminal and writes:

```text
outputs/batch_map.html
```

The final HTML map embeds the detection screenshots directly, so it can be opened independently after processing.

## Configuration

All shared parameters are in `config.py`. Important values are:

- `DETECTION_FPS = 10.0`
- `CONFIDENCE_THRESHOLD = 0.75`
- `MIN_OBJECT_CONFIRMATIONS = 2`
- `DUPLICATE_RADIUS_M = 0.75`
- `CAMERA_DIAGONAL_FOV_DEG = 82.1`
- `CAMERA_PITCH_DEG = -90.0`
- `HEADING_SOURCE = "trajectory"`

The supplied SRT does not contain reliable gimbal/drone yaw. `trajectory` therefore estimates a heading from GPS motion. This is an explicit project limitation: trajectory direction is not always identical to the drone body heading. A drone/SRT containing gimbal pitch and yaw would allow the camera geometry to use the full intended model directly.

## Tests

The core mathematical and registry logic can be checked with:

```bash
python -m unittest discover -s tests -v
```

These tests cover camera geometry, temporal sampling and geographic duplicate confirmation. Neural-network accuracy itself is evaluated with the trained YOLO results and the demo video rather than unit tests.
