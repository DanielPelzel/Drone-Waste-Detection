import re
from datetime import timedelta

"""Liest SRT Dateien aus und gibt eine Liste an Blöcken pro Block zurück"""
def read_file(file_path):
    with open(file_path, 'r') as file:
        content = file.read()
        content_list = content.split('\n\n')
        return content_list

def gps_time_list(content_list):
    gps_time_list = []
    for block in content_list:
        time = re.search(r"(\d{2}:\d{2}:\d{2},\d+) -->", block)
        lon = re.search(r"\[longitude: (\d{1,3}\.\d+)", block)
        lat = re.search(r"\[latitude: (\d{1,3}\.\d+)", block)

        if time and lon and lat:
            time_str = time.group(1)
            h, m, rest = time_str.split(":")
            s,ms = rest.split(",")
            time = timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))
            gps_time_list.append((time, lon.group(1), lat.group(1)))

    return gps_time_list

def get_gps_from_time(time, liste):
    closest = min(liste, key=lambda x: abs(x[0] - time))
    return closest[0], closest[1], closest[2]

def str_to_timedelta(time_str):

    h, m, rest = time_str.split(":")
    s,ms = rest.split(",")
    return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))


srt_datei = "/media/daniel-pelzel/7048-990F/DCIM/100MEDIA/DJI_0073.SRT"

content_list = read_file(srt_datei)
list = gps_time_list(content_list)

t = str_to_timedelta("00:00:20,10")
cord = get_gps_from_time(t, list)
print(cord)