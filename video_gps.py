import re
from datetime import timedelta


class VideoGPS():
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.gps_cords = []
        self._extract()


    def _read_file(self):
        """
        Liest die SRT-Datei ein und gibt Inhalt aus Liste von Blöcken zurück
        :return: Liste von Strings, je Block ein Eintrag
        """

        with open(self.file_path, 'r') as file:
            content = file.read()
            content_list = content.split('\n\n')
            return content_list



    def _gps_time_list(self, content_list):
        """
        Geht die Liste von Strings durch und extrahiert GPS-Zeitpunkte, lat und lon
        :param content_list:
        :return: Eine Liste von Tupeln (Zeit, lon, lat)
        """

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
                gps_time_list.append((time, float(lon.group(1)), float(lat.group(1))))

        return gps_time_list


    def get_gps_from_time(self, time: timedelta):
        """
        Gibt die GPS Daten zum nächstgelegenen Zeitpunkt zurück
        :param time:
        :return: Dict mit 'timestamp' (timedelta), 'lon' (float), 'lat' (float)
        """

        closest = min(self.gps_cords, key=lambda x: abs(x[0] - time))
        return {"timestamp": closest[0],
                "lon": closest[1],
                "lat" : closest[2]
                }

    def _extract(self):
        """
        Kombiniert _read_file und _gps_time_list
        Wird automatisch aufgerufen, wenn Instanz erstellt und befüllt gps_cords
        :return:
        """

        content_list = self._read_file()
        self.gps_cords = self._gps_time_list(content_list)


