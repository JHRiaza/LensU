from __future__ import annotations

import unittest

from presets import list_presets, load_preset


class PresetTests(unittest.TestCase):
    def test_presets_load(self):
        presets = list_presets()
        self.assertGreaterEqual(len(presets), 5)
        loaded = load_preset("cooke_s4i")
        self.assertEqual(loaded.lens_family, "Cooke S4/i")
        self.assertTrue(bool(loaded.notes))
        self.assertGreaterEqual(len(loaded.calibration_points), 1)


if __name__ == "__main__":
    unittest.main()
