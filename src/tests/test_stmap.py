from __future__ import annotations

import unittest

import numpy as np

from stmap import generate_stmap


class STMapTests(unittest.TestCase):
    def test_stmap_generation(self):
        camera_matrix = np.array([[100.0, 0.0, 2.0], [0.0, 100.0, 1.5], [0.0, 0.0, 1.0]], dtype=np.float32)
        dist_coeffs = np.zeros((1, 5), dtype=np.float32)
        stmap = generate_stmap(camera_matrix, dist_coeffs, image_size=(4, 3))
        self.assertEqual(stmap.shape, (3, 4, 3))
        self.assertTrue(np.isclose(stmap[0, 0, 0], 0.125, atol=1e-4))
        self.assertTrue(np.isclose(stmap[0, 0, 1], (0.5 / 3.0), atol=1e-4))

    def test_stmap_dimensions(self):
        camera_matrix = np.array([[500.0, 0.0, 320.0], [0.0, 500.0, 240.0], [0.0, 0.0, 1.0]], dtype=np.float32)
        dist_coeffs = np.zeros((1, 5), dtype=np.float32)
        stmap = generate_stmap(camera_matrix, dist_coeffs, image_size=(640, 480), output_size=(320, 240))
        self.assertEqual(stmap.shape, (240, 320, 3))


if __name__ == "__main__":
    unittest.main()

