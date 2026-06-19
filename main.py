from video_gps import *

video = VideoGPS("/Volumes/Untitled/DCIM/100MEDIA/DJI_0079.SRT")
Koordinaten = video.get_gps_from_time(timedelta(seconds=10))
print(Koordinaten)
