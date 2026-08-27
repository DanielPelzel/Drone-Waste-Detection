"""Unit tests for the non-neural core logic."""

import unittest
from datetime import timedelta

from detection.frame_sampler import TimeFrameSampler
from detection.waste_registry import WasteRegistry
from geolocation.camera_geometry import (
    estimate_object_gps,
    fov_from_diagonal,
    image_point_to_camera_ray,
    ray_ground_intersection,
    rotate_ray_for_gimbal,
)


class CameraGeometryTests(unittest.TestCase):
    def test_fov_split_is_reasonable_for_16_9(self):
        horizontal, vertical = fov_from_diagonal(82.1, 3840, 2160)
        self.assertGreater(horizontal, vertical)
        self.assertLess(horizontal, 82.1)
        self.assertLess(vertical, 82.1)

    def test_nadir_center_is_directly_below_drone(self):
        result = estimate_object_gps(
            drone_lat=51.0,
            drone_lon=9.0,
            altitude_m=10.0,
            heading_deg=0.0,
            center_x=960,
            center_y=540,
            image_width=1920,
            image_height=1080,
            diagonal_fov_deg=82.1,
            camera_pitch_deg=-90.0,
        )
        self.assertAlmostEqual(result["ground_distance_m"], 0.0, places=6)
        self.assertAlmostEqual(result["lat"], 51.0, places=7)
        self.assertAlmostEqual(result["lon"], 9.0, places=7)

    def test_minus_45_center_hits_ground_one_altitude_forward(self):
        ray = image_point_to_camera_ray(960, 540, 1920, 1080, 70, 45)
        ray = rotate_ray_for_gimbal(ray, camera_pitch_deg=-45.0)
        right, forward, _ = ray_ground_intersection(ray, altitude_m=10.0)
        self.assertAlmostEqual(right, 0.0, places=6)
        self.assertAlmostEqual(forward, 10.0, places=6)


class SamplerTests(unittest.TestCase):
    def test_10fps_sampler_over_30fps_input(self):
        sampler = TimeFrameSampler(10.0)
        hits = [i for i in range(31) if sampler.should_process(i / 30.0)]
        self.assertEqual(hits[:4], [0, 3, 6, 9])
        self.assertGreaterEqual(len(hits), 10)


class RegistryTests(unittest.TestCase):
    def test_geographic_duplicate_confirms_same_object(self):
        registry = WasteRegistry(duplicate_radius_m=1.0, min_confirmations=2)
        first = registry.observe(
            lat=51.0,
            lon=9.0,
            time=timedelta(seconds=1),
            confidence=0.8,
            track_id=1,
            altitude_m=3.5,
            heading_deg=0,
            ground_distance_m=1.0,
        )
        second = registry.observe(
            lat=51.000003,
            lon=9.0,
            time=timedelta(seconds=2),
            confidence=0.9,
            track_id=99,
            altitude_m=3.5,
            heading_deg=0,
            ground_distance_m=1.1,
        )
        self.assertTrue(first.is_new_object)
        self.assertFalse(first.confirmed)
        self.assertEqual(second.object_id, first.object_id)
        self.assertTrue(second.became_confirmed)
        self.assertEqual(len(registry.confirmed_detections()), 1)


if __name__ == "__main__":
    unittest.main()
