"""General pinhole-camera geolocation using ray-ground intersection.

Coordinate conventions
----------------------
Local drone/camera axes before world rotation:
    x = right
    y = forward
    z = up

Camera pitch:
    0 deg   -> optical axis horizontal/forward
   -90 deg  -> optical axis vertically downward (nadir)

Heading:
    0 deg   -> north
    90 deg  -> east

The current project assumes camera yaw is aligned with drone heading except for
CAMERA_YAW_OFFSET_DEG and assumes zero roll. The pitch calculation itself is
fully general and therefore is not restricted to the -90 degree test video.
"""

import math
from .gps_utils import offset_gps


def fov_from_diagonal(diagonal_fov_deg: float, image_width: int, image_height: int) -> tuple[float, float]:
    """Convert diagonal rectilinear FOV into horizontal and vertical FOV."""
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive.")
    if not 0.0 < diagonal_fov_deg < 180.0:
        raise ValueError("Diagonal FOV must be between 0 and 180 degrees.")

    aspect = image_width / image_height
    tan_diag = math.tan(math.radians(diagonal_fov_deg) / 2.0)
    tan_v = tan_diag / math.sqrt(aspect * aspect + 1.0)
    tan_h = aspect * tan_v
    horizontal = math.degrees(2.0 * math.atan(tan_h))
    vertical = math.degrees(2.0 * math.atan(tan_v))
    return horizontal, vertical


def image_point_to_camera_ray(
    center_x: float,
    center_y: float,
    image_width: int,
    image_height: int,
    horizontal_fov_deg: float,
    vertical_fov_deg: float,
) -> tuple[float, float, float]:
    """Return an unnormalised ray (right, forward, up) before gimbal pitch.

    Pixel centers are converted with the pinhole model rather than by linearly
    interpolating angles. This is important away from the image centre.
    """
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive.")

    nx = (center_x - image_width / 2.0) / (image_width / 2.0)
    ny_up = -(center_y - image_height / 2.0) / (image_height / 2.0)

    x = nx * math.tan(math.radians(horizontal_fov_deg) / 2.0)
    y = 1.0
    z = ny_up * math.tan(math.radians(vertical_fov_deg) / 2.0)
    return x, y, z


def rotate_ray_for_gimbal(
    ray: tuple[float, float, float],
    camera_pitch_deg: float,
    camera_roll_deg: float = 0.0,
) -> tuple[float, float, float]:
    """Rotate camera ray by roll then pitch in local drone coordinates."""
    x, y, z = ray

    # Roll around optical/forward axis (y). Usually zero in stabilized footage.
    roll = math.radians(camera_roll_deg)
    x_r = x * math.cos(roll) + z * math.sin(roll)
    y_r = y
    z_r = -x * math.sin(roll) + z * math.cos(roll)

    # Pitch around local right axis (x). Negative values tilt camera down.
    pitch = math.radians(camera_pitch_deg)
    x_p = x_r
    y_p = y_r * math.cos(pitch) - z_r * math.sin(pitch)
    z_p = y_r * math.sin(pitch) + z_r * math.cos(pitch)
    return x_p, y_p, z_p


def ray_ground_intersection(
    ray_local: tuple[float, float, float],
    altitude_m: float,
) -> tuple[float, float, float]:
    """Intersect local ray with flat ground z=-altitude.

    Returns (right_m, forward_m, slant_distance_m).
    """
    if altitude_m <= 0:
        raise ValueError("Altitude must be positive.")

    x, y, z = ray_local
    if z >= -1e-9:
        raise ValueError(
            "Selected image ray does not intersect the ground in front of the camera. "
            "Check camera pitch/FOV and the bounding-box position."
        )

    scale = -altitude_m / z
    right_m = scale * x
    forward_m = scale * y
    slant_m = scale * math.sqrt(x * x + y * y + z * z)
    return right_m, forward_m, slant_m


def rotate_local_to_world(
    right_m: float,
    forward_m: float,
    heading_deg: float,
    camera_yaw_offset_deg: float = 0.0,
) -> tuple[float, float]:
    """Rotate camera-local right/forward offset into north/east coordinates."""
    heading = math.radians((heading_deg + camera_yaw_offset_deg) % 360.0)
    north_m = forward_m * math.cos(heading) - right_m * math.sin(heading)
    east_m = forward_m * math.sin(heading) + right_m * math.cos(heading)
    return north_m, east_m


def estimate_object_gps(
    drone_lat: float,
    drone_lon: float,
    altitude_m: float,
    heading_deg: float,
    center_x: float,
    center_y: float,
    image_width: int,
    image_height: int,
    diagonal_fov_deg: float,
    camera_pitch_deg: float,
    camera_yaw_offset_deg: float = 0.0,
    camera_roll_deg: float = 0.0,
) -> dict[str, float]:
    """Estimate ground/GPS position of a detected object's bounding-box centre."""
    horizontal_fov_deg, vertical_fov_deg = fov_from_diagonal(
        diagonal_fov_deg, image_width, image_height
    )
    ray = image_point_to_camera_ray(
        center_x=center_x,
        center_y=center_y,
        image_width=image_width,
        image_height=image_height,
        horizontal_fov_deg=horizontal_fov_deg,
        vertical_fov_deg=vertical_fov_deg,
    )
    ray = rotate_ray_for_gimbal(
        ray,
        camera_pitch_deg=camera_pitch_deg,
        camera_roll_deg=camera_roll_deg,
    )
    right_m, forward_m, slant_m = ray_ground_intersection(ray, altitude_m)
    north_m, east_m = rotate_local_to_world(
        right_m,
        forward_m,
        heading_deg=heading_deg,
        camera_yaw_offset_deg=camera_yaw_offset_deg,
    )
    gps = offset_gps(drone_lat, drone_lon, north_m, east_m)
    return {
        **gps,
        "right_offset_m": right_m,
        "forward_offset_m": forward_m,
        "north_offset_m": north_m,
        "east_offset_m": east_m,
        "ground_distance_m": math.hypot(right_m, forward_m),
        "slant_distance_m": slant_m,
        "horizontal_fov_deg": horizontal_fov_deg,
        "vertical_fov_deg": vertical_fov_deg,
    }
