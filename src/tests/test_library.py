from __future__ import annotations

import unittest
from unittest.mock import patch

import lens_library
import src.lens_library as lens_library_module
from calibration import CalibrationPoint, LensProfile
from test_support import workspace_tempdir


def _profile(name: str) -> LensProfile:
    profile = LensProfile(lens_name=name)
    profile.add_calibration(CalibrationPoint(focal_length_mm=35.0, rms_error=0.2))
    return profile


class LibraryTests(unittest.TestCase):
    def test_library_save_load(self):
        with workspace_tempdir() as tmpdir:
            with patch.object(lens_library_module, "LIBRARY_DIR", tmpdir):
                saved = lens_library.save_to_library(_profile("Library Lens"))
                loaded = lens_library.load_from_library(saved.name)
        self.assertEqual(loaded.lens_name, "Library Lens")
        self.assertEqual(loaded.calibration_points[0].focal_length_mm, 35.0)

    def test_library_search(self):
        with workspace_tempdir() as tmpdir:
            with patch.object(lens_library_module, "LIBRARY_DIR", tmpdir):
                lens_library.save_to_library(_profile("Cooke Test Lens"))
                lens_library.save_to_library(_profile("Canon Test Lens"))
                results = lens_library.search_library(lens_name="cooke")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Cooke Test Lens")


if __name__ == "__main__":
    unittest.main()
