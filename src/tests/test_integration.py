from __future__ import annotations

import json
import unittest

from calibration import BreathingPoint, CalibrationPoint, LensProfile, NodalOffset
from lens_database import export_open_format, import_open_format, validate_open_format
from nuke_export import export_nuke_gizmo, export_nuke_script
from test_support import workspace_tempdir
from ue_export import export_ue_json, export_ue_python_script


class IntegrationTests(unittest.TestCase):
    def test_full_profile_workflow_roundtrip(self):
        profile = LensProfile(
            lens_name="Integration Lens",
            lens_family="Test Series",
            manufacturer="Sony",
            lens_type="zoom",
            mount="E",
            sensor_width_mm=24.89,
            sensor_height_mm=18.66,
            image_width=3840,
            image_height=2160,
            notes="Integration workflow",
            source="QA",
            color_science="Sony S-Log3/S-Gamut3.Cine",
            working_colorspace="ACEScg",
        )
        profile.add_calibration(
            CalibrationPoint(
                focal_length_mm=35.0,
                k1=-0.012,
                k2=0.0021,
                p1=0.0002,
                p2=-0.0002,
                k3=0.0,
                cx=0.5,
                cy=0.5,
                fx=2100.0,
                fy=2105.0,
                rms_error=0.11,
                num_images=16,
            )
        )
        profile.add_nodal_offset(
            NodalOffset(
                focal_length_mm=35.0,
                offset_x=1.5,
                offset_y=0.2,
                offset_z=-0.4,
                rotation_x=0.1,
                rotation_y=0.0,
                rotation_z=-0.1,
                confidence=0.95,
                method="parallax",
            )
        )
        profile.add_breathing_point(
            BreathingPoint(
                focus_distance_m=1.0,
                measured_focal_length_mm=34.4,
                nominal_focal_length_mm=35.0,
            )
        )

        with workspace_tempdir() as tmpdir:
            ue_json_path = export_ue_json(profile, tmpdir)
            ue_script_path = export_ue_python_script(profile, ue_json_path.name, tmpdir)
            nuke_script_path = export_nuke_script(profile, tmpdir / "lens.nk")
            nuke_gizmo_path = export_nuke_gizmo(profile, tmpdir / "lens.gizmo")
            open_path = export_open_format(profile, tmpdir / "integration.lensu.json")

            valid, errors = validate_open_format(open_path)
            imported = import_open_format(open_path)

            ue_payload = json.loads(ue_json_path.read_text(encoding="utf-8"))
            nuke_script = nuke_script_path.read_text(encoding="utf-8")
            nuke_gizmo = nuke_gizmo_path.read_text(encoding="utf-8")
            ue_python = ue_script_path.read_text(encoding="utf-8")

        self.assertTrue(valid, errors)
        self.assertEqual(imported.to_dict(), profile.to_dict())
        self.assertEqual(ue_payload["user_metadata"]["working_colorspace"], "ACEScg")
        self.assertEqual(ue_payload["lens_info"]["mount"], "E")
        self.assertIn("Sony S-Log3/S-Gamut3.Cine", nuke_script)
        self.assertIn("ACEScg", nuke_gizmo)
        self.assertIn("create_lens_file", ue_python)


if __name__ == "__main__":
    unittest.main()
