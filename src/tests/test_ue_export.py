from __future__ import annotations

import json
import unittest

from calibration import CalibrationPoint, LensProfile
from test_support import workspace_tempdir
from ue_export import export_ue_json, export_ue_python_script


def _sample_profile() -> LensProfile:
    profile = LensProfile(
        lens_name="UE Test Lens",
        manufacturer="ARRI",
        mount="LPL",
        color_science="ARRI LogC4",
        working_colorspace="ACEScg",
        image_width=1920,
        image_height=1080,
    )
    profile.add_calibration(
        CalibrationPoint(
            focal_length_mm=50.0,
            k1=-0.01,
            k2=0.001,
            p1=0.0,
            p2=0.0,
            k3=0.0,
            cx=0.5,
            cy=0.5,
            fx=1000.0,
            fy=1000.0,
        )
    )
    return profile


class UEExportTests(unittest.TestCase):
    def test_ue_json_structure(self):
        profile = _sample_profile()
        with workspace_tempdir() as tmpdir:
            json_path = export_ue_json(profile, tmpdir)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["lens_info"]["lens_name"], "UE Test Lens")
        self.assertEqual(payload["lens_info"]["manufacturer"], "ARRI")
        self.assertEqual(payload["lens_info"]["mount"], "LPL")
        self.assertEqual(payload["user_metadata"]["color_science"], "ARRI LogC4")
        self.assertEqual(payload["distortion_table"][0]["distortion_info"]["parameters"][0], -0.01)
        self.assertEqual(payload["focal_length_table"][0]["zoom"], 50.0)

    def test_ue_python_script_generated(self):
        profile = _sample_profile()
        with workspace_tempdir() as tmpdir:
            json_path = export_ue_json(profile, tmpdir)
            script_path = export_ue_python_script(profile, json_path.name, tmpdir)
            script = script_path.read_text(encoding="utf-8")
        self.assertIn("create_lens_file", script)
        self.assertIn("UE_Test_Lens", script)

    def test_fisheye_forces_stmap_mode(self):
        profile = LensProfile(lens_name="UE Fisheye Lens", image_width=1920, image_height=1080)
        profile.add_calibration(
            CalibrationPoint(
                focal_length_mm=14.0,
                fx=800.0,
                fy=800.0,
                is_fisheye=True,
                fisheye_coeffs=[0.01, -0.001, 0.0001, 0.0],
            )
        )
        with workspace_tempdir() as tmpdir:
            json_path = export_ue_json(profile, tmpdir, data_mode="Parameters")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["data_mode"], "STMap")
        self.assertEqual(payload["st_map_table"][0]["st_map_info"]["projection_model"], "equidistant")


if __name__ == "__main__":
    unittest.main()
