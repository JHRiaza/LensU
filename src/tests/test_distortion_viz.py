from __future__ import annotations

import unittest

import numpy as np

from calibration import CalibrationPoint
from distortion_viz import (
    compare_distortion_profiles,
    render_distortion_grid,
    render_distortion_magnitude_map,
    render_distortion_vector_field,
)


class DistortionVisualizationTests(unittest.TestCase):
    def setUp(self):
        self.point = CalibrationPoint(
            focal_length_mm=50.0,
            k1=-0.08,
            k2=0.015,
            p1=0.001,
            p2=-0.0008,
            k3=0.0,
            cx=0.5,
            cy=0.5,
            fx=1200.0,
            fy=1180.0,
            rms_error=0.25,
        )
        self.other_point = CalibrationPoint(
            focal_length_mm=50.0,
            k1=-0.03,
            k2=0.008,
            p1=0.0002,
            p2=-0.0001,
            k3=0.0,
            cx=0.5,
            cy=0.5,
            fx=1200.0,
            fy=1180.0,
            rms_error=0.18,
        )
        self.image_size = (1280, 720)

    def test_distortion_renderers_return_images(self):
        for image in (
            render_distortion_grid(self.point, self.image_size),
            render_distortion_magnitude_map(self.point, self.image_size),
            render_distortion_vector_field(self.point, self.image_size),
        ):
            self.assertEqual(image.shape, (self.image_size[1], self.image_size[0], 3))
            self.assertEqual(image.dtype, np.uint8)
            self.assertGreater(int(image.std()), 0)

    def test_profile_comparison_renders_side_by_side(self):
        comparison = compare_distortion_profiles(self.point, self.other_point, self.image_size)
        self.assertEqual(comparison.shape[0], self.image_size[1])
        self.assertGreater(comparison.shape[1], self.image_size[0] * 2)
        self.assertEqual(comparison.dtype, np.uint8)


if __name__ == "__main__":
    unittest.main()
