from __future__ import annotations

import unittest

from calibration import AnamorphicInfo, CalibrationPoint, CameraRig, LensProfile
from test_support import workspace_tempdir


class CalibrationTests(unittest.TestCase):
    def test_calibration_point_creation(self):
        point = CalibrationPoint(focal_length_mm=50.0, k1=-0.02, rms_error=0.12)
        self.assertEqual(point.focal_length_mm, 50.0)
        self.assertEqual(point.k1, -0.02)
        self.assertEqual(point.rms_error, 0.12)

    def test_lens_profile_add_calibration(self):
        profile = LensProfile(lens_name="Test Zoom")
        profile.add_calibration(CalibrationPoint(focal_length_mm=75.0))
        profile.add_calibration(CalibrationPoint(focal_length_mm=35.0))
        profile.add_calibration(CalibrationPoint(focal_length_mm=75.0, k1=0.01))
        self.assertEqual([point.focal_length_mm for point in profile.calibration_points], [35.0, 75.0])
        self.assertEqual(profile.calibration_points[-1].k1, 0.01)

    def test_lens_profile_json_roundtrip(self):
        profile = LensProfile(
            lens_name="Roundtrip Lens",
            lens_family="Test Family",
            lens_type="prime",
            notes="Approximate",
            source="Unit test",
            encoder_mappings={"focus": [{"encoder": 0.0, "value": 1.0}]},
            anamorphic=AnamorphicInfo(squeeze_ratio=1.5, desqueeze_applied=True),
        )
        profile.add_calibration(CalibrationPoint(focal_length_mm=50.0, k1=-0.01))

        with workspace_tempdir() as tmpdir:
            path = tmpdir / "profile.json"
            profile.save_json(path)
            loaded = LensProfile.load_json(path)

        self.assertEqual(loaded.lens_name, "Roundtrip Lens")
        self.assertEqual(loaded.lens_family, "Test Family")
        self.assertEqual(loaded.notes, "Approximate")
        self.assertEqual(loaded.source, "Unit test")
        self.assertEqual(loaded.encoder_mappings["focus"][0]["value"], 1.0)
        self.assertIsNotNone(loaded.anamorphic)
        self.assertEqual(loaded.anamorphic.squeeze_ratio, 1.5)
        self.assertEqual(loaded.calibration_points[0].k1, -0.01)

    def test_anamorphic_info(self):
        info = AnamorphicInfo(squeeze_ratio=2.0, desqueeze_applied=False)
        self.assertEqual(info.squeeze_ratio, 2.0)
        self.assertFalse(info.desqueeze_applied)

    def test_fisheye_fields_roundtrip(self):
        point = CalibrationPoint(
            focal_length_mm=14.0,
            is_fisheye=True,
            fisheye_coeffs=[0.1, -0.01, 0.001, 0.0],
        )
        profile = LensProfile(lens_name="Fisheye Test")
        profile.add_calibration(point)
        self.assertTrue(profile.calibration_points[0].is_fisheye)
        self.assertEqual(profile.calibration_points[0].fisheye_coeffs[0], 0.1)

    def test_camera_rig_json_roundtrip(self):
        rig = CameraRig(rig_name="VP Stage")
        main = LensProfile(lens_name="Main Cam")
        witness = LensProfile(lens_name="Witness Cam")
        main.add_calibration(CalibrationPoint(focal_length_mm=35.0, k1=-0.02))
        witness.add_calibration(CalibrationPoint(focal_length_mm=50.0, k1=-0.01))
        rig.add_camera("Main", main)
        rig.add_camera("Witness", witness)

        with workspace_tempdir() as tmpdir:
            path = tmpdir / "rig.json"
            rig.save_json(path)
            loaded = CameraRig.load_json(path)

        self.assertEqual(loaded.rig_name, "VP Stage")
        self.assertEqual(sorted(loaded.cameras.keys()), ["Main", "Witness"])
        self.assertEqual(loaded.cameras["Main"].calibration_points[0].focal_length_mm, 35.0)
        self.assertEqual(loaded.cameras["Witness"].lens_name, "Witness Cam")


if __name__ == "__main__":
    unittest.main()
