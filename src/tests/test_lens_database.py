from __future__ import annotations

import json
import unittest

from calibration import BreathingPoint, CalibrationPoint, LensProfile, NodalOffset
from lens_database import OPEN_FORMAT_VERSION, export_open_format, import_open_format, validate_open_format
from test_support import workspace_tempdir


def _build_profile() -> LensProfile:
    profile = LensProfile(
        lens_name="Community Lens",
        lens_family="Signature",
        manufacturer="ARRI",
        lens_type="prime",
        mount="LPL",
        sensor_width_mm=36.0,
        sensor_height_mm=24.0,
        image_width=4096,
        image_height=2160,
        notes="Shared profile",
        source="Unit Test",
        color_science="ARRI LogC4",
        working_colorspace="ACEScg",
    )
    profile.add_calibration(
        CalibrationPoint(
            focal_length_mm=50.0,
            k1=-0.01,
            k2=0.002,
            p1=0.0001,
            p2=-0.0001,
            k3=0.0,
            cx=0.5,
            cy=0.5,
            fx=2450.0,
            fy=2452.0,
            rms_error=0.12,
            num_images=14,
        )
    )
    profile.add_nodal_offset(NodalOffset(focal_length_mm=50.0, offset_x=1.0, confidence=0.9, method="parallax"))
    profile.add_breathing_point(BreathingPoint(focus_distance_m=1.2, measured_focal_length_mm=49.2, nominal_focal_length_mm=50.0))
    return profile


class LensDatabaseTests(unittest.TestCase):
    def test_open_format_roundtrip(self):
        profile = _build_profile()

        with workspace_tempdir() as tmpdir:
            path = export_open_format(profile, tmpdir / "community.lensu.json")
            valid, errors = validate_open_format(path)
            loaded = import_open_format(path)

        self.assertTrue(valid, errors)
        self.assertEqual(loaded.to_dict(), profile.to_dict())

    def test_open_format_payload_is_self_describing(self):
        profile = _build_profile()

        with workspace_tempdir() as tmpdir:
            path = export_open_format(profile, tmpdir / "community.lensu.json")
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertEqual(payload["format"], OPEN_FORMAT_VERSION)
        self.assertEqual(payload["lens"]["manufacturer"], "ARRI")
        self.assertEqual(payload["sensor"]["resolution"], [4096, 2160])
        self.assertEqual(payload["color_pipeline"]["working_colorspace"], "ACEScg")
        self.assertIn("tool", payload["metadata"])

    def test_validation_catches_common_errors(self):
        invalid_payload = {
            "format": "lensu-open-v1",
            "lens": {"name": "", "manufacturer": "", "type": "macro", "mount": ""},
            "sensor": {"width_mm": -1, "height_mm": 0, "resolution": [1920]},
            "calibrations": [{"focal_length_mm": 0, "cx": 2.0, "cy": -1.0}],
            "nodal_offsets": [{"focal_length_mm": -10, "confidence": 1.5}],
            "breathing": [{"nominal_focal_length_mm": 0, "points": [{"focus_distance_m": 0, "measured_focal_length_mm": -1}]}],
            "metadata": {},
        }

        with workspace_tempdir() as tmpdir:
            path = tmpdir / "invalid.lensu.json"
            path.write_text(json.dumps(invalid_payload), encoding="utf-8")
            valid, errors = validate_open_format(path)

        self.assertFalse(valid)
        self.assertGreaterEqual(len(errors), 6)


if __name__ == "__main__":
    unittest.main()
