from __future__ import annotations

import json
import socket
import unittest

from calibration import CalibrationPoint, CameraRig, LensProfile
from livelink_emitter import LiveLinkEmitter
from session_autosave import load_autosave, write_autosave
from test_support import workspace_tempdir


class LiveLinkAndAutosaveTests(unittest.TestCase):
    def test_livelink_emitter_sends_udp_payload(self):
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1.0)
        try:
            profile = LensProfile(lens_name="Emitter Lens")
            profile.add_calibration(CalibrationPoint(focal_length_mm=35.0, k1=-0.02, cx=0.51, cy=0.49))
            emitter = LiveLinkEmitter(target_ip="127.0.0.1", port=receiver.getsockname()[1])
            try:
                emitter.send_static_profile(profile, 35.0)
                payload, _ = receiver.recvfrom(4096)
            finally:
                emitter.close()
        finally:
            receiver.close()

        message = json.loads(payload.decode("utf-8"))
        self.assertEqual(message["SubjectName"], "LensU")
        self.assertEqual(message["FocalLength"], 35.0)
        self.assertEqual(len(message["DistortionParameters"]), 5)

    def test_autosave_roundtrip(self):
        rig = CameraRig(rig_name="Autosave Rig")
        profile = LensProfile(lens_name="Autosave Lens")
        profile.add_calibration(CalibrationPoint(focal_length_mm=50.0, k1=-0.01))
        rig.add_camera("Main", profile)

        with workspace_tempdir() as tmpdir:
            path = tmpdir / "autosave.json"
            write_autosave(rig=rig, selected_camera_label="Main", calibration_runs={"50.000": {"mode": "Checkerboard"}}, path=path)
            restored = load_autosave(path)

        self.assertIsNotNone(restored)
        self.assertEqual(restored["rig"].rig_name, "Autosave Rig")
        self.assertEqual(restored["selected_camera_label"], "Main")
        self.assertEqual(restored["rig"].cameras["Main"].lens_name, "Autosave Lens")
        self.assertEqual(restored["calibration_runs"], {})


if __name__ == "__main__":
    unittest.main()
