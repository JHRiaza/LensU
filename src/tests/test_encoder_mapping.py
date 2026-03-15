from __future__ import annotations

import unittest

from encoder_mapping import EncoderMapping, create_mapping_from_samples


class EncoderMappingTests(unittest.TestCase):
    def test_mapping_samples_sorted_and_clamped(self):
        mapping = create_mapping_from_samples([(65535, 10.0), (-1, 1.0), (100, 2.0)])
        self.assertEqual(mapping[0], (0, 1.0))
        self.assertEqual(mapping[-1], (65535, 10.0))

    def test_interpolates_between_samples(self):
        mapping = EncoderMapping(
            lens_name="Test Lens",
            focus_map=[(0, 1.0), (1000, 5.0)],
            zoom_map=[(0, 24.0), (1000, 50.0)],
            iris_map=[(0, 2.0), (1000, 4.0)],
        )
        self.assertAlmostEqual(mapping.encoder_to_focus(500), 3.0)
        self.assertAlmostEqual(mapping.encoder_to_zoom(500), 37.0)
        self.assertAlmostEqual(mapping.encoder_to_iris(500), 3.0)

    def test_interpolation_accuracy_across_multiple_segments(self):
        mapping = EncoderMapping(
            lens_name="Test Lens",
            focus_map=[(0, 1.0), (1000, 3.0), (4000, 9.0)],
            zoom_map=[],
            iris_map=[],
        )
        self.assertAlmostEqual(mapping.encoder_to_focus(250), 1.5)
        self.assertAlmostEqual(mapping.encoder_to_focus(2500), 6.0)
        self.assertAlmostEqual(mapping.encoder_to_focus(99999), 9.0)


if __name__ == "__main__":
    unittest.main()
