from __future__ import annotations

import unittest

from calibration import CalibrationPoint, LensProfile
from nuke_export import export_nuke_gizmo, export_nuke_script
from test_support import workspace_tempdir


class NukeExportTests(unittest.TestCase):
    def test_nuke_script_contains_expected_nodes(self):
        profile = LensProfile(
            lens_name="Cooke 50mm",
            manufacturer="Cooke",
            mount="PL",
            color_science="ARRI LogC4",
            working_colorspace="ACEScg",
            image_width=2048,
            image_height=1152,
        )
        profile.add_calibration(CalibrationPoint(focal_length_mm=50.0, k1=-0.02, k2=0.001, p1=0.0001, p2=-0.0001))

        with workspace_tempdir() as tmpdir:
            path = export_nuke_script(profile, tmpdir / "lens.nk")
            text = path.read_text(encoding="utf-8")

        self.assertIn("LensDistortion", text)
        self.assertIn("STMap", text)
        self.assertIn("Read_Plate", text)
        self.assertIn("Color Science: ARRI LogC4", text)

    def test_nuke_gizmo_contains_expected_nodes(self):
        profile = LensProfile(lens_name="Cooke 50mm", color_science="ARRI LogC4", working_colorspace="ACEScg")
        profile.add_calibration(CalibrationPoint(focal_length_mm=50.0, k1=-0.02))

        with workspace_tempdir() as tmpdir:
            path = export_nuke_gizmo(profile, tmpdir / "lens.gizmo")
            text = path.read_text(encoding="utf-8")

        self.assertIn("Gizmo", text)
        self.assertIn("LensDistortion", text)
        self.assertIn("Input", text)
        self.assertIn("ACEScg", text)


if __name__ == "__main__":
    unittest.main()
