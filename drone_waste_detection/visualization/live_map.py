"""Stable live map that updates markers without reloading the browser page."""

import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from urllib.parse import urlparse
import webbrowser


class _QuietHandler(SimpleHTTPRequestHandler):
    """HTTP handler that suppresses repetitive browser polling log messages."""

    def log_message(self, format, *args):
        """Disable the default HTTP request log output."""
        return


class LiveMapServer:
    """Serve one persistent Leaflet page and provide marker data from memory.

    The browser keeps one Leaflet map open for the entire live demonstration.
    Marker updates are returned directly by the local HTTP server instead of
    repeatedly replacing a JSON file on disk. This avoids Windows/OneDrive file
    locking problems and prevents map output errors from interrupting detection.
    """

    def __init__(
        self,
        output_dir: Path,
        map_path: Path,
        data_path: Path,
        host: str,
        port: int,
        poll_ms: int,
        fallback_location: tuple[float, float],
    ) -> None:
        self.output_dir = Path(output_dir)
        self.map_path = Path(map_path)
        # Kept as part of the public interface for compatibility with config.py.
        # Live marker data itself is no longer written to this file.
        self.data_path = Path(data_path)
        self.host = host
        self.port = int(port)
        self.poll_ms = int(poll_ms)
        self.fallback_location = fallback_location
        self._httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._payload_json = "[]"
        self._payload_lock = threading.Lock()

    def start(self) -> None:
        """Create the map page, start the local server and open the browser."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._write_html()
        self.update([])

        live_map = self

        class LiveMapRequestHandler(_QuietHandler):
            """Serve static map assets and dynamic in-memory detection data."""

            def do_GET(self) -> None:
                """Return live detections directly for the JSON polling route."""
                if urlparse(self.path).path == "/detections.json":
                    with live_map._payload_lock:
                        response_body = live_map._payload_json.encode("utf-8")

                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                    self.send_header("Pragma", "no-cache")
                    self.send_header("Content-Length", str(len(response_body)))
                    self.end_headers()
                    self.wfile.write(response_body)
                    return

                super().do_GET()

        handler = partial(LiveMapRequestHandler, directory=str(self.output_dir))
        try:
            self._httpd = ThreadingHTTPServer((self.host, self.port), handler)
        except OSError:
            # If the preferred port is occupied, use any available local port.
            self._httpd = ThreadingHTTPServer((self.host, 0), handler)

        self.port = self._httpd.server_port
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()
        webbrowser.open(f"http://{self.host}:{self.port}/{self.map_path.name}")

    def stop(self) -> None:
        """Stop the local map server without blocking application shutdown."""
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None

        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def update(self, detections: list[dict]) -> None:
        """Publish the current confirmed objects to the browser in memory."""
        payload = []

        # Convert the internal detection dictionaries into JSON-safe map data.
        for item in detections:
            image_path = item.get("image_path")
            image_data_uri = None
            if image_path is not None:
                path = Path(image_path)
                if path.exists():
                    # Embed the JPEG directly in the in-memory JSON payload.
                    # The browser therefore never races against a file write or
                    # OneDrive synchronization while loading a popup image.
                    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
                    image_data_uri = f"data:image/jpeg;base64,{encoded}"

            payload.append(
                {
                    "object_id": item["object_id"],
                    "lat": item["lat"],
                    "lon": item["lon"],
                    "first_seen": str(item["time"]),
                    "last_seen": str(item["last_seen"]),
                    "conf": item["conf"],
                    "observations": item["observations"],
                    "track_ids": item.get("track_ids", []),
                    "altitude_m": item["altitude_m"],
                    "heading_deg": item["heading_deg"],
                    "ground_distance_m": item["ground_distance_m"],
                    "image_data_uri": image_data_uri,
                }
            )

        # Replacing one Python string is fast and, unlike replacing a file on
        # disk, cannot be blocked by OneDrive or another Windows process.
        serialized = json.dumps(payload, indent=2)
        with self._payload_lock:
            self._payload_json = serialized

    def _write_html(self) -> None:
        """Write the persistent Leaflet page used for the entire live run."""
        lat, lon = self.fallback_location
        html = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>Drone Waste Detection - Live Map</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\">
  <style>
    html, body, #map {{ height: 100%; margin: 0; }}
    .status {{ position:absolute; z-index:1000; top:10px; right:10px; background:white; padding:7px 10px; border-radius:5px; font:13px sans-serif; box-shadow:0 1px 5px rgba(0,0,0,.35); }}
    .popup-img {{ display:block; width:100%; max-width:100%; height:auto; box-sizing:border-box; border-radius:6px; margin-top:8px; }}
  </style>
</head>
<body>
  <div id=\"map\"></div>
  <div class=\"status\" id=\"status\">Waiting for detections…</div>
  <script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\"></script>
  <script>
    const map = L.map('map').setView([{lat}, {lon}], 12);
    L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{{z}}/{{y}}/{{x}}', {{
      maxZoom: 20,
      attribution: 'Tiles &copy; Esri'
    }}).addTo(map);
    const layer = L.layerGroup().addTo(map);
    let firstNonEmptyUpdate = true;
    let lastPayload = null;

    function esc(value) {{
      return String(value).replace(/[&<>'\"]/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','\"':'&quot;'}}[c]));
    }}

    async function refreshMarkers() {{
      try {{
        const response = await fetch('detections.json?ts=' + Date.now(), {{cache:'no-store'}});
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const data = await response.json();
        const serialized = JSON.stringify(data);
        if (serialized === lastPayload) return;
        lastPayload = serialized;
        layer.clearLayers();
        const bounds = [];

        for (const item of data) {{
          const tracks = item.track_ids.length ? item.track_ids.join(', ') : 'unavailable';
          const image = item.image_data_uri ? `<br><img class=\"popup-img\" src=\"${{item.image_data_uri}}\" alt=\"Waste detection context screenshot\">` : '<br><em>No screenshot available.</em>';
          const popup = `<b>Waste Object ${{item.object_id}}</b><br>` +
            `First seen: ${{esc(item.first_seen)}}<br>` +
            `Last seen: ${{esc(item.last_seen)}}<br>` +
            `Best confidence: ${{Number(item.conf).toFixed(2)}}<br>` +
            `Observations: ${{item.observations}}<br>` +
            `Track IDs: ${{esc(tracks)}}<br>` +
            `Altitude: ${{Number(item.altitude_m).toFixed(2)}} m<br>` +
            `Heading: ${{Number(item.heading_deg).toFixed(1)}}°<br>` +
            `Object ground distance: ${{Number(item.ground_distance_m).toFixed(2)}} m<br>` +
            `GPS: ${{Number(item.lat).toFixed(7)}}, ${{Number(item.lon).toFixed(7)}}` + image;
          const marker = L.marker([item.lat, item.lon]).bindPopup(popup, {{minWidth:300, maxWidth:330}});
          marker.bindTooltip(`Waste Object ${{item.object_id}} | Confidence ${{Number(item.conf).toFixed(2)}}`);
          marker.addTo(layer);
          bounds.push([item.lat, item.lon]);
        }}

        document.getElementById('status').textContent = `${{data.length}} confirmed waste object(s)`;
        if (data.length && firstNonEmptyUpdate) {{
          map.fitBounds(bounds, {{maxZoom:19, padding:[30,30]}});
          firstNonEmptyUpdate = false;
        }}
      }} catch (error) {{
        document.getElementById('status').textContent = 'Map data retrying…';
      }}
    }}

    refreshMarkers();
    setInterval(refreshMarkers, {self.poll_ms});
  </script>
</body>
</html>"""
        self.map_path.write_text(html, encoding="utf-8")
