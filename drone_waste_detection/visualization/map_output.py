"""Static Folium map generation with embedded waste-detection context screenshots."""

import base64
from pathlib import Path

import folium
import xyzservices.providers as xyz


def _image_data_uri(path: Path | None) -> str | None:
    """Encode a saved screenshot directly into the HTML map for portability."""
    if path is None or not path.exists():
        return None
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def save_static_map(
    detections: list[dict],
    output_path: Path,
    fallback_location: tuple[float, float],
) -> None:
    """Write a complete final map containing one marker per confirmed object."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if detections:
        location = [
            sum(item["lat"] for item in detections) / len(detections),
            sum(item["lon"] for item in detections) / len(detections),
        ]
        zoom = 19
    else:
        location = list(fallback_location)
        zoom = 12

    map_object = folium.Map(location=location, zoom_start=zoom, tiles=xyz.Esri.WorldImagery)

    for item in detections:
        tracks = ", ".join(map(str, item.get("track_ids", []))) or "unavailable"
        image_uri = _image_data_uri(item.get("image_path"))
        image_html = (
            f'<br><img src="{image_uri}" style="max-width:280px;max-height:200px;border-radius:6px;">'
            if image_uri
            else "<br><em>No screenshot available.</em>"
        )
        popup_html = (
            f"<b>Waste Object {item['object_id']}</b><br>"
            f"First seen: {item['time']}<br>"
            f"Last seen: {item['last_seen']}<br>"
            f"Best confidence: {item['conf']:.2f}<br>"
            f"Observations: {item['observations']}<br>"
            f"Track IDs: {tracks}<br>"
            f"Altitude: {item['altitude_m']:.2f} m<br>"
            f"Heading: {item['heading_deg']:.1f}°<br>"
            f"Object ground distance: {item['ground_distance_m']:.2f} m<br>"
            f"GPS: {item['lat']:.7f}, {item['lon']:.7f}"
            f"{image_html}"
        )
        tooltip = (
            f"Waste Object {item['object_id']} | "
            f"Confidence {item['conf']:.2f} | "
            f"GPS {item['lat']:.7f}, {item['lon']:.7f}"
        )

        folium.Marker(
            location=[item["lat"], item["lon"]],
            popup=folium.Popup(popup_html, max_width=330),
            tooltip=tooltip,
            icon=folium.Icon(color="blue"),
        ).add_to(map_object)

    # Folium writes the file once at the end, which is ideal for batch mode.
    map_object.save(output_path)
