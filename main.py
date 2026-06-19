from nbclient.client import timestamp

from video_gps import *

Koordinaten = []

video = VideoGPS("/Volumes/Untitled/DCIM/100MEDIA/DJI_0079.SRT")

#for i in timestamps:
#    cord = video.get_gps_from_time(i)
#    Koordinaten.append(cord["lon"],cord["lat"])


#single_cords = video.get_gps_from_time(timedelta(seconds=10))
#Koordinaten.append(single_cords)

cord = video.get_gps_from_time(timedelta(seconds=10))
cord2= video.get_gps_from_time(timedelta(seconds=12))
Koordinaten.append([cord["lat"],cord["lon"]])
Koordinaten.append([cord2["lat"],cord2["lon"]])


print(Koordinaten)
