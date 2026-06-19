from nbclient.client import timestamp
import pandas as pd
import folium
import xyzservices.providers as xyz
from video_gps import *


#---GPS Koordinaten aus Video auslesen---

video = VideoGPS("/Volumes/Untitled/DCIM/100MEDIA/DJI_0079.SRT")
koordinaten = []


#Testkoordinaten zum Testen aus Video, später Liste von Timestamps übergeben mit einer for Schleife
koordinaten.append([video.get_gps_from_time(timedelta(seconds=10))["lat"],
                    video.get_gps_from_time(timedelta(seconds=10))["lon"]])
koordinaten.append([video.get_gps_from_time(timedelta(seconds=20))["lat"],
                    video.get_gps_from_time(timedelta(seconds=20))["lon"]])

print(koordinaten)


#---Karte erstellen----

mean_lat = sum(coord[0] for coord in koordinaten) / len(koordinaten)
mean_lon = sum(coord[1] for coord in koordinaten) / len(koordinaten)

m = folium.Map(
    location=[mean_lat, mean_lon],
    zoom_start=17,
    tiles=xyz.Esri.WorldImagery
)


#---Marker setzen---
for coordinate in koordinaten: #wenn es nur die coordinaten sein sollen
    folium.Marker(
        location=[coordinate[0], coordinate[1]],
        popup="",
        icon=folium.Icon(color="green")
    ).add_to(m)

m.save("map.html")





