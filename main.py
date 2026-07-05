#from nbclient.client import timestamp
#import pandas as pd
import folium
import xyzservices.providers as xyz
from video_gps import *
from detect_waste_timestamps import detect_waste_timestamps


#---GPS Koordinaten aus Video auslesen---

video = VideoGPS(r"C:\Users\Jim Yektai\OneDrive\Documents\Muellprojekt\DJI_0079.srt")
koordinaten = []

#---Filter von Trash detection nach Konfidenz, Zeitabstand zur letzten Erkennung und Anzahl aufeinanderfolgender Frames mit Müllfund---

conf_value = 0.75
min_gap_seconds_value = 1.5
required_consecutive_frames_value = 3

#---Videoanalyse: Zeitstempel der Müllfunde aus dem Video extrahiert---

timestamps = detect_waste_timestamps(
    video_path=r"C:\Users\Jim Yektai\OneDrive\Documents\Muellprojekt\DJI_0079.mp4",
    model_path=r"C:\Users\Jim Yektai\OneDrive\Documents\Muellprojekt\runs\detect\waste_freeze10_selective_v5_continued\weights\best.pt",
    conf=conf_value,
    min_gap_seconds=min_gap_seconds_value,
    required_consecutive_frames=required_consecutive_frames_value
)

print(f"{len(timestamps)} Müllfunde erkannt.")

#---Liste von Timestamps übergeben mit einer for Schleife---
for t, detection_conf in timestamps:
    gps = video.get_gps_from_time(t)

    koordinaten.append({
    "lat": gps["lat"],
    "lon": gps["lon"],
    "time": t,
    "conf": detection_conf
})

    print(f"{t} | conf={detection_conf:.2f} -> {gps['lat']:.6f}, {gps['lon']:.6f}")

#---Ausgabe der Koordinatenliste---

print("\nKoordinatenliste:")
print(koordinaten)


#---Karte erstellen----

mean_lat = sum(coord["lat"] for coord in koordinaten) / len(koordinaten)
mean_lon = sum(coord["lon"] for coord in koordinaten) / len(koordinaten)

m = folium.Map(
    location=[mean_lat, mean_lon],
    zoom_start=17,
    tiles=xyz.Esri.WorldImagery
)


#---Marker setzen---
for coordinate in koordinaten:
    folium.Marker(
        location=[coordinate["lat"], coordinate["lon"]],
        popup=(
            f"Zeit: {coordinate['time']}<br>"
            f"Confidence: {coordinate['conf']:.2f}"
        ),
        icon=folium.Icon(color="green")
    ).add_to(m)

filename = f"map_conf{conf_value}_frames{required_consecutive_frames_value}_gap{min_gap_seconds_value}.html"
m.save(filename)

print(f"Karte gespeichert als: {filename}")





