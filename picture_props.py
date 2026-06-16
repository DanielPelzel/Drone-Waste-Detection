from PIL import Image
from PIL.ExifTags import GPS, TAGS
import os
import json

from scipy.optimize import direct


def to_decimal(coords, ref):
    degrees, minutes, seconds = coords
    decimal = float(degrees) + float(minutes) / 60 + float(seconds) / 3600
    return decimal * {"N": 1, "S": -1, "E": 1, "W": -1}[ref]

def get_gps(image_path):
    img = Image.open(image_path)
    exif = img.getexif()
    exif_ifd = exif.get_ifd(34853)
    lat = to_decimal(exif_ifd[2], exif_ifd[1])
    lon  = to_decimal(exif_ifd[4], exif_ifd[3])

    return lat, lon

def get_all_gps(directory_path):
    gps_cords = []
    for file in os.listdir(directory_path):



        if file.endswith(".JPG"):
            full_path = os.path.join(directory_path, file)
            lat, lon = get_gps(full_path)

            if lat == None and lon == None:
                continue

            gps_cords.append((file, lat, lon))
    return gps_cords


directory_path = "/media/daniel-pelzel/7048-990F/DCIM/100MEDIA/"
gps = get_all_gps(directory_path)
print(gps)





directory_path = "/media/daniel-pelzel/7048-990F/DCIM/100MEDIA/"


# print(TAGS)