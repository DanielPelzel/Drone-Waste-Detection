#---timedelta Rechnet Sekunden in Videozeit um---
#---cv2 liest das Video frame für frame---
from datetime import timedelta
import cv2
from ultralytics import YOLO

#---trainiertes Modell wird geladen und auf das Video angewendet, um Müll Zeitpunkte zu erkennen.
#Ausgabe einer Liste von Zeitpunkten, an denen Müll erkannt wurde, zusammen mit der Konfidenz---
def detect_waste_timestamps(
    video_path,
    model_path,
    conf=0.8,
    min_gap_seconds=3.0,
    required_consecutive_frames=5
):
    model = YOLO(model_path)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)

    if fps <= 0:
        raise ValueError("FPS konnte nicht gelesen werden.")

    timestamps = []
    last_detection_time = None
    frame_index = 0
    consecutive_detection_frames = 0

#---Frame by Frame Überprüfung ob Müll erkannt wird---
    while True:
        success, frame = cap.read()

#---Video zuende wenn kein Frame mehr gelesen werden kann---
        if not success:
            break

#--- Prüfen des aktuellen Frames---
        results = model(frame, conf=conf, verbose=False)
        boxes = results[0].boxes

        detected = boxes is not None and len(boxes) > 0

#---Müll in aufeinanderfolgenden Frames erkennen---
        if detected:
            consecutive_detection_frames += 1
        else:
            consecutive_detection_frames = 0

        if consecutive_detection_frames == required_consecutive_frames:
            current_time = timedelta(seconds=frame_index / fps)

#---prüfen, ob letzter Fund weit genug zurück liegt---
            if (
                last_detection_time is None
                or (current_time - last_detection_time).total_seconds() >= min_gap_seconds
            ):
#---bester Konfidenzwert im Frame wird gespeichert, Hinterlegung in der Liste---
                best_confidence = float(boxes.conf.max())
                timestamps.append((current_time, best_confidence))
                last_detection_time = current_time

        frame_index += 1

#---Ausgabe Timestampliste---
    cap.release()
    return timestamps


if __name__ == "__main__":
    video_path = "DJI_0079.mp4"
    model_path = "runs/detect/waste_freeze10/weights/best.pt"

    timestamps = detect_waste_timestamps(video_path, model_path)

    print("Gefundene Müll-Zeitpunkte:")
    for timestamp in timestamps:
        print(timestamp)